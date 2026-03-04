# 🚀 Streamlit Cloud 部署指南

## 📋 准备工作清单

在推送到GitHub和部署到Streamlit Cloud之前，请确认以下事项：

### ✅ 必需文件
- [x] `app.py` - 主应用文件
- [x] `config.yaml` - 配置文件
- [x] `requirements.txt` - Python依赖
- [x] `.env.example` - 环境变量模板
- [x] `.gitignore` - 忽略敏感文件
- [x] `README.md` - 项目说明
- [x] `.streamlit/config.toml` - Streamlit配置

### ✅ 敏感信息检查
- [x] `.env` 文件已在 `.gitignore` 中
- [x] `venv/` 虚拟环境已在 `.gitignore` 中
- [x] API密钥不在代码中硬编码

## 🔐 API密钥准备

### 方式1：千问API（推荐）
1. 登录[阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 进入"模型服务" -> "千问VL"
3. 开通服务并获取API Key
4. 记录下API Key，待部署时使用

### 方式2：Gemini API（备选）
1. 访问[Google AI Studio](https://makersuite.google.com/app/apikey)
2. 创建新的API Key
3. 记录下API Key，待部署时使用

## 📤 推送到GitHub

### 1. 初始化Git仓库（如果还没有）
```bash
cd /Users/rexxarzhang/CodeBuddy/coach
git init
```

### 2. 添加远程仓库
```bash
git remote add origin https://github.com/rexxarzhang-code/MathCoach.git
```

### 3. 添加所有文件
```bash
git add .
```

### 4. 提交更改
```bash
git commit -m "Initial commit: AI Math Coach with PDF export and optimized display"
```

### 5. 推送到GitHub
```bash
git push -u origin main
```

如果分支是master而不是main：
```bash
git push -u origin master
```

## ☁️ 部署到Streamlit Cloud

### 1. 登录Streamlit Cloud
访问：https://share.streamlit.io/

使用GitHub账号登录

### 2. 新建App
1. 点击 **"New app"** 按钮
2. 选择你的仓库：`rexxarzhang-code/MathCoach`
3. 选择分支：`main`（或`master`）
4. 主文件路径：`app.py`
5. App URL（自定义）：`mathcoach` 或其他名称

### 3. 配置Secrets（重要！）
在部署之前，必须配置API密钥：

1. 点击 **"Advanced settings"**
2. 在 **"Secrets"** 部分，添加以下内容：

```toml
# 千问API密钥（推荐）
QWEN_API_KEY = "你的千问API密钥"

# 或者 Gemini API密钥（备选）
GEMINI_API_KEY = "你的Gemini API密钥"
```

**注意**：
- Secrets格式为TOML，不是JSON
- 字符串需要用引号包裹
- 至少配置一个API密钥

### 4. 部署App
点击 **"Deploy"** 按钮

Streamlit Cloud会自动：
1. 克隆你的GitHub仓库
2. 安装`requirements.txt`中的依赖
3. 运行`app.py`
4. 分配一个公开URL

### 5. 等待部署完成
首次部署约需要3-5分钟：
- ✅ 绿色勾：部署成功
- ❌ 红色叉：部署失败（查看日志）

## 🔧 部署后配置

### 更新README中的App链接
1. 复制Streamlit Cloud分配的URL（如：`https://mathcoach.streamlit.app`）
2. 更新`README.md`中的徽章链接：
```markdown
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://mathcoach.streamlit.app)
```
3. 提交并推送更新：
```bash
git add README.md
git commit -m "Update app URL in README"
git push
```

### 设置自定义域名（可选）
1. 在Streamlit Cloud的App设置中
2. 进入"Settings" -> "General"
3. 在"Custom domain"中添加你的域名
4. 按照提示配置DNS记录

## 🐛 常见问题排查

### 问题1：部署失败 - 依赖安装错误
**解决方案**：
1. 检查`requirements.txt`格式是否正确
2. 确保所有包名拼写正确
3. 尝试指定具体版本号

### 问题2：运行时错误 - API密钥未配置
**解决方案**：
1. 检查Secrets是否正确配置
2. 确认TOML格式正确（字符串要加引号）
3. 重启App使Secrets生效

### 问题3：运行时错误 - 模块导入失败
**解决方案**：
1. 确认`requirements.txt`包含所有需要的包
2. 检查包名是否正确（如`Pillow`不是`PIL`）
3. 查看部署日志，确认安装过程

### 问题4：App加载慢
**解决方案**：
1. 检查是否有大文件（如venv）被上传
2. 确认`.gitignore`正确配置
3. 优化代码，减少启动时的计算

### 问题5：中文显示乱码
**解决方案**：
1. 确认文件编码为UTF-8
2. 检查`config.toml`中的字体设置
3. 使用支持中文的字体

## 🔄 更新已部署的App

### 方式1：自动部署（推荐）
Streamlit Cloud默认开启自动部署：
1. 本地修改代码
2. 提交并推送到GitHub：
```bash
git add .
git commit -m "Update: 描述你的更改"
git push
```
3. Streamlit Cloud自动检测并重新部署

### 方式2：手动重启
1. 登录Streamlit Cloud
2. 找到你的App
3. 点击右上角 "⋮" -> "Reboot app"

## 📊 监控和日志

### 查看应用日志
1. 在Streamlit Cloud的App页面
2. 点击右下角的 "Manage app"
3. 查看 "Logs" 标签
4. 实时监控应用运行状态

### 查看使用统计
1. 在App设置中查看访问量
2. 监控资源使用情况
3. 检查API调用次数

## 💡 最佳实践

### 1. 分支管理
- `main/master`：生产环境
- `dev`：开发测试
- 使用不同分支部署不同版本

### 2. 环境变量
- 本地使用`.env`文件
- 云端使用Streamlit Secrets
- 永远不要硬编码API密钥

### 3. 性能优化
- 使用`@st.cache_data`缓存数据
- 使用`@st.cache_resource`缓存模型
- 避免重复的API调用

### 4. 安全性
- 定期轮换API密钥
- 监控API使用量，防止滥用
- 设置访问控制（如果需要）

## 📝 部署检查清单

推送前最后确认：
- [ ] 所有敏感信息已从代码中移除
- [ ] `.gitignore`正确配置
- [ ] `requirements.txt`包含所有依赖
- [ ] `README.md`内容完整准确
- [ ] API密钥已准备好
- [ ] 代码已在本地测试通过

部署时确认：
- [ ] 仓库和分支选择正确
- [ ] 主文件路径为`app.py`
- [ ] Secrets正确配置
- [ ] 部署成功，App可访问
- [ ] 功能测试通过

## 🎉 部署成功后

1. **测试所有功能**：
   - 上传图片
   - 分析错题
   - 生成延展练习
   - 下载PDF和Markdown

2. **分享给用户**：
   - 复制App URL
   - 发送给目标用户
   - 收集反馈

3. **持续改进**：
   - 监控错误日志
   - 根据反馈优化
   - 定期更新功能

---

## 🆘 需要帮助？

- Streamlit文档：https://docs.streamlit.io/
- Streamlit社区：https://discuss.streamlit.io/
- GitHub Issues：https://github.com/rexxarzhang-code/MathCoach/issues

祝部署顺利！🚀
