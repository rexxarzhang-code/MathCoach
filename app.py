import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from PIL import Image
import os
from dotenv import load_dotenv
import yaml
from io import BytesIO
import base64
from datetime import datetime
import re

from qcloud_cos import CosConfig, CosS3Client
import hashlib
import json
import urllib.parse

# 版本信息
APP_VERSION = "v1.2.2"
APP_BUILD_DATE = "2026-04-15"

# 加载环境变量
load_dotenv()

# 配置API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')

# 配置腾讯云 COS
TENCENT_SECRET_ID = os.getenv('TENCENT_SECRET_ID')
TENCENT_SECRET_KEY = os.getenv('TENCENT_SECRET_KEY')
TENCENT_COS_REGION = os.getenv('TENCENT_COS_REGION')
TENCENT_COS_BUCKET = os.getenv('TENCENT_COS_BUCKET')

# 初始化 COS 客户端
cos_client = None
if all([TENCENT_SECRET_ID, TENCENT_SECRET_KEY, TENCENT_COS_REGION, TENCENT_COS_BUCKET]):
    try:
        cos_config = CosConfig(
            Region=TENCENT_COS_REGION,
            SecretId=TENCENT_SECRET_ID,
            SecretKey=TENCENT_SECRET_KEY,
            Scheme='https'
        )
        cos_client = CosS3Client(cos_config)
    except Exception as e:
        st.warning(f"COS 初始化失败: {str(e)}")

if QWEN_API_KEY:
    qwen_client = OpenAI(
        api_key=QWEN_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=300.0  # 设置超时时间为300秒（5分钟），避免延展练习生成时超时
    )
else:
    qwen_client = None

# 加载配置文件
def load_config():
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {
            'student': {
                'location': '长沙市',
                'grade': '初中二年级',
                'textbook': '人教版'
            },
            'analysis': {
                'enable_exercises': True,  # 默认开启延展练习
                'difficulty_range': ['相同难度', '稍难', '综合应用']
            }
        }

config = load_config()

# 模型配置
AVAILABLE_MODELS = {
    'qwen': {
        'name': '通义千问 Qwen3.5-Plus (推荐)',
        'model_id': 'qwen3.5-plus-2026-02-15',
        'available': QWEN_API_KEY is not None
    },
    'qwen-3.6-plus': {
        'name': '通义千问 Qwen3.6-Plus (最新)',
        'model_id': 'qwen3.6-plus',
        'available': QWEN_API_KEY is not None
    }
}

def encode_image_base64(image):
    """将PIL图片转换为base64"""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def call_qwen_vision(prompt, images, stream=False, model_id='qwen3.5-plus-2026-02-15'):
    """调用千问视觉模型（支持多图）
    
    Args:
        prompt: 提示词
        images: 单个PIL图片或图片列表
        stream: 是否流式输出
        model_id: 模型ID
    """
    try:
        # 确保images是列表
        if not isinstance(images, list):
            images = [images]
        
        # 限制最多4张图
        if len(images) > 4:
            raise Exception("千问模型最多支持4张图片")
        
        # 构建消息内容
        content = [{'type': 'text', 'text': prompt}]
        for img in images:
            img_base64 = encode_image_base64(img)
            content.append({
                'type': 'image_url', 
                'image_url': {'url': f'data:image/png;base64,{img_base64}'}
            })
        
        response = qwen_client.chat.completions.create(
            model=model_id,
            messages=[{
                'role': 'user',
                'content': content
            }],
            temperature=0.3,  # 降低temperature减少触发内容审核的可能性
            stream=stream
        )
        if stream:
            return response  # 返回流式生成器
        else:
            return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"千问API调用失败: {str(e)}")

def call_vision_model(prompt, images, model_type='qwen', stream=False):
    """统一的视觉模型调用接口（支持多图）
    
    Args:
        prompt: 提示词
        images: 单个PIL图片或图片列表
        model_type: 模型类型
        stream: 是否流式输出
    """
    if model_type in ['qwen', 'qwen-3.6-plus'] and qwen_client:
        # 获取对应的model_id
        model_id = AVAILABLE_MODELS[model_type]['model_id']
        return call_qwen_vision(prompt, images, stream=stream, model_id=model_id)
    else:
        raise Exception(f"模型 {model_type} 不可用,请检查API Key配置")

def stream_qwen_response(response_stream):
    """处理千问流式响应"""
    for chunk in response_stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

def stream_gemini_response(response_stream):
    """处理Gemini流式响应"""
    for chunk in response_stream:
        yield chunk.text

def get_model():
    """获取可用的模型 - 保留用于兼容"""
    return None, st.session_state.get('selected_model', 'qwen')

model, current_model_name = get_model()

def analyze_knowledge_points(images, stream=False):
    """分析题目的知识点和考点（支持多图）
    
    Args:
        images: 单个PIL图片或图片列表（第1张=错题，后续=草稿）
        stream: 是否流式输出
    """
    target_school = config['student'].get('target_school', '雅礼中学')
    school_group = config['student'].get('school_group', '四大五小')
    
    # 确保images是列表
    if not isinstance(images, list):
        images = [images]
    
    # 根据图片数量调整prompt
    if len(images) > 1:
        image_desc = f"""
**图片说明**:
- 第1张图片: 错题本身
- 第2-{len(images)}张图片: 学生的草稿纸/解题过程

请综合分析错题和草稿内容。
"""
    else:
        image_desc = "**图片说明**: 这是错题图片。"
    
    prompt = f"""
你是一位经验丰富的{config['student']['location']}数学老师,深度熟悉{config['student']['textbook']}{config['student']['grade']}教材。

{image_desc}

学生信息:
- 地区: {config['student']['location']}
- 年级: {config['student']['grade']}
- 教材: {config['student']['textbook']}
- **学习目标**: 考上{config['student']['location']}{school_group},目标高中是**{target_school}**

请仔细分析这道题目,重点关注:

1. **核心知识点**: 
   - 这道题主要考查哪些数学知识点?
   - 这些知识点在{config['student']['textbook']}{config['student']['grade']}的哪个学期学习?
   - 是否有超纲内容?(如果有,请明确指出)

2. **考点类型**: 
   - 计算题/证明题/应用题/综合题?
   - 在{config['student']['location']}中考中属于什么题型?
   - **对于目标{target_school}的重要程度**: 必考/常考/偶考

3. **教材章节**: 
   - 精确对应{config['student']['textbook']}{config['student']['grade']}教材的第几章第几节
   - 相关的课本例题编号(如有)

4. **难度等级**: 
   - 对于{config['student']['grade']}学生的难度: 简单/中等/较难/困难
   - 对应考试分值段: 基础题(1-6分)/中档题(7-10分)/压轴题(11-15分)
   - **对于{target_school}录取标准的掌握要求**: 基础必会/重点掌握/拔高训练

5. **常见考试场景**: 
   - {config['student']['location']}哪些学校常考此类题(如长郡、雅礼、麓山等)
   - 通常出现在期中/期末/月考/中考的第几题
   - 近3年{config['student']['location']}真题中的类似题型
   - **{target_school}近年自主招生/选拔考试中的考察频率**

6. **解法要求**:
   - 此题使用的解法是否在教学大纲内?
   - 有无更简单的符合课本的标准解法?

7. **备考建议**:
   - 针对目标{target_school},此知识点的重要性和建议训练强度
   - 类似题型的推荐练习资源

请以清晰的结构化格式输出,使用markdown格式。**特别强调是否有超纲内容或解法,以及对目标{target_school}的重要程度。**
"""
    try:
        selected_model = st.session_state.get('selected_model', 'qwen')
        if stream:
            return call_vision_model(prompt, images, selected_model, stream=True)
        else:
            result = call_vision_model(prompt, images, selected_model)
            return result
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            return f"⚠️ **API配额已用完**\n\n今日免费配额已耗尽,请:\n1. 明天再试\n2. 或升级到付费计划\n3. 查看使用情况: https://ai.dev/rate-limit\n\n错误详情: {str(e)[:200]}"
        else:
            return f"❌ **分析失败**: {str(e)[:200]}"

def diagnose_error(images, knowledge_analysis="", stream=False):
    """诊断学生的错误原因（支持多图，带历史记忆）
    
    Args:
        images: 单个PIL图片或图片列表（第1张=错题，后续=草稿）
        knowledge_analysis: 知识点分析结果（用于提取关键词）
        stream: 是否流式输出
    """
    target_school = config['student'].get('target_school', '雅礼中学')
    school_group = config['student'].get('school_group', '四大五小')
    
    # 确保images是列表
    if not isinstance(images, list):
        images = [images]
    
    # 提取当前题目的关键词
    current_keywords = extract_keywords_from_text(knowledge_analysis)
    
    # 搜索历史相似错题
    similar_errors = search_similar_errors(current_keywords, limit=3)
    
    # 生成记忆提示
    memory_prompt = generate_memory_prompt(similar_errors, current_keywords)
    
    # 根据图片数量调整prompt
    if len(images) > 1:
        image_desc = f"""
**重要提示**: 你收到了{len(images)}张图片:
- 第1张: 错题本身（题目+学生答案）
- 第2-{len(images)}张: 学生的草稿纸

**请特别注意草稿纸内容**,这是诊断错误的关键:
- 草稿上的计算步骤在哪一步出错?
- 有没有划掉重来的痕迹（说明思路混乱）?
- 是计算错误还是概念理解错误?
- 草稿和最终答案是否一致?

通过草稿纸,你可以看到学生的完整解题过程,而不仅仅是最终答案。
"""
    else:
        image_desc = "**图片说明**: 这是错题图片,请根据图片内容分析学生的错误。"
    
    prompt = f"""
你是一位温和耐心的数学老师,请仔细观察这道题目和学生的答题过程(包括草稿痕迹)。

{image_desc}

学生背景:
- 目标: 考上{config['student']['location']}{school_group},目标高中是**{target_school}**
- 当前年级: {config['student']['grade']}

{memory_prompt}

请分析:
1. **学生解题思路**: 学生是怎么思考这道题的?
2. **出错步骤**: 在哪一步出现了错误?{' (请结合草稿纸的内容具体指出)' if len(images) > 1 else ''}
3. **错误类型**: 
   - 概念理解错误
   - 计算失误
   - 审题不清
   - 方法选择不当
   - 其他
4. **错误原因**: 为什么会犯这个错误?可能的思维漏洞是什么?
5. **重复错误检查**: {'⚠️ 根据历史记录，这个知识点不是第一次出错！请特别说明：' if similar_errors else ''}
   {'- 与之前错误的相似之处' if similar_errors else ''}
   {'- 是否存在根本性的理解问题' if similar_errors else ''}
   {'- 为什么会重复犯错' if similar_errors else ''}
6. **改进建议**: 
   - 具体应该如何改进?需要加强哪方面的练习?
   - **针对目标{target_school}**: 此类错误如果不改正,对考入{target_school}的影响程度(严重/中等/轻微)
   - {'**针对重复错误的强化方案**（务必给出具体、可执行的训练计划）' if similar_errors else '建议的训练重点和强度'}

7. **激励与目标**:
   - 以目标{target_school}为动力,给予鼓励和具体的提升路径

请用鼓励和建设性的语气,帮助学生理解错误并改进。使用markdown格式输出。
"""
    try:
        selected_model = st.session_state.get('selected_model', 'qwen')
        if stream:
            return call_vision_model(prompt, images, selected_model, stream=True)
        else:
            result = call_vision_model(prompt, images, selected_model)
            return result
    except Exception as e:
        error_str = str(e).lower()
        
        # 配额错误
        if "quota" in error_str or "429" in error_str:
            return "⚠️ **API配额已用完** - 请稍后重试或升级计划"
        
        # 内容审核错误 - 尝试切换模型或简化prompt
        elif "datainspectionfailed" in error_str or "inappropriate content" in error_str:
            # 如果是千问失败，尝试切换到 Gemini
            if selected_model in ['qwen', 'qwen-max'] and GEMINI_API_KEY:
                try:
                    # 简化 prompt，移除可能触发审核的内容
                    simplified_prompt = f"""
请分析这道数学错题：

1. **学生解题思路**: 学生是怎么思考的?
2. **出错步骤**: 在哪一步出错了?
3. **错误类型**: 概念理解/计算失误/审题不清/方法不当
4. **改进建议**: 如何避免类似错误?

请使用温和、鼓励的语气，用markdown格式输出。
"""
                    result = call_vision_model(simplified_prompt, images, 'gemini', stream=stream)
                    # 添加提示说明使用了备用模型
                    if stream:
                        return result
                    else:
                        return f"⚠️ *（原模型内容审核失败，已自动切换到备用模型）*\n\n{result}"
                except Exception as backup_error:
                    return f"⚠️ **内容审核失败**\n\n千问模型触发内容审核，切换Gemini也失败。\n\n建议：\n1. 检查错题图片是否包含敏感内容\n2. 稍后重试\n3. 联系管理员\n\n错误: {str(backup_error)[:200]}"
            else:
                return f"⚠️ **内容审核失败**\n\nAI模型的安全审核机制被触发，可能原因：\n1. 图片内容被误判\n2. 生成的分析触发了敏感词检测\n\n建议：\n1. 尝试重新上传清晰的错题图片\n2. 稍后重试\n3. 如持续失败，请联系管理员\n\n错误详情: {str(e)[:200]}"
        
        # 其他错误
        else:
            return f"❌ **诊断失败**: {str(e)[:200]}"

def generate_similar_exercises(images, knowledge_analysis, exercise_count=None, stream=False):
    """生成相似的练习题 - 优先从真题库中检索（支持多图）
    
    Args:
        images: 单个PIL图片或图片列表（第1张=错题，后续=草稿）
        knowledge_analysis: 知识点分析结果
        exercise_count: 练习题数量
        stream: 是否流式输出
    """
    # 确保images是列表
    if not isinstance(images, list):
        images = [images]
    
    # 获取当前学期的教学大纲
    semester = config['student'].get('semester', '上学期')
    grade_key = f"八年级{semester}"
    syllabus_content = config.get('analysis', {}).get('syllabus', {}).get(grade_key, [])
    syllabus_str = "、".join(syllabus_content) if syllabus_content else "当前学期已学内容"
    
    forbidden_content = config.get('analysis', {}).get('forbidden', [])
    forbidden_str = "、".join(forbidden_content) if forbidden_content else "超纲内容"
    
    target_school = config['student'].get('target_school', '雅礼中学')
    school_group = config['student'].get('school_group', '四大五小')
    
    # 使用传入的exercise_count，如果没有则使用配置文件中的值
    if exercise_count is None:
        exercise_count = config['analysis']['exercise_count']
    
    # 根据题目数量动态生成难度描述
    if exercise_count == 1:
        difficulty_desc = "- 第1题: 巩固基础,与错题相同知识点,难度相当"
    elif exercise_count == 2:
        difficulty_desc = f"""- 第1题: 巩固基础,与错题相同知识点,难度相当
- 第2题: 轻微变式,增加一个条件或步骤,达到{target_school}中等题水平"""
    else:
        difficulty_desc = f"""- 第1题: {config['analysis']['difficulty_range'][0]} - 巩固基础,与错题相同知识点,难度相当
- 第2题: {config['analysis']['difficulty_range'][1]} - 轻微变式,增加一个条件或步骤,达到{target_school}中等题水平
- 第3题: {config['analysis']['difficulty_range'][2]} - 知识点融合,但**不得超出{config['student']['grade']}教学大纲**,模拟{target_school}选拔题难度"""
    
    prompt = f"""
你是{config['student']['location']}的资深数学教研专家,深度熟悉{config['student']['textbook']}{config['student']['grade']}教材的教学大纲和考试要求。

**学生当前学习阶段**:
- 年级: {config['student']['grade']}
- 学期: {semester}
- 已学范围: {syllabus_str}
- **严禁使用**: {forbidden_str}
- **学习目标**: 考上{config['student']['location']}{school_group},目标高中是**{target_school}**

**重要说明**: 本次任务是为学生推荐**恰好{exercise_count}道**真题练习,而不是自己编题!

**题目来源要求**(极其重要):
1. **必须从近3年真实题库中选择原题**(2023-2026年),包括但不限于:
   - 长沙四大名校近3年真题(雅礼、长郡、师大附中、一中)
   - 长沙名校集团校真题(麓山国际、南雅、明德等)
   - {target_school}近3年期中、期末、月考真题
   - 湖南省近3年中考真题及各地市模拟题
   - **严禁使用2020年以前的旧题**,年份过早的题目会被直接拒收
   
2. **每道题必须标注**:
   - 题目来源(学校名称、年份、考试类型) - **年份必须是2023年及以后**
   - **详细搜索关键词**(供学生在作业帮/小猿搜题/百度作业搜索)
   - 例如: "【来源】2024年长沙市雅礼中学初二下学期期末考试第18题"
   - 例如: "【搜索关键词】雅礼中学 2024 初二期末 勾股定理 第18题"
   
3. **链接有效性**:
   - **不要提供具体的题目URL**,这些链接通常会失效
   - 改为提供**精确的搜索关键词**,学生可以直接在作业帮/小猿搜题中搜索到
   - 搜索关键词必须包含: 学校名+年份+年级+考试类型+知识点
   
4. **如果某道题确实找不到近3年合适的真题**,才可以参考类似真题风格自行编写,但必须注明"改编自XXX年XXX题"

**知识点匹配**:
基于以下知识点分析,选择相关真题:
{knowledge_analysis}

**难度梯度**:
{difficulty_desc}

**几何图形处理**(极其重要):
对于涉及几何图形的题目:
1. **通过搜索关键词让学生自行查找原题**:
   - 提供精确的搜索关键词: "学校名+年份+年级+知识点+题号"
   - 例如: "雅礼中学 2024 初二期末 勾股定理 第18题"
   - 学生可以在作业帮/小猿搜题APP中输入关键词查看原图
   
2. **同时提供详细的文字描述**:
   - 例如: "如图,在△ABC中,AB=AC,点D在BC上,且BD=3cm,DC=4cm,AD垂直BC于D"
   - 描述要包含: 图形类型、关键点位置、边长数据、角度关系
   - **注意**: 文字描述中不要使用数学符号(如⊥),改用中文"垂直"、"平行"等

3. **重要提示**: 
   - **绝对禁止使用ASCII字符图**,学生完全看不懂
   - **不要提供具体URL**,链接很快就会失效
   - **必须提供可精确搜索到原题的关键词**

**教学大纲约束**:
- 初二上学期: 三角形、全等三角形、轴对称、整式乘除、因式分解
- 初二下学期: 分式、二次根式、勾股定理、平行四边形、一次函数
- **禁止使用**: 圆、相似、二次函数、三角函数等超纲内容

**输出格式**:
每道题必须包含:
```
### 练习题X (难度: XXX)

**【来源】** 2024年长沙市雅礼中学初二下学期期末考试第18题

**【如何找到原题和配图】**
1. 打开作业帮APP或小猿搜题APP
2. 输入搜索关键词: "雅礼中学 2024 初二期末 勾股定理 第18题"
3. 即可找到原题和完整几何图

**【题目描述】**
(清晰描述题目内容和条件)
(对于几何图: 用文字详细描述图形,例如"如图,在△ABC中,AB=AC,点D在BC上,BD=3cm,DC=4cm,AD垂直BC于D")

**【考查知识点】** 
勾股定理、等腰三角形性质

**【参考答案】**
(详细解答步骤)

**【解题要点】**
(关键思路、易错点提示)
```

**重要说明**:
- **年份必须是2023-2026年**,旧题会被拒收
- **不要提供具体URL**,这些链接很快失效
- **必须提供精确的搜索关键词**,让学生能在APP中找到原题
- **绝对禁止ASCII字符图**,必须引导学生通过搜索查看真实配图
- 文字描述中不要使用特殊数学符号(如⊥、∠等),改用中文

**特别强调**:
- 真题优先级: {target_school}真题 > 长沙其他名校真题 > 湖南省真题 > 改编题
- 每道题必须有明确来源和**可访问的题目链接**
- 题目链接应来自: 作业帮、小猿搜题、百度作业等主流在线题库平台
- **绝对禁止使用ASCII字符图**,必须让学生通过链接查看真实几何图
- 如果实在无法提供链接,必须给出精确的搜索关键词让学生自行搜索

请立即开始检索并推荐**恰好{exercise_count}道**真题!
"""
    try:
        selected_model = st.session_state.get('selected_model', 'qwen')
        if stream:
            return call_vision_model(prompt, images, selected_model, stream=True)
        else:
            result = call_vision_model(prompt, images, selected_model)
            return result
    except Exception as e:
        error_msg = str(e).lower()
        if "quota" in error_msg or "429" in error_msg:
            return "⚠️ **API配额已用完** - 请稍后重试或升级计划"
        elif "timeout" in error_msg or "timed out" in error_msg:
            return "⚠️ **生成超时** - 延展练习内容较多，请稍后重试或减少练习题数量"
        else:
            return f"❌ **生成失败**: {str(e)[:200]}"

def upload_to_cos(file_data, file_name, file_type='image'):
    """
    上传文件到腾讯云 COS
    
    Args:
        file_data: 文件数据（bytes 或 BytesIO）
        file_name: 文件名
        file_type: 文件类型（image/report）
    
    Returns:
        dict: {'success': bool, 'url': str, 'key': str, 'error': str}
    """
    if not cos_client:
        return {'success': False, 'error': 'COS 未配置'}
    
    try:
        # 生成唯一文件名（使用时间戳+hash避免重复）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_hash = hashlib.md5(file_data if isinstance(file_data, bytes) else file_data.getvalue()).hexdigest()[:8]
        
        # 根据类型确定存储路径
        if file_type == 'image':
            year = datetime.now().strftime('%Y')
            month = datetime.now().strftime('%m')
            cos_key = f"images/{year}/{month}/{timestamp}_{file_hash}_{file_name}"
        else:  # report
            year = datetime.now().strftime('%Y')
            month = datetime.now().strftime('%m')
            cos_key = f"reports/{year}/{month}/{timestamp}_{file_hash}_{file_name}"
        
        # 上传文件
        if isinstance(file_data, bytes):
            response = cos_client.put_object(
                Bucket=TENCENT_COS_BUCKET,
                Body=file_data,
                Key=cos_key,
                EnableMD5=False
            )
        else:
            response = cos_client.put_object(
                Bucket=TENCENT_COS_BUCKET,
                Body=file_data.getvalue(),
                Key=cos_key,
                EnableMD5=False
            )
        
        # 生成访问URL（内部访问）
        url = f"https://{TENCENT_COS_BUCKET}.cos.{TENCENT_COS_REGION}.myqcloud.com/{cos_key}"
        
        return {
            'success': True,
            'url': url,
            'key': cos_key,
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'url': None,
            'key': None
        }

def list_history_from_cos(limit=20):
    """
    从 COS 获取历史记录
    
    Args:
        limit: 返回的最大记录数
    
    Returns:
        list: 历史记录列表 [{'key': str, 'name': str, 'time': str, 'size': int}]
    """
    if not cos_client:
        return []
    
    try:
        # 列出所有图片
        response = cos_client.list_objects(
            Bucket=TENCENT_COS_BUCKET,
            Prefix='images/',
            MaxKeys=limit
        )
        
        if 'Contents' not in response:
            return []
        
        # 解析结果
        history = []
        for item in response['Contents']:
            # 确保 size 是整数类型
            try:
                size = int(item['Size']) if isinstance(item['Size'], str) else item['Size']
            except (ValueError, TypeError):
                size = 0  # 如果转换失败，默认为0
            
            history.append({
                'key': item['Key'],
                'name': os.path.basename(item['Key']),
                'time': item['LastModified'],
                'size': size
            })
        
        # 按时间倒序排序
        history.sort(key=lambda x: x['time'], reverse=True)
        
        return history
    except Exception as e:
        st.error(f"获取历史记录失败: {str(e)}")
        return []

def download_from_cos(cos_key):
    """
    从 COS 下载文件
    
    Args:
        cos_key: COS 对象键
    
    Returns:
        bytes: 文件数据
    """
    if not cos_client:
        return None
    
    try:
        response = cos_client.get_object(
            Bucket=TENCENT_COS_BUCKET,
            Key=cos_key
        )
        # 修复：使用 get_raw_stream().read() 读取完整内容
        # 默认的 read() 只读取 1024 字节
        return response['Body'].get_raw_stream().read()
    except Exception as e:
        st.error(f"下载失败: {str(e)}")
        return None

def delete_from_cos(cos_key):
    """
    从 COS 删除文件
    
    Args:
        cos_key: COS 对象键
    
    Returns:
        dict: {'success': bool, 'error': str}
    """
    if not cos_client:
        return {'success': False, 'error': 'COS 未配置'}
    
    try:
        cos_client.delete_object(
            Bucket=TENCENT_COS_BUCKET,
            Key=cos_key
        )
        return {'success': True, 'error': None}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def delete_history_record(image_key):
    """
    删除历史记录（包括图片和对应的JSON分析）
    
    Args:
        image_key: 图片的 COS 键（images/路径）
    
    Returns:
        dict: {'success': bool, 'deleted_files': list, 'error': str}
    """
    if not cos_client:
        return {'success': False, 'error': 'COS 未配置', 'deleted_files': []}
    
    deleted_files = []
    errors = []
    
    try:
        # 1. 删除图片文件
        result = delete_from_cos(image_key)
        if result['success']:
            deleted_files.append(image_key)
        else:
            errors.append(f"删除图片失败: {result['error']}")
        
        # 2. 查找并删除对应的JSON分析记录
        # 从图片key提取文件名信息（时间戳_hash）
        # 例如：images/2026/03/20260309_135113_f4c676a9_reload_20260309_135113.png
        # 对应：records/2026/03/20260309_*_reload_20260309_135113.png.json
        
        if 'images/' in image_key:
            # 提取完整文件名
            file_name = image_key.split('/')[-1]  # 获取文件名
            parts = file_name.split('_')
            if len(parts) >= 2:
                timestamp = parts[0]  # 20260309
                
                # 构建records路径前缀（与save_analysis_record中的格式一致）
                year = timestamp[:4]
                month = timestamp[4:6]
                search_prefix = f"records/{year}/{month}/"
                
                # 查找匹配的JSON文件（根据原始图片文件名匹配）
                response = cos_client.list_objects(
                    Bucket=TENCENT_COS_BUCKET,
                    Prefix=search_prefix,
                    MaxKeys=100
                )
                
                if 'Contents' in response:
                    for item in response['Contents']:
                        json_key = item['Key']
                        # 检查JSON文件名是否包含原始图片文件名
                        # records/2026/03/20260309_135113_reload_20260309_135113.png.json
                        if json_key.endswith('.json') and file_name in json_key:
                            result = delete_from_cos(json_key)
                            if result['success']:
                                deleted_files.append(json_key)
                            else:
                                errors.append(f"删除JSON失败: {result['error']}")
        
        if errors:
            return {
                'success': False, 
                'error': '; '.join(errors),
                'deleted_files': deleted_files
            }
        else:
            return {
                'success': True, 
                'error': None,
                'deleted_files': deleted_files
            }
            
    except Exception as e:
        return {
            'success': False, 
            'error': str(e),
            'deleted_files': deleted_files
        }

def format_friendly_time(time_str):
    """
    将 ISO 8601 时间格式转换为友好格式
    
    Args:
        time_str: ISO 8601 格式的时间字符串（如：2026-03-04T08:33:48.000Z）
    
    Returns:
        str: 友好格式的时间字符串（如：2026-03-04 16:33:48）
    """
    try:
        # 解析 ISO 8601 格式
        from datetime import datetime
        
        # 移除末尾的 .000Z 或 Z
        if time_str.endswith('Z'):
            time_str = time_str[:-1]
        if '.' in time_str:
            time_str = time_str.split('.')[0]
        
        # 解析时间
        dt = datetime.fromisoformat(time_str)
        
        # 转换为本地时间（UTC+8）
        from datetime import timedelta
        dt = dt + timedelta(hours=8)
        
        # 格式化为友好格式
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        # 如果解析失败，返回原始字符串
        return time_str

def check_image_duplicate(image_data):
    """
    检查图片是否已经上传并分析过
    
    Args:
        image_data: 图片数据（bytes）
    
    Returns:
        dict: {
            'is_duplicate': bool,  # 是否重复
            'record': dict,        # 如果重复，返回之前的分析记录
            'image_key': str,      # 图片的 COS 键
            'upload_time': str     # 首次上传时间
        }
    """
    if not cos_client:
        return {'is_duplicate': False}
    
    try:
        # 计算图片的 MD5 哈希
        image_hash = hashlib.md5(image_data).hexdigest()
        
        # 搜索所有图片，查找相同哈希
        marker = ""
        while True:
            response = cos_client.list_objects(
                Bucket=TENCENT_COS_BUCKET,
                Prefix='images/',
                Marker=marker,
                MaxKeys=1000
            )
            
            if 'Contents' not in response:
                break
            
            # 检查每个图片的哈希
            for item in response['Contents']:
                key = item['Key']
                
                # 跳过目录
                if key.endswith('/'):
                    continue
                
                # 从文件名中提取哈希（格式：YYYYMMDD_HHMMSS_hash_filename）
                filename = os.path.basename(key)
                key_parts = filename.split('_')
                
                if len(key_parts) >= 3:
                    stored_hash = key_parts[2]
                    
                    # 如果哈希匹配，说明是同一张图片
                    if stored_hash == image_hash[:8]:  # 使用前8位哈希
                        # 找到重复图片，查找对应的分析记录
                        upload_time = item['LastModified']
                        
                        # 提取原始文件名（去掉时间戳和哈希）
                        # 格式：YYYYMMDD_HHMMSS_hash_原始文件名.jpg
                        # 原始文件名从第3个下划线后开始
                        original_filename = '_'.join(key_parts[3:])
                        
                        # 搜索 records 目录，查找包含原始文件名的 JSON
                        record_response = cos_client.list_objects(
                            Bucket=TENCENT_COS_BUCKET,
                            Prefix='records/',
                            MaxKeys=1000
                        )
                        
                        if 'Contents' in record_response:
                            for record_item in record_response['Contents']:
                                record_key = record_item['Key']
                                
                                # 检查记录是否对应这张图片
                                # JSON文件名格式：YYYYMMDD_HHMMSS_原始文件名.json
                                if original_filename in record_key and record_key.endswith('.json'):
                                    # 下载并解析记录
                                    try:
                                        record_data = cos_client.get_object(
                                            Bucket=TENCENT_COS_BUCKET,
                                            Key=record_key
                                        )
                                        record_content = record_data['Body'].get_raw_stream().read().decode('utf-8')
                                        record = json.loads(record_content)
                                        
                                        return {
                                            'is_duplicate': True,
                                            'record': record,
                                            'image_key': key,
                                            'upload_time': upload_time
                                        }
                                    except Exception as e:
                                        # 记录解析失败，继续搜索
                                        continue
            
            # 检查是否还有更多对象
            if response['IsTruncated'] == 'false':
                break
            marker = response['NextMarker']
        
        # 没有找到重复
        return {'is_duplicate': False}
    
    except Exception as e:
        st.warning(f"去重检查失败: {str(e)}")
        return {'is_duplicate': False}

def save_analysis_record(image_key, image_name, knowledge_analysis, error_diagnosis, exercises):
    """
    保存错题分析记录到 COS（JSON格式）
    
    Args:
        image_key: 图片的COS键
        image_name: 图片名称
        knowledge_analysis: 知识点分析结果
        error_diagnosis: 错因诊断结果
        exercises: 练习题
    
    Returns:
        dict: {'success': bool, 'record_key': str, 'error': str}
    """
    if not cos_client:
        return {'success': False, 'error': 'COS 未配置'}
    
    try:
        # 提取关键信息（用于后续检索）
        # 简单提取知识点关键词
        knowledge_keywords = extract_keywords_from_text(knowledge_analysis)
        
        # 构建记录
        record = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'image_key': image_key,
            'image_name': image_name,
            'student_info': {
                'grade': config['student']['grade'],
                'location': config['student']['location'],
                'textbook': config['student']['textbook'],
                'semester': config['student'].get('semester', '未设置')
            },
            'analysis': {
                'knowledge_points': knowledge_analysis,
                'error_diagnosis': error_diagnosis,
                'exercises': exercises,
                'keywords': knowledge_keywords  # 用于快速检索
            }
        }
        
        # 保存到 COS
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        record_key = f"records/{datetime.now().strftime('%Y/%m')}/{timestamp}_{image_name}.json"
        
        response = cos_client.put_object(
            Bucket=TENCENT_COS_BUCKET,
            Body=json.dumps(record, ensure_ascii=False, indent=2).encode('utf-8'),
            Key=record_key,
            EnableMD5=False
        )
        
        return {
            'success': True,
            'record_key': record_key,
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'record_key': None
        }

def extract_keywords_from_text(text):
    """
    从分析文本中提取关键知识点
    
    Args:
        text: 分析文本
    
    Returns:
        list: 关键词列表
    """
    # 常见数学知识点关键词库
    math_keywords = [
        '二次函数', '一次函数', '反比例函数', '函数', 
        '勾股定理', '相似三角形', '全等三角形', '三角形',
        '平行四边形', '矩形', '菱形', '正方形', '梯形',
        '圆', '切线', '弦', '圆周角', '圆心角',
        '因式分解', '配方法', '公式法', '十字相乘',
        '方程', '方程组', '不等式', '不等式组',
        '分式', '二次根式', '整式', '代数式',
        '概率', '统计', '平均数', '中位数', '众数',
        '旋转', '平移', '轴对称', '中心对称',
        '角平分线', '中位线', '垂直平分线',
        '计算', '证明', '应用题', '综合题'
    ]
    
    # 在文本中查找关键词
    found_keywords = []
    text_lower = text.lower()
    
    for keyword in math_keywords:
        if keyword in text:
            found_keywords.append(keyword)
    
    return list(set(found_keywords))  # 去重

def search_similar_errors(keywords, limit=5):
    """
    根据关键词搜索历史中的相似错题
    
    Args:
        keywords: 关键词列表
        limit: 返回的最大记录数
    
    Returns:
        list: 相似错题记录列表
    """
    if not cos_client or not keywords:
        return []
    
    try:
        # 列出所有分析记录
        response = cos_client.list_objects(
            Bucket=TENCENT_COS_BUCKET,
            Prefix='records/',
            MaxKeys=500  # 最多检索最近500条（支持长期使用1-2年）
        )
        
        if 'Contents' not in response:
            return []
        
        similar_records = []
        
        # 遍历记录，计算相似度
        for item in response['Contents']:
            try:
                # 下载记录（修复：使用 get_raw_stream().read() 读取完整内容）
                record_data = cos_client.get_object(
                    Bucket=TENCENT_COS_BUCKET,
                    Key=item['Key']
                )
                record = json.loads(record_data['Body'].get_raw_stream().read().decode('utf-8'))
                
                # 计算关键词匹配度
                record_keywords = record.get('analysis', {}).get('keywords', [])
                match_count = len(set(keywords) & set(record_keywords))
                
                if match_count > 0:
                    similar_records.append({
                        'record': record,
                        'match_score': match_count,
                        'match_keywords': list(set(keywords) & set(record_keywords))
                    })
            except:
                continue
        
        # 按匹配度排序
        similar_records.sort(key=lambda x: x['match_score'], reverse=True)
        
        return similar_records[:limit]
    
    except Exception as e:
        st.warning(f"搜索历史记录失败: {str(e)}")
        return []

def generate_memory_prompt(similar_errors, current_keywords):
    """
    基于历史错题生成记忆提示
    
    Args:
        similar_errors: 相似错题列表
        current_keywords: 当前题目的关键词
    
    Returns:
        str: 记忆提示文本（用于添加到 AI prompt）
    """
    if not similar_errors:
        return ""
    
    memory_text = "\n\n**⚠️ 重要提醒：历史错题记忆**\n\n"
    memory_text += "根据错题档案，学生在以下知识点上曾经出现过错误：\n\n"
    
    for idx, item in enumerate(similar_errors, 1):
        record = item['record']
        match_keywords = item['match_keywords']
        timestamp = record.get('timestamp', '未知时间')
        error_diag = record.get('analysis', {}).get('error_diagnosis', '')
        
        # 提取错误类型（简短版本）
        error_summary = error_diag[:200] + "..." if len(error_diag) > 200 else error_diag
        
        memory_text += f"{idx}. **{timestamp}** - 知识点：{', '.join(match_keywords)}\n"
        memory_text += f"   错误类型：{error_summary}\n\n"
    
    memory_text += "**请在本次分析中**：\n"
    memory_text += "1. 特别关注学生是否在相同知识点上重复犯错\n"
    memory_text += "2. 如果是重复错误，请明确指出\"这不是第一次在XX知识点上出错\"\n"
    memory_text += "3. 针对重复错误，给出更具体的改进建议和强化训练方案\n"
    memory_text += "4. 如果错误类型相似，分析是否存在根本性的理解问题\n\n"
    
    return memory_text

def create_report(image_name, knowledge_analysis, error_diagnosis, exercises):
    """生成完整报告"""
    report = f"""# 数学错题分析报告

## 📋 基本信息
- **学生**: {config['student']['grade']} {config['student']['textbook']}
- **地区**: {config['student']['location']}
- **错题**: {image_name}
- **分析时间**: {st.session_state.get('analysis_time', '未记录')}

---

## 📚 知识点分析
{knowledge_analysis}

---

## 🔍 错因诊断
{error_diagnosis}

---

## 💪 延展练习
{exercises}

---

## 📝 温馨提示
1. 请认真完成延展练习,巩固薄弱知识点
2. 遇到困难可以查阅{config['student']['textbook']}教材相关章节
3. 建议将此类错题整理到错题本,定期复习

---
*本报告由AI数学教练自动生成*
"""
    return report

def convert_latex_to_text(text):
    """
    将LaTeX数学公式转换为可读的文本格式，优化根号和分数显示
    """
    # 常见数学符号替换
    replacements = {
        r'\Rightarrow': '⇒',
        r'\Leftarrow': '⇐',
        r'\Leftrightarrow': '⇔',
        r'\rightarrow': '→',
        r'\leftarrow': '←',
        r'\therefore': '∴',
        r'\because': '∵',
        r'\pm': '±',
        r'\times': '×',
        r'\div': '÷',
        r'\leq': '≤',
        r'\geq': '≥',
        r'\neq': '≠',
        r'\approx': '≈',
        r'\infty': '∞',
        r'\angle': '∠',
        r'\triangle': '△',
        r'\circ': '°',
        r'\cdot': '·',
        r'\ldots': '…',
        r'\dots': '…',
        r'\parallel': '∥',
        r'\perp': '⊥',
        r'\in': '∈',
        r'\notin': '∉',
        r'\subset': '⊂',
        r'\subseteq': '⊆',
        r'\alpha': 'α',
        r'\beta': 'β',
        r'\gamma': 'γ',
        r'\theta': 'θ',
        r'\pi': 'π',
        r'\sin': 'sin',
        r'\cos': 'cos',
        r'\tan': 'tan',
    }
    
    # 替换常见符号
    for latex, unicode_char in replacements.items():
        text = text.replace(latex, unicode_char)
    
    # 处理上标 (^) - 增强版本，支持变量的上标
    # 先处理常见的数字上标
    text = re.sub(r'\^2', '²', text)
    text = re.sub(r'\^3', '³', text)
    # 处理多位数上标
    def convert_superscript(match):
        num_str = match.group(1)
        superscript_map = '⁰¹²³⁴⁵⁶⁷⁸⁹'
        return ''.join([superscript_map[int(d)] for d in num_str if d.isdigit()])
    text = re.sub(r'\^(\d+)', convert_superscript, text)
    
    # 处理常见的Unicode分数（完整显示）
    fraction_unicode = {
        '1/2': '½', '1/3': '⅓', '2/3': '⅔', '1/4': '¼', '3/4': '¾',
        '1/5': '⅕', '2/5': '⅖', '3/5': '⅗', '4/5': '⅘',
        '1/6': '⅙', '5/6': '⅚', '1/8': '⅛', '3/8': '⅜', '5/8': '⅝', '7/8': '⅞'
    }
    
    # 处理分数 \frac{a}{b}
    # 优先使用Unicode分数字符
    def convert_fraction(match):
        numerator = match.group(1).strip()
        denominator = match.group(2).strip()
        frac_key = f"{numerator}/{denominator}"
        if frac_key in fraction_unicode:
            return fraction_unicode[frac_key]
        else:
            # 对于复杂分数，使用更清晰的显示方式
            return f"{numerator}/{denominator}"
    
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', convert_fraction, text)
    
    # 处理根号 \sqrt{x} 或 \sqrt[n]{x}
    # 使用Unicode根号符号 √ (U+221A)
    def convert_sqrt(match):
        content = match.group(1).strip()
        # 移除内部的大括号
        content = content.replace('{', '').replace('}', '')
        # 如果内容是单个数字、字母、或简单的数字，不加括号
        if re.match(r'^[a-zA-Z0-9]+$', content) or re.match(r'^\d+$', content):
            return f"√{content}"
        # 如果内容包含运算符，添加括号以便清晰
        elif any(op in content for op in ['+', '-', '*', '/', ' ']):
            return f"√({content})"
        else:
            # 默认不加括号，显示更简洁
            return f"√{content}"
    
    text = re.sub(r'\\sqrt\{([^}]+)\}', convert_sqrt, text)
    # 处理n次根号
    def convert_nth_sqrt(match):
        n = match.group(1).strip()
        content = match.group(2).strip()
        content = content.replace('{', '').replace('}', '')
        return f"{n}√{content}"
    text = re.sub(r'\\sqrt\[([^]]+)\]\{([^}]+)\}', convert_nth_sqrt, text)
    
    # 移除多余的LaTeX语法
    text = text.replace(r'\{', '').replace(r'\}', '')
    text = text.replace(r'\ ', ' ')
    
    return text





# Streamlit UI
st.set_page_config(page_title="数学错题AI教练", page_icon="📐", layout="wide")

# 初始化session state
if 'selected_model' not in st.session_state:
    # 优先使用千问
    if QWEN_API_KEY:
        st.session_state['selected_model'] = 'qwen'
    elif GEMINI_API_KEY:
        st.session_state['selected_model'] = 'gemini'
    else:
        st.session_state['selected_model'] = None

st.title("📐 数学错题AI教练")
semester_display = config['student'].get('semester', '未设置')
target_school = config['student'].get('target_school', '雅礼中学')
school_group = config['student'].get('school_group', '四大五小')

st.markdown(f"**当前配置**: {config['student']['location']} | {config['student']['grade']}{semester_display} | {config['student']['textbook']}")
st.markdown(f"🎯 **学习目标**: 考上长沙{school_group}，目标高中 **{target_school}**")

# 侧边栏配置（先处理侧边栏，确保 selected_model 是最新的）
with st.sidebar:
    st.header("🤖 模型选择")
    
    # 模型选择器
    available_model_options = []
    for key, info in AVAILABLE_MODELS.items():
        if info['available']:
            available_model_options.append((key, info['name']))
    
    if available_model_options:
        # 计算当前选择的索引
        current_model = st.session_state.get('selected_model')
        default_index = 0
        for idx, (key, _) in enumerate(available_model_options):
            if key == current_model:
                default_index = idx
                break
        
        selected = st.radio(
            "选择AI模型",
            options=[k for k, _ in available_model_options],
            format_func=lambda k: AVAILABLE_MODELS[k]['name'],
            index=default_index,
            key='model_selector'  # 添加唯一的 key
        )
        st.session_state['selected_model'] = selected
        
        # 显示模型信息
        st.caption(f"模型ID: `{AVAILABLE_MODELS[selected]['model_id']}`")
    else:
        st.error("❌ 没有可用的模型,请配置API Key")
        selected = None

# 显示当前模型（在侧边栏处理后显示，确保是最新值）
if st.session_state.get('selected_model'):
    model_info = AVAILABLE_MODELS[st.session_state['selected_model']]
    st.info(f"🤖 当前模型: **{model_info['name']}** (`{model_info['model_id']}`)")
else:
    st.error("❌ 未配置任何API Key,请在 .env 文件中配置 QWEN_API_KEY 或 GEMINI_API_KEY")

# 继续侧边栏其他配置
with st.sidebar:
    
    st.divider()
    st.header("⚙️ 配置")
    
    location = st.text_input("地区", value=config['student']['location'])
    grade = st.text_input("年级", value=config['student']['grade'])
    semester = st.selectbox("学期", ["上学期", "下学期"], 
                           index=0 if config['student'].get('semester', '上学期') == '上学期' else 1)
    textbook = st.text_input("教材版本", value=config['student']['textbook'])
    
    st.divider()
    st.subheader("🎯 学习目标")
    target_school = st.text_input(
        "目标高中", 
        value=config['student'].get('target_school', '雅礼中学'),
        help="设置目标高中，AI会根据目标学校调整建议"
    )
    school_group = st.text_input(
        "目标学校群体", 
        value=config['student'].get('school_group', '四大五小'),
        help="例如：四大名校、四大五小等"
    )
    
    st.divider()
    
    # 延展练习开关（默认开启，固定1题）
    enable_exercises = st.checkbox(
        "💪 生成延展练习（推荐）", 
        value=config['analysis'].get('enable_exercises', True),
        help="AI会推荐1道相似练习题，巩固知识点。关闭可提升分析速度。"
    )
    
    if st.button("💾 保存配置"):
        config['student']['location'] = location
        config['student']['grade'] = grade
        config['student']['semester'] = semester
        config['student']['textbook'] = textbook
        config['student']['target_school'] = target_school
        config['student']['school_group'] = school_group
        config['analysis']['enable_exercises'] = enable_exercises
        
        with open('config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)
        
        st.success("✅ 配置已保存!")
        st.rerun()
    
    st.divider()
    
    # COS 历史记录
    if cos_client:
        st.header("📚 错题历史")
        if st.button("📖 查看历史记录", use_container_width=True):
            st.session_state['show_history'] = True
            st.rerun()
    
    st.divider()
    st.markdown("### 💡 使用说明")
    st.markdown("""
    1. 上传图片(最多4张)
       - 第1张: 错题本身 ✅
       - 第2-4张: 草稿纸(可选) 📝
    2. 点击"开始分析"按钮
    3. 查看知识点、错因、练习题
    4. 下载完整报告
    
    💡 **提示**: 上传草稿纸可以帮助AI更准确地定位出错步骤!
    """)
    
    st.divider()
    st.markdown("### ⚠️ 配额提示")
    st.warning("""
    **Gemini免费版限制**:
    - 每天约1500次请求
    - 每次分析需3次请求
    - 如遇配额错误,请明天再试
    - 或访问 [Google AI Studio](https://ai.google.dev/) 升级
    """)
    
    # 版本号显示（调试用）
    st.divider()
    st.caption(f"🔧 {APP_VERSION} ({APP_BUILD_DATE})")

# 主界面
# 检查是否有从历史记录reload的图片
if 'reload_image' in st.session_state:
    # 将图片字节数据转换为Image对象
    reload_img_data = st.session_state['reload_image']
    image = Image.open(BytesIO(reload_img_data))
    
    # 执行去重检查
    if cos_client and 'duplicate_check_done' not in st.session_state:
        with st.spinner("🔍 正在加载历史分析..."):
            # 检查是否重复
            duplicate_check = check_image_duplicate(reload_img_data)
            st.session_state['duplicate_check'] = duplicate_check
            st.session_state['duplicate_check_done'] = True
    
    # 如果找到历史分析，显示它
    if st.session_state.get('duplicate_check', {}).get('is_duplicate', False):
        dup_info = st.session_state['duplicate_check']
        
        # ⚠️ 不要清除reload_image,因为checkbox点击会触发rerun
        
        # ⚠️ 不要清除reload_image,因为checkbox点击会触发rerun
        
        # 格式化时间
        friendly_time = format_friendly_time(dup_info['upload_time'])
        
        # 添加返回按钮
        if st.button("⬅️ 返回主页", key="back_from_reload"):
            # 清除所有reload相关状态
            st.session_state.pop('reload_image', None)
            st.session_state.pop('duplicate_check', None)
            st.session_state.pop('duplicate_check_done', None)
            st.rerun()
        
        st.info(f"📥 已加载 **{friendly_time}** 的分析结果")
        
        record = dup_info['record']
        
        # 显示图片
        st.subheader("📷 原题")
        st.image(image, use_column_width=True)
        
        # 显示分析时间
        if 'timestamp' in record:
            st.caption(f"🕐 分析时间：{record['timestamp']}")
        
        st.divider()
        
        # 显示知识点分析
        if 'analysis' in record and 'knowledge_points' in record['analysis']:
            with st.expander("📚 知识点分析", expanded=True):
                st.markdown(record['analysis']['knowledge_points'])
        
        # 显示错因诊断
        if 'analysis' in record and 'error_diagnosis' in record['analysis']:
            with st.expander("🔍 错因诊断", expanded=True):
                st.markdown(record['analysis']['error_diagnosis'])
        
        # 显示延展练习
        if 'analysis' in record and 'exercises' in record['analysis']:
            with st.expander("💪 延展练习", expanded=True):
                st.markdown(record['analysis']['exercises'])
        
        st.divider()
        
        # 提供下载按钮
        st.markdown("### 📥 导出报告")
        
        # 🔍 调试信息按钮
        if st.checkbox("🔍 显示调试信息", key="debug_history_reload"):
            with st.expander("调试数据", expanded=True):
                st.json({
                    'timestamp': record.get('timestamp', '未记录'),
                    'has_knowledge_points': 'knowledge_points' in record.get('analysis', {}),
                    'has_error_diagnosis': 'error_diagnosis' in record.get('analysis', {}),
                    'has_exercises': 'exercises' in record.get('analysis', {}),
                    'knowledge_preview': record.get('analysis', {}).get('knowledge_points', '')[:100] + "...",
                })
                st.info("📋 如果这里显示的时间是正确的,但StackEdit打印出来的时间不对,说明可能是StackEdit的缓存问题。请使用'📥 下载Markdown'按钮,然后手动导入到StackEdit。")
        
        # 生成Markdown报告
        markdown_report = f"""# 📊 数学错题分析报告

## 🕐 分析时间
{record.get('timestamp', '未记录')}

---

## 📚 知识点分析
{record['analysis'].get('knowledge_points', '暂无内容')}

---

## 🔍 错因诊断
{record['analysis'].get('error_diagnosis', '暂无内容')}

---

## 💪 延展练习
{record['analysis'].get('exercises', '暂无内容')}

---

*本报告由数学错题分析系统自动生成*
"""
        
        # 生成StackEdit URL (带时间戳防止缓存)
        timestamp_tag = f"\n\n---\n*导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        markdown_with_timestamp = markdown_report + timestamp_tag
        encoded_content = base64.b64encode(markdown_with_timestamp.encode('utf-8')).decode('utf-8')
        stackedit_url = f"https://stackedit.io/app#providerId=base64&content={urllib.parse.quote(encoded_content)}"
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                label="📥 下载Markdown",
                data=markdown_report,
                file_name=f"错题分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True,
                help="下载到本地,手动导入StackEdit"
            )
        
        with col2:
            # 显示内容供复制
            if st.button("📋 显示内容", use_container_width=True, help="点击后在下方显示完整内容,可直接复制"):
                st.session_state['show_markdown_content'] = True
        
        with col3:
            st.link_button(
                label="🖨️ StackEdit",
                url=stackedit_url,
                use_container_width=True,
                type="secondary",
                help="⚠️ 可能缓存旧内容,建议用'下载'方式"
            )
        
        # 如果点击了显示内容
        if st.session_state.get('show_markdown_content', False):
            st.divider()
            st.markdown("### 📄 完整内容(可全选复制)")
            st.code(markdown_report, language="markdown")
            st.success("✅ 请按 Ctrl+A (Mac: Cmd+A) 全选,然后 Ctrl+C 复制,粘贴到 StackEdit 或其他编辑器")
            if st.button("❌ 关闭内容显示"):
                st.session_state['show_markdown_content'] = False
                st.rerun()
        
        # 添加使用说明
        with st.expander("📖 如何正确打印? (避免缓存)", expanded=False):
            st.markdown("""
            ### ✅ 推荐方法: 下载后导入
            1. 点击 **"📥 下载Markdown"** 
            2. 访问 https://stackedit.io/app
            3. 点击左上角菜单 **☰** → **Import from disk**
            4. 选择刚下载的.md文件
            5. 点击右上角 **🖨️ 打印图标**
            
            ### 📋 或者: 显示+复制
            1. 点击 **"📋 显示内容"**
            2. 全选复制内容 (Ctrl+A → Ctrl+C)
            3. 打开 StackEdit,新建文档
            4. 粘贴 (Ctrl+V)
            5. 打印
            
            ### ⚠️ 不推荐: 直接点"StackEdit"按钮
            - 浏览器可能缓存旧内容
            - 看到的可能不是最新版本
            """)

        
        st.stop()
    else:
        # 没有找到历史记录，显示图片并允许重新分析
        st.warning("⚠️ 未找到该图片的历史分析记录")
        st.subheader("📷 原题")
        st.image(image, use_column_width=True)
        
        st.info("💡 您可以直接点击下方\"开始分析\"按钮，对这张图片进行AI分析")
        
        # 重置去重检查状态，允许分析
        st.session_state.pop('duplicate_check_done', None)
        st.session_state.pop('duplicate_check', None)
        
        # 将图片数据保存到session_state，作为"已上传"的图片
        # 这样后面的分析逻辑就能直接使用
        st.session_state['reload_image_for_analysis'] = reload_img_data
        st.session_state['reload_image_object'] = image
        st.session_state['image_already_displayed'] = True  # 标记图片已显示

# 优先检查是否有正在分析/已分析的图片数据（rerun后恢复）
if 'current_image' in st.session_state and 'knowledge_analysis' in st.session_state:
    # 从session_state恢复图片数据
    image = st.session_state['current_image']
    uploaded_file = st.session_state.get('current_uploaded_file')
    draft_files = st.session_state.get('current_draft_files', [])
    uploaded_files = ['dummy']  # 标记有图片需要处理
# 检查是否有从历史记录reload但未找到分析的图片
elif 'reload_image_for_analysis' in st.session_state:
    # 使用reload的图片数据
    image = st.session_state['reload_image_object']
    uploaded_file = None
    draft_files = []
    
    # 不立即删除reload标记，保留到分析完成
    # （否则点击"开始分析"按钮后页面刷新会丢失图片数据）
    
    # 跳过文件上传器，直接进入分析流程
    uploaded_files = ['dummy']  # 标记有图片需要处理
else:
    uploaded_files = st.file_uploader(
        "📤 上传图片", 
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        help="第1张必须是错题本身，后续图片(最多3张)可以是草稿纸"
    )
    
    # 检测文件是否变化，如果变化则重置去重检查状态
    if uploaded_files:
        current_file_id = uploaded_files[0].file_id if hasattr(uploaded_files[0], 'file_id') else uploaded_files[0].name
        if 'last_file_id' not in st.session_state or st.session_state['last_file_id'] != current_file_id:
            # 文件已更换，重置去重检查状态
            st.session_state['last_file_id'] = current_file_id
            st.session_state.pop('duplicate_check_done', None)
            st.session_state.pop('duplicate_check', None)

if uploaded_files:
    # 如果是从reload来的，跳过上传文件处理
    if uploaded_files[0] != 'dummy':
        # 限制最多4张图片
        if len(uploaded_files) > 4:
            st.error("❌ 最多上传4张图片（1张错题+3张草稿）")
            st.stop()
        
        # 第1张是错题，后续是草稿
        uploaded_file = uploaded_files[0]
        draft_files = uploaded_files[1:] if len(uploaded_files) > 1 else []
        
        # 显示原图
        image = Image.open(uploaded_file)
        
        # 🔍 去重检查：检查这张图片是否已经分析过（只对真正上传的文件检查）
        if cos_client and 'duplicate_check_done' not in st.session_state:
            with st.spinner("🔍 正在检查是否为重复图片..."):
                # 将图片转换为字节
                img_byte_arr = BytesIO()
                image.save(img_byte_arr, format=image.format or 'PNG')
                img_byte_arr.seek(0)
                image_bytes = img_byte_arr.getvalue()
                
                # 检查是否重复
                duplicate_check = check_image_duplicate(image_bytes)
                st.session_state['duplicate_check'] = duplicate_check
                st.session_state['duplicate_check_done'] = True
    else:
        # 从reload来的图片，已经在前面显示过了，且已确认无历史记录
        # 这里不需要再做去重检查
        pass
    
    # 如果是重复图片，显示提示和历史记录
    if st.session_state.get('duplicate_check', {}).get('is_duplicate', False):
        dup_info = st.session_state['duplicate_check']
        
        # 格式化时间
        friendly_time = format_friendly_time(dup_info['upload_time'])
        
        st.warning("⚠️ **检测到重复图片！**")
        st.info(f"""
        📋 这道错题已经在 **{friendly_time}** 分析过了！
        
        为了避免浪费 AI 配额和产生重复数据，我们为您展示之前的分析结果。
        
        💡 如果需要重新分析，请先删除之前的记录，或使用不同的图片。
        """)
        
        # 显示之前的分析结果
        st.divider()
        st.subheader("📚 历史分析结果")
        
        record = dup_info['record']
        
        # 显示图片
        st.markdown("### 📷 原题")
        st.image(image, use_column_width=True)
        
        # 显示分析时间
        if 'timestamp' in record:
            st.caption(f"🕐 分析时间：{record['timestamp']}")
        
        st.divider()
        
        # 显示知识点分析
        if 'analysis' in record and 'knowledge_points' in record['analysis']:
            with st.expander("📚 知识点分析", expanded=True):
                st.markdown(record['analysis']['knowledge_points'])
        
        # 显示错因诊断
        if 'analysis' in record and 'error_diagnosis' in record['analysis']:
            with st.expander("🔍 错因诊断", expanded=True):
                st.markdown(record['analysis']['error_diagnosis'])
        
        # 显示延展练习
        if 'analysis' in record and 'exercises' in record['analysis']:
            with st.expander("💪 延展练习", expanded=True):
                st.markdown(record['analysis']['exercises'])
        
        st.divider()
        
        # 提供下载按钮
        st.markdown("### 📥 导出报告")
        
        # 生成Markdown报告
        markdown_report = f"""# 📊 数学错题分析报告

## 🕐 分析时间
{record.get('timestamp', '未记录')}

---

## 📚 知识点分析
{record['analysis'].get('knowledge_points', '暂无内容')}

---

## 🔍 错因诊断
{record['analysis'].get('error_diagnosis', '暂无内容')}

---

## 💪 延展练习
{record['analysis'].get('exercises', '暂无内容')}

---

*本报告由数学错题分析系统自动生成*
"""
        
        # 生成StackEdit URL
        encoded_content = base64.b64encode(markdown_report.encode('utf-8')).decode('utf-8')
        stackedit_url = f"https://stackedit.io/app#providerId=base64&content={urllib.parse.quote(encoded_content)}"
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📥 下载Markdown",
                data=markdown_report,
                file_name=f"错题分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True
            )
        
        with col2:
            st.link_button(
                label="🖨️ StackEdit打印",
                url=stackedit_url,
                use_container_width=True,
                type="primary",
                help="📱 手机端推荐! 一键在StackEdit中打开,完美支持数学公式打印"
            )
        
        # 阻止继续分析
        st.stop()
    
    # 如果不是重复图片，继续正常流程
    # 如果有草稿图，调整布局显示
    if draft_files:
        st.subheader("📷 上传的图片")
        cols = st.columns(min(4, len(uploaded_files)))
        
        # 显示错题（第1张）
        with cols[0]:
            st.markdown("**错题**")
            st.image(image, use_column_width=True)
            if uploaded_file:
                st.caption(f"📄 {uploaded_file.name}")
        
        # 显示草稿（后续图片）
        for idx, draft_file in enumerate(draft_files):
            with cols[idx + 1]:
                st.markdown(f"**草稿 {idx + 1}**")
                draft_image = Image.open(draft_file)
                st.image(draft_image, use_column_width=True)
                st.caption(f"📝 {draft_file.name}")
    else:
        # 只有错题，居中显示
        # 如果已经有分析结果(rerun后)，或者是第一次显示，都要显示图片
        # 只有在reload时首次显示过才跳过
        should_display = True
        if st.session_state.get('image_already_displayed', False) and 'knowledge_analysis' not in st.session_state:
            # reload时已显示过，且还没有分析结果，跳过显示
            should_display = False
            st.session_state.pop('image_already_displayed', None)
        
        if should_display:
            st.subheader("📷 原题")
            st.image(image, use_column_width=True)
    
    
    # 快速操作按钮（只在没有分析结果时显示）
    if 'knowledge_analysis' not in st.session_state:
        st.divider()
        st.subheader("🎯 快速操作")
        
        # 开始分析按钮（占据全宽）
        analysis_clicked = st.button("🚀 开始分析", type="primary", use_container_width=True)
    else:
        # 已有分析结果，不显示开始分析按钮
        analysis_clicked = False
    
    # 分析逻辑（在按钮外，占据全宽）
    if analysis_clicked:
        st.session_state['analysis_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存当前图片和文件信息到session_state，以便rerun后继续显示
        st.session_state['current_image'] = image
        st.session_state['current_uploaded_file'] = uploaded_file
        st.session_state['current_draft_files'] = draft_files
        
        # 现在可以清除reload标记了（因为已经保存到current_*中）
        st.session_state.pop('reload_image_for_analysis', None)
        st.session_state.pop('reload_image_object', None)
        st.session_state.pop('image_already_displayed', None)
        
        # 上传错题图片到 COS
        if cos_client:
            with st.spinner("📤 正在保存错题到云端..."):
                # 将图片转换为字节流
                img_byte_arr = BytesIO()
                image.save(img_byte_arr, format=image.format or 'PNG')
                img_byte_arr.seek(0)
                
                # 生成文件名（如果是reload的图片，使用时间戳生成）
                file_name = uploaded_file.name if uploaded_file else f"reload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                
                # 上传到 COS
                upload_result = upload_to_cos(img_byte_arr, file_name, file_type='image')
                if upload_result['success']:
                    st.success("✅ 错题已保存到云端")
                    st.session_state['cos_image_key'] = upload_result['key']
                else:
                    st.warning(f"⚠️ 云端保存失败: {upload_result['error']}")
        
        # 准备所有图片（错题+草稿）
        all_images = [image]
        if draft_files:
            for draft_file in draft_files:
                all_images.append(Image.open(draft_file))
        
        # 显示分析提示
        if len(all_images) > 1:
            st.info(f"📊 正在分析 {len(all_images)} 张图片（1张错题 + {len(draft_files)}张草稿）...")
        
        # 创建占位符
        status_placeholder = st.empty()
        knowledge_placeholder = st.empty()
        error_placeholder = st.empty()
        exercise_placeholder = st.empty()
        
        # 1. 知识点分析 - 流式输出
        status_placeholder.info("📚 正在分析知识点...")
        try:
            selected_model = st.session_state.get('selected_model', 'qwen')
            response_stream = analyze_knowledge_points(all_images, stream=True)
            
            knowledge_text = ""
            with knowledge_placeholder.container():
                st.markdown("### 📚 知识点分析")
                text_area = st.empty()
                
                # 检查返回类型 - 可能是字符串(非流式)或流对象
                if isinstance(response_stream, str):
                    # 非流式结果,直接显示
                    knowledge_text = response_stream
                    text_area.markdown(knowledge_text, unsafe_allow_html=True)
                else:
                    # 流式处理
                    if selected_model == 'qwen' or selected_model == 'qwen-max':
                        for chunk in stream_qwen_response(response_stream):
                            knowledge_text += chunk
                            # 使用code显示避免LaTeX渲染问题,最后才完整渲染
                            text_area.text(knowledge_text)
                    else:  # gemini
                        for chunk in stream_gemini_response(response_stream):
                            knowledge_text += chunk
                            text_area.text(knowledge_text)
                    
                    # 流式完成后,完整渲染markdown(包含LaTeX)
                    text_area.markdown(knowledge_text, unsafe_allow_html=True)
            
            st.session_state['knowledge_analysis'] = knowledge_text
            status_placeholder.success("✅ 知识点分析完成!")
        except Exception as e:
            knowledge_placeholder.error(f"❌ 知识点分析失败: {str(e)[:200]}")
            st.session_state['knowledge_analysis'] = f"分析失败: {str(e)}"
        
        # 2. 错因诊断 - 流式输出（带历史记忆）
        status_placeholder.info("🔍 正在诊断错误原因（检索历史记录...）")
        try:
            # 传入知识点分析结果，用于搜索相似历史错题
            response_stream = diagnose_error(all_images, knowledge_analysis=st.session_state['knowledge_analysis'], stream=True)
            
            error_text = ""
            with error_placeholder.container():
                st.markdown("### 🔍 错因诊断")
                text_area = st.empty()
                
                # 检查返回类型 - 可能是字符串(非流式)或流对象
                if isinstance(response_stream, str):
                    # 非流式结果,直接显示
                    error_text = response_stream
                    text_area.markdown(error_text, unsafe_allow_html=True)
                else:
                    # 流式处理
                    if selected_model == 'qwen' or selected_model == 'qwen-max':
                        for chunk in stream_qwen_response(response_stream):
                            error_text += chunk
                            text_area.text(error_text)
                    else:  # gemini
                        for chunk in stream_gemini_response(response_stream):
                            error_text += chunk
                            text_area.text(error_text)
                    
                    # 流式完成后,完整渲染markdown(包含LaTeX)
                    text_area.markdown(error_text, unsafe_allow_html=True)
            
            st.session_state['error_diagnosis'] = error_text
            status_placeholder.success("✅ 错因诊断完成!")
        except Exception as e:
            error_placeholder.error(f"❌ 错因诊断失败: {str(e)[:200]}")
            st.session_state['error_diagnosis'] = f"诊断失败: {str(e)}"
        
        # 3. 练习题生成 - 流式输出（可选，根据用户设置）
        if enable_exercises:
            status_placeholder.info("💪 正在生成延展练习...")
            try:
                response_stream = generate_similar_exercises(
                    all_images, 
                    st.session_state['knowledge_analysis'], 
                    exercise_count=1,  # 固定生成1题，提升效率
                    stream=True
                )
                
                exercise_text = ""
                with exercise_placeholder.container():
                    st.markdown("### 💪 延展练习")
                    text_area = st.empty()
                    
                    # 检查返回类型 - 可能是字符串(非流式)或流对象
                    if isinstance(response_stream, str):
                        # 非流式结果,直接显示
                        exercise_text = response_stream
                        text_area.markdown(exercise_text, unsafe_allow_html=True)
                    else:
                        # 流式处理
                        if selected_model == 'qwen' or selected_model == 'qwen-max':
                            for chunk in stream_qwen_response(response_stream):
                                exercise_text += chunk
                                text_area.text(exercise_text)
                        else:  # gemini
                            for chunk in stream_gemini_response(response_stream):
                                exercise_text += chunk
                                text_area.text(exercise_text)
                        
                        # 流式完成后,完整渲染markdown(包含LaTeX)
                        text_area.markdown(exercise_text, unsafe_allow_html=True)
                
                st.session_state['exercises'] = exercise_text
                status_placeholder.success("✅ 全部分析完成!")
            except Exception as e:
                error_msg = str(e).lower()
                if "timeout" in error_msg or "timed out" in error_msg:
                    exercise_placeholder.error("⚠️ **延展练习生成超时** - 内容较多需要较长时间，已增加超时限制。请刷新页面重试或在侧边栏关闭延展练习")
                    st.session_state['exercises'] = "生成超时，请重试"
                else:
                    exercise_placeholder.error(f"❌ 练习题生成失败: {str(e)[:300]}")
                    st.session_state['exercises'] = f"生成失败: {str(e)}"
        else:
            # 用户关闭了延展练习
            st.session_state['exercises'] = ""
            status_placeholder.success("✅ 分析完成!（已跳过延展练习）")
        
        # 4. 保存分析记录到 COS（用于后续记忆功能）
        if cos_client and st.session_state.get('cos_image_key'):
            status_placeholder.info("💾 正在保存分析记录...")
            try:
                # 使用之前保存的文件名（如果是reload的图片，使用生成的文件名）
                file_name = uploaded_file.name if uploaded_file else f"reload_{st.session_state.get('analysis_time', datetime.now().strftime('%Y%m%d_%H%M%S')).replace(':', '').replace(' ', '_').replace('-', '')}.png"
                
                save_result = save_analysis_record(
                    st.session_state['cos_image_key'],
                    file_name,
                    st.session_state.get('knowledge_analysis', ''),
                    st.session_state.get('error_diagnosis', ''),
                    st.session_state.get('exercises', '')
                )
                if save_result['success']:
                    status_placeholder.success("✅ 分析记录已保存！AI老师会记住这次错题！")
                else:
                    status_placeholder.warning(f"⚠️ 记录保存失败: {save_result['error']}")
            except Exception as e:
                status_placeholder.warning(f"⚠️ 记录保存失败: {str(e)}")
        
        st.rerun()
    
    # 显示分析结果
    if 'knowledge_analysis' in st.session_state:
        st.divider()
        
        # 根据是否生成延展练习决定标签页
        has_exercises = st.session_state.get('exercises', '') != ""
        
        if has_exercises:
            tab1, tab2, tab3, tab4 = st.tabs(["📚 知识点分析", "🔍 错因诊断", "💪 延展练习", "📄 完整报告"])
        else:
            tab1, tab2, tab4 = st.tabs(["📚 知识点分析", "🔍 错因诊断", "📄 完整报告"])
        
        with tab1:
            st.markdown(st.session_state['knowledge_analysis'], unsafe_allow_html=True)
        
        with tab2:
            st.markdown(st.session_state['error_diagnosis'], unsafe_allow_html=True)
        
        if has_exercises:
            with tab3:
                st.markdown(st.session_state['exercises'], unsafe_allow_html=True)
        
        with tab4:
            # 首先生成报告
            # 使用文件名（如果是reload的图片，使用默认名称）
            file_name_for_report = uploaded_file.name if uploaded_file else "错题"
            
            report = create_report(
                file_name_for_report,
                st.session_state['knowledge_analysis'],
                st.session_state['error_diagnosis'],
                st.session_state['exercises']
            )
            
            # 生成StackEdit URL
            encoded_content = base64.b64encode(report.encode('utf-8')).decode('utf-8')
            stackedit_url = f"https://stackedit.io/app#providerId=base64&content={urllib.parse.quote(encoded_content)}"
            
            # 下载按钮放在最上方，更容易看到
            st.subheader("📥 导出报告")
            st.info("💡 提示：Markdown格式适合数字存档，StackEdit适合在线打印(手机端推荐)")
            
            # 下载按钮
            col1, col2 = st.columns(2)
            
            with col1:
                # 生成下载文件名
                download_file_name = uploaded_file.name.split('.')[0] if uploaded_file else datetime.now().strftime('%Y%m%d_%H%M%S')
                
                st.download_button(
                    label="📥 下载Markdown",
                    data=report,
                    file_name=f"错题分析_{download_file_name}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    help="适合在支持Markdown的编辑器中查看"
                )
            
            with col2:
                st.link_button(
                    label="🖨️ StackEdit打印",
                    url=stackedit_url,
                    use_container_width=True,
                    type="primary",
                    help="📱 手机端推荐! 一键在StackEdit中打开,完美支持数学公式打印"
                )
            
            # 下载按钮后显示报告内容
            st.divider()
            st.markdown(report, unsafe_allow_html=True)

# 历史记录页面
if st.session_state.get('show_history', False):
    st.header("📚 错题历史记录")
    
    if st.button("⬅️ 返回主页"):
        st.session_state['show_history'] = False
        st.rerun()
    
    st.divider()
    
    if not cos_client:
        st.warning("⚠️ 未配置 COS 存储，无法查看历史记录")
    else:
        with st.spinner("📖 加载历史记录..."):
            history = list_history_from_cos(limit=50)
        
        if not history:
            st.info("📭 暂无历史记录")
        else:
            st.success(f"找到 {len(history)} 条历史记录")
            
            # 按时间分组显示
            for idx, item in enumerate(history):
                with st.expander(f"📝 {item['name']} - {item['time']}", expanded=(idx==0)):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # 下载并显示图片
                        img_data = download_from_cos(item['key'])
                        if img_data:
                            img = Image.open(BytesIO(img_data))
                            st.image(img, use_column_width=True)
                    
                    with col2:
                        st.markdown(f"**上传时间**: {item['time']}")
                        # 安全地显示文件大小，确保是数字类型
                        try:
                            size_kb = float(item['size']) / 1024
                            st.markdown(f"**文件大小**: {size_kb:.2f} KB")
                        except (TypeError, ValueError, ZeroDivisionError):
                            st.markdown(f"**文件大小**: 未知")
                        
                        if st.button("🔍 查看分析", key=f"reanalyze_{idx}", use_container_width=True):
                            # 保存图片数据，触发去重检查显示历史分析
                            st.session_state['reload_image'] = img_data
                            st.session_state['show_history'] = False
                            st.rerun()
                        
                        # 删除按钮
                        if st.button("🗑️ 删除", key=f"delete_{idx}", type="secondary", use_container_width=True):
                            # 保存待删除的记录索引到session_state
                            st.session_state[f'confirm_delete_{idx}'] = True
                            st.rerun()
                        
                        # 二次确认对话框
                        if st.session_state.get(f'confirm_delete_{idx}', False):
                            st.warning("⚠️ **确认删除？**")
                            st.markdown(f"即将删除错题: **{item['name']}**")
                            st.error("🚨 删除后无法恢复！图片和分析记录将从云端永久移除。")
                            
                            col_confirm, col_cancel = st.columns(2)
                            
                            with col_confirm:
                                if st.button("✅ 确认删除", key=f"confirm_{idx}", type="primary", use_container_width=True):
                                    with st.spinner("🗑️ 正在删除错题记录..."):
                                        result = delete_history_record(item['key'])
                                        if result['success']:
                                            deleted_count = len(result['deleted_files'])
                                            st.success(f"✅ 成功删除 {deleted_count} 个相关文件")
                                            
                                            # 分类显示删除的文件
                                            for file in result['deleted_files']:
                                                if 'images/' in file:
                                                    st.caption(f"🖼️ 图片: {file.split('/')[-1]}")
                                                elif 'records/' in file:
                                                    st.caption(f"📄 分析记录: {file.split('/')[-1]}")
                                                else:
                                                    st.caption(f"✓ {file}")
                                            
                                            st.info("💡 提示: 图片和对应的分析记录均已从云存储中移除")
                                            st.balloons()
                                            # 清除确认状态
                                            st.session_state.pop(f'confirm_delete_{idx}', None)
                                            # 延迟刷新，让用户看到成功消息
                                            import time
                                            time.sleep(2)
                                            st.rerun()
                                        else:
                                            st.error(f"❌ 删除失败: {result['error']}")
                                            if result['deleted_files']:
                                                st.warning(f"⚠️ 部分文件已删除（共{len(result['deleted_files'])}个），但未完全清理")
                                            # 清除确认状态
                                            st.session_state.pop(f'confirm_delete_{idx}', None)
                            
                            with col_cancel:
                                if st.button("❌ 取消", key=f"cancel_{idx}", use_container_width=True):
                                    # 清除确认状态
                                    st.session_state.pop(f'confirm_delete_{idx}', None)
                                    st.rerun()
    
    # 版本号显示（调试用）
    st.markdown("---")
    st.caption(f"🔧 版本: {APP_VERSION} | 构建日期: {APP_BUILD_DATE}")
    
    st.stop()

elif not uploaded_files:
    st.info("👆 请上传一张错题图片开始分析")
    
    # 显示示例
    st.markdown("### 📖 功能说明")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        #### 📚 知识点分析
        - 识别核心知识点
        - 定位教材章节
        - 评估难度等级
        - 考试场景分析
        """)
    
    with col2:
        st.markdown("""
        #### 🔍 错因诊断
        - 追踪解题思路
        - 定位出错步骤
        - 分析错误类型
        - 提供改进建议
        """)
    
    with col3:
        st.markdown("""
        #### 💪 延展练习
        - 匹配本地考试风格
        - 难度梯度设计
        - 针对性训练
        - 含答案和解析
        """)
    
    # 版本号显示（调试用）
    st.markdown("---")
    st.caption(f"🔧 版本: {APP_VERSION} | 构建日期: {APP_BUILD_DATE}")
