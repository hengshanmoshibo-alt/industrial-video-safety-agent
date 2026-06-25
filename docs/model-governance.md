# 模型治理

## 能力

- 模型供应商：`/api/models/providers`
- 模型路由：`/api/models/routes`
- 提示词版本：`/api/prompts/versions`
- 模型调用日志：`/api/model-call-logs`

## 默认行为

未配置真实模型时，AI Orchestrator 使用本地 mock LLM，保证系统可完整演示。

配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 后，RAG 回答自动调用 OpenAI-compatible `/chat/completions`。

## 日志

每次 AI 调用记录：

- 供应商
- 模型
- 提示词版本
- 输入摘要
- 输出摘要
- 响应耗时
- token 估算
- 成本字段
