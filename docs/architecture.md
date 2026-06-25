# 终极版架构说明

## 架构

系统采用本机 Docker Compose 可运行的微服务架构：

- API Gateway 统一接收前端 `/api` 请求并转发到内部服务。
- Auth Service 管理租户、组织、用户、角色和 JWT。
- Conversation Service 管理会话、消息、转人工和坐席接管。
- Knowledge Service 管理知识库、版本、审批、发布和 Milvus 向量索引。
- AI Orchestrator 执行 RAG、模型路由、提示词版本和模型调用日志。
- Ticket Service 管理工单和流转记录。
- Channel Service 管理渠道与模拟 webhook。
- Analytics Service 管理运营指标、质检规则和系统健康。
- Worker 预留异步任务入口。

## 数据

- PostgreSQL：租户、用户、会话、消息、工单、知识文档、治理配置和审计数据。
- Milvus：知识切片向量。
- Redis：缓存、限流和任务状态预留。

## 默认策略

- 默认租户：`default`。
- 默认账号：`admin / Admin123!`。
- 默认知识库：中文电商客服种子知识库。
- 默认模型：本地 mock LLM；配置 OpenAI-compatible 环境变量后切换真实模型。
