# 🎓 AI数学错题分析教练

> 基于AI大模型的智能数学错题分析系统，专为长沙地区初中学生打造

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## ✨ 功能特点

### 📸 智能图像识别
- 支持拍照上传错题图片
- 自动识别题目内容和学生解答过程
- 支持手写、打印等多种题目格式

### 📚 知识点分析
- **精准定位**：自动识别涉及的数学知识点
- **教材对应**：对应人教版教材章节
- **难度评估**：评估题目难度和考试定位
- **超纲检测**：自动检查是否超出当前学习范围

### 🔍 错因诊断
- **思路分析**：解析学生解题思路
- **错误定位**：精准指出错误步骤
- **类型归类**：归纳错误类型（概念理解、计算失误、逻辑跳跃等）
- **改进建议**：提供针对性改进建议

### 💪 延展练习
- **真题优先**：从长沙四大名校（雅礼、长郡、师大附中、一中）近3年真题中选择
- **难度梯度**：提供1-3道不同难度的练习题
- **精准检索**：提供题目搜索关键词，方便在作业帮/小猿搜题中查找原题
- **详细解答**：包含完整解题步骤和要点提示

### 📄 报告导出
- **PDF格式**：优化的数学符号显示，适合打印
- **Markdown格式**：便于数字存档和编辑
- **完整报告**：包含所有分析内容和练习题

## 🚀 快速开始

### 在线使用

直接访问：[MathCoach App](https://your-app-url.streamlit.app)

### 本地部署

1. **克隆项目**
```bash
git clone https://github.com/rexxarzhang-code/MathCoach.git
cd MathCoach
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置API密钥**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件，填入你的API密钥
# 支持千问(Qwen)和Gemini两种模型
```

4. **运行应用**
```bash
streamlit run app.py
```

5. **访问应用**

浏览器自动打开 `http://localhost:8501`

## 🔑 API密钥配置

### 千问API（推荐）

1. 访问[阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 开通千问VL模型服务
3. 获取API Key
4. 在`.env`文件中配置：
```env
QWEN_API_KEY=your_qwen_api_key_here
```

### Gemini API（备选）

1. 访问[Google AI Studio](https://makersuite.google.com/app/apikey)
2. 创建API Key
3. 在`.env`文件中配置：
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

## 📖 使用说明

### 1. 上传错题图片
- 点击"上传错题图片"按钮
- 支持JPG、PNG、JPEG格式
- 建议图片清晰，包含完整题目和解答

### 2. 配置学生信息
在侧边栏设置：
- **年级**：选择学生当前年级
- **学期**：上学期/下学期
- **教材版本**：人教版/北师大版等
- **目标学校**：雅礼/长郡/师大附中/一中等
- **延展练习数量**：1-3题

### 3. 分析错题
点击"开始分析"按钮，系统将自动：
1. 识别题目内容
2. 分析知识点和难度
3. 诊断错误原因
4. 生成延展练习

### 4. 查看结果
在不同标签页查看：
- **知识点分析**：了解题目考点和难度
- **错因诊断**：明确错误原因
- **延展练习**：获取相似练习题
- **完整报告**：下载PDF/Markdown格式报告

## 🎯 适用对象

- **学生**：长沙地区初中学生，尤其是目标四大名校的学生
- **家长**：希望了解孩子数学薄弱环节，进行针对性辅导
- **教师**：快速批改错题，生成个性化练习题

## 📊 技术栈

- **前端框架**：Streamlit
- **AI模型**：
  - 千问VL (Qwen-VL-Max) - 主力模型
  - Gemini Pro Vision - 备用模型
- **PDF生成**：ReportLab
- **图像处理**：Pillow
- **配置管理**：PyYAML

## 📁 项目结构

```
MathCoach/
├── app.py                      # 主应用文件
├── config.yaml                 # 配置文件（学生信息、教学大纲等）
├── requirements.txt            # Python依赖
├── .env.example               # 环境变量模板
├── .gitignore                 # Git忽略文件
├── README.md                  # 项目说明
└── [更新日志]
    ├── LaTeX公式修复.md
    ├── PDF数学符号显示优化.md
    ├── 真题链接功能更新.md
    └── 延展练习真题检索更新.md
```

## ⚙️ 配置说明

### config.yaml

```yaml
student:
  grade: "初中二年级"
  semester: "下学期"          # 上学期/下学期
  textbook: "人教版"
  location: "长沙市"
  target_school: "雅礼中学"   # 目标高中
  school_group: "四大名校"

analysis:
  exercise_count: 3           # 延展练习数量（1-3）
  difficulty_range:
    - "基础巩固"
    - "中等提升"
    - "拔高挑战"
  
  # 教学大纲（按学期）
  syllabus:
    八年级上学期:
      - "三角形"
      - "全等三角形"
      - "轴对称"
      - "整式的乘除"
      - "因式分解"
    
    八年级下学期:
      - "分式"
      - "二次根式"
      - "勾股定理"
      - "平行四边形"
      - "一次函数"
  
  # 禁用内容（超纲）
  forbidden:
    - "圆"
    - "相似"
    - "二次函数"
    - "三角函数"
```

## 🔄 更新日志

### v1.3.0 (2026-03-01)
- ✨ 优化PDF数学符号显示（根号、分数）
- 🐛 修复PDF生成时HTML解析错误
- 🎯 强化真题检索功能（限定近3年真题）
- 📝 改用搜索关键词替代易失效的URL链接

### v1.2.0 (2026-02-28)
- ✨ 新增PDF导出功能
- 🔧 优化LaTeX公式转换
- 🎯 延展练习数量精确控制

### v1.1.0
- ✨ 集成千问VL模型
- 🎯 新增目标学校功能
- 📚 优化教学大纲约束

### v1.0.0
- 🎉 初始版本发布

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📝 许可证

MIT License

## 👨‍💻 作者

Rexxar Zhang

## 🙏 致谢

- 阿里云百炼平台提供千问VL模型支持
- Google AI Studio提供Gemini模型支持
- Streamlit提供优秀的Web框架
- 长沙四大名校提供优质教学资源参考

---

**注意**：本项目仅供学习交流使用，请勿用于商业用途。题目来源请遵守相关版权规定。
