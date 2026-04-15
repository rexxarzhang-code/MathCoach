# 🚀 Release v1.2.3 (2026-04-15)

## 主要变更

### 🐛 关键 Bug 修复

**修复历史错题分析报错问题**

症状：在历史记录中点击"查看分析"，或重新分析错题时，出现以下错误：
```
分析失败: 'ChatCompletionChunk' object has no attribute 'text'
诊断失败: 'ChatCompletionChunk' object has no attribute 'text'
```

根本原因：v1.2.2 升级到 qwen-3.6-plus 后，代码中残留了多处旧的 Gemini 条件判断逻辑。由于 `qwen-3.6-plus` 不在旧的判断条件 `['qwen', 'qwen-max']` 中，流式响应会错误地走到 Gemini 处理分支，而 Gemini 的 chunk 对象不存在 `.text` 属性，导致报错。

修复内容：
1. 删除知识点分析、错因诊断流式处理中所有 Gemini 的 `else` 分支
2. 删除错误处理中的 Gemini 降级逻辑（内容审核失败时切换 Gemini）
3. 统一所有流式响应使用 `stream_qwen_response()`

### 🧹 彻底清理 Gemini 依赖

- 移除 `import google.generativeai as genai`
- 移除 `GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')`
- 更新错误提示文本，不再提及 Gemini

## 升级建议

本次为 Bug 修复版本，建议立即升级。升级后：
- 历史错题分析功能恢复正常
- 重新分析错题不再报错
- 项目依赖更简洁，无需 google-generativeai 库

## 已知问题

v1.2.2 之前分析保存的历史记录，如果分析结果包含错误信息，需要手动删除后重新分析。
