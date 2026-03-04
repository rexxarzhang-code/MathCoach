# 📁 项目结构说明

## 目录结构

```
MathCoach/
├── app.py                          # 主应用文件
├── config.yaml                     # 配置文件（学生信息、教学大纲）
├── requirements.txt                # Python依赖包列表
├── README.md                       # 项目主文档
├── DEPLOYMENT.md                   # 部署指南
│
├── .env.example                    # 环境变量模板
├── .gitignore                      # Git忽略规则
├── secrets.toml.example            # Streamlit Secrets模板
│
├── .streamlit/                     # Streamlit配置
│   └── config.toml                 # UI主题和服务器配置
│
├── docs/                           # 项目文档
│   ├── PROJECT_STRUCTURE.md        # 本文件
│   └── changelogs/                 # 开发日志
│       ├── PDF数学符号显示优化.md
│       ├── 真题链接功能更新.md
│       ├── 延展练习真题检索更新.md
│       ├── LaTeX公式修复.md
│       └── ...                     # 其他更新日志
│
└── venv/                           # 虚拟环境（不提交到Git）
```

## 核心文件说明

### `app.py`
主应用程序文件，包含：
- Streamlit UI界面
- 图像上传和处理
- AI模型调用（千问VL、Gemini）
- 知识点分析、错因诊断、延展练习生成
- PDF和Markdown导出功能
- LaTeX公式转换

**主要函数**：
- `call_vision_model()` - 调用AI视觉模型
- `analyze_knowledge_points()` - 分析知识点
- `diagnose_error()` - 诊断错误
- `generate_similar_exercises()` - 生成延展练习
- `convert_latex_to_text()` - LaTeX转文本
- `markdown_to_pdf()` - Markdown转PDF
- `create_report()` - 生成完整报告

### `config.yaml`
配置文件，包含：
- 学生信息（年级、教材、地区、目标学校）
- 延展练习设置（数量、难度梯度）
- 教学大纲（按学期划分）
- 禁用内容（超纲知识点）

**配置项**：
```yaml
student:
  grade: "初中二年级"
  semester: "下学期"
  textbook: "人教版"
  location: "长沙市"
  target_school: "雅礼中学"
  school_group: "四大名校"

analysis:
  exercise_count: 3
  difficulty_range:
    - "基础巩固"
    - "中等提升"
    - "拔高挑战"
  
  syllabus:
    八年级上学期: [...]
    八年级下学期: [...]
  
  forbidden: [...]
```

### `requirements.txt`
Python依赖包：
- `streamlit` - Web框架
- `google-generativeai` - Gemini模型
- `openai` - 千问模型（兼容OpenAI API）
- `python-dotenv` - 环境变量管理
- `Pillow` - 图像处理
- `PyYAML` - YAML配置解析
- `reportlab` - PDF生成
- `markdown` - Markdown解析

## 配置文件说明

### `.env` (本地开发)
环境变量配置，**不提交到Git**：
```env
QWEN_API_KEY=your_qwen_api_key
GEMINI_API_KEY=your_gemini_api_key
```

### `.streamlit/secrets.toml` (云端部署)
Streamlit Cloud密钥配置，**不提交到Git**：
```toml
QWEN_API_KEY = "your_qwen_api_key"
GEMINI_API_KEY = "your_gemini_api_key"
```

### `.streamlit/config.toml`
Streamlit UI配置：
- 主题颜色
- 字体设置
- 服务器端口
- 使用统计开关

## 文档目录说明

### `docs/changelogs/`
开发日志和更新记录：
- **PDF数学符号显示优化.md** - 根号、分数显示优化
- **真题链接功能更新.md** - 真题检索方式更新
- **延展练习真题检索更新.md** - 真题来源约束
- **LaTeX公式修复.md** - LaTeX转换问题修复
- **PDF编码问题修复.md** - PDF生成错误修复
- 其他功能更新日志...

## 数据流程

```
用户上传图片
    ↓
Streamlit接收并显示
    ↓
调用AI模型（千问VL/Gemini）
    ↓
生成分析结果
    ├── 知识点分析
    ├── 错因诊断
    └── 延展练习
    ↓
显示在Web界面
    ↓
用户下载报告
    ├── PDF格式（优化数学符号）
    └── Markdown格式（原始内容）
```

## 开发流程

### 本地开发
1. 克隆项目
2. 创建虚拟环境：`python -m venv venv`
3. 激活虚拟环境：`source venv/bin/activate`
4. 安装依赖：`pip install -r requirements.txt`
5. 配置`.env`文件
6. 运行：`streamlit run app.py`
7. 测试功能
8. 提交代码

### 云端部署
1. 推送到GitHub
2. 登录Streamlit Cloud
3. 创建新App
4. 配置Secrets
5. 部署并测试

## 测试说明

### 功能测试
- [x] 图片上传（JPG/PNG/JPEG）
- [x] 知识点分析准确性
- [x] 错因诊断完整性
- [x] 延展练习质量
- [x] PDF导出（数学符号显示）
- [x] Markdown导出
- [x] 模型切换（千问/Gemini）
- [x] 配置修改（年级/学期/目标学校）

### 性能测试
- [x] 图片上传速度
- [x] AI响应时间
- [x] PDF生成速度
- [x] 页面加载速度

## 维护说明

### 定期维护
- 更新教学大纲（每学期）
- 更新真题来源（每年）
- 更新Python依赖（每月）
- 检查API密钥有效性

### 问题排查
- 查看Streamlit日志
- 检查API调用次数
- 监控错误率
- 收集用户反馈

## 扩展方向

### 功能扩展
- [ ] 支持更多年级
- [ ] 支持更多科目
- [ ] 添加错题本功能
- [ ] 添加学习进度跟踪
- [ ] 支持批量分析

### 技术优化
- [ ] 缓存AI响应结果
- [ ] 优化PDF生成速度
- [ ] 支持更多数学符号
- [ ] 改进图像识别准确性
- [ ] 添加单元测试

### 部署优化
- [ ] Docker容器化
- [ ] 自定义域名
- [ ] CDN加速
- [ ] 负载均衡
- [ ] 监控告警

---

最后更新：2026-03-01
