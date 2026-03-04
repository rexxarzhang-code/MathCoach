# 千问模型集成完成! 🎉

## ✅ 已完成的更新

1. **支持双模型**: 千问 Qwen-VL-Max + Google Gemini
2. **优先使用千问**: 配额更充足,响应速度快
3. **UI模型切换**: 侧边栏可实时切换模型
4. **错误处理**: 完善的异常捕获和提示

## 🚀 配置步骤

### 1. 添加千问API Key

编辑 `.env` 文件,添加您的千问API Key:

```bash
# Gemini API Key (可选)
GEMINI_API_KEY=your_gemini_api_key_here

# 千问 API Key (推荐)
QWEN_API_KEY=your_qwen_api_key_here
```

### 2. 获取千问API Key

1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 登录后进入"API-KEY管理"
3. 创建新的API Key
4. 复制并粘贴到 `.env` 文件

### 3. 重启应用

刷新浏览器页面即可,Streamlit会自动重新加载配置。

## 📊 模型对比

| 特性 | 千问 Qwen-VL-Max | Gemini Flash |
|------|------------------|--------------|
| **视觉能力** | ⭐⭐⭐⭐⭐ 优秀 | ⭐⭐⭐⭐⭐ 优秀 |
| **中文理解** | ⭐⭐⭐⭐⭐ 专为中文优化 | ⭐⭐⭐⭐ 良好 |
| **免费配额** | 💰 更充足 | ⚠️ 有限(1500次/天) |
| **响应速度** | ⚡ 快 | ⚡ 快 |
| **数学能力** | ⭐⭐⭐⭐⭐ 强 | ⭐⭐⭐⭐⭐ 强 |

## 🎯 使用建议

- **推荐**: 优先使用千问,配额更充足
- **备用**: Gemini配额用完时可切换
- **测试**: 可在侧边栏实时切换对比效果

## 💡 特性说明

### 自动模型选择
- 如果配置了千问API Key,默认使用千问
- 如果只有Gemini API Key,自动使用Gemini
- 支持在侧边栏手动切换

### 错误提示
- 配额用完时显示友好提示
- API错误时显示具体错误信息
- 未配置API Key时提示用户配置

## 🔧 技术细节

**千问API调用**:
- 使用 OpenAI 兼容接口
- 模型: `qwen-vl-max-latest`
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`

**图片处理**:
- 自动转换为 base64 格式
- 通过 `image_url` 方式传递

## 📞 获取帮助

- 千问文档: https://help.aliyun.com/zh/model-studio/
- Gemini文档: https://ai.google.dev/

---
*更新时间: 2026-02-28*
