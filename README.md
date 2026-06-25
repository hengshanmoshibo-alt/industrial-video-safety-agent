# AiCoding 智能客服系统终极版

本项目是本机可完整运行的微服务版智能客服平台，采用 FastAPI 微服务、React 前端、PostgreSQL、Milvus、Redis 和 Docker Compose。

## 功能

- 网页访客客服聊天
- Milvus RAG 知识库问答与来源引用
- 中文电商客服种子知识库
- 转人工、坐席接管、人工回复
- 工单创建与流转
- 租户、组织、用户、角色、知识治理、模型治理、渠道配置、运营统计和审计日志
- OpenAI-compatible 大模型接口，未配置时使用本地知识库模板回复

## 服务清单

- `api-gateway`：统一 `/api` 入口。
- `auth-service`：租户、用户、角色、JWT。
- `conversation-service`：会话、消息、AI 回复、转人工、坐席接管。
- `ticket-service`：工单和流转记录。
- `knowledge-service`：知识文档、版本、审批、发布、Milvus 索引。
- `ai-orchestrator`：RAG、模型路由、提示词版本、模型调用日志。
- `channel-service`：网页渠道和企微/微信/飞书/钉钉模拟回调。
- `analytics-service`：运营指标、质检、系统健康。
- `worker`：异步任务入口预留。
- `frontend`：统一管理台、坐席台和治理中心。

## 本机启动

Docker：

```bash
docker compose up --build
```

访问：

- 前端：`http://localhost:5173`
- 网关：`http://localhost:8000`

默认管理员：

- 用户名：`admin`
- 密码：`Admin123!`

## 数据策略

默认导入自建中文电商客服种子知识库。公开数据集只作为测试、评估和问法扩展，不默认进入生产知识库。

详见 [docs/data-sources.md](docs/data-sources.md)。

## 终极版验收

启动完整环境后可运行：

```bash
python scripts/verify_ultimate.py
```

该脚本会验证管理员登录、种子知识库导入、Milvus + 关键词混合 RAG、投诉/转人工识别、满意度、质检任务、审计日志和系统健康。

## 文档

- [架构说明](docs/architecture.md)
- [部署说明](docs/deployment.md)
- [模型治理](docs/model-governance.md)
- [知识治理](docs/knowledge-governance.md)
- [API 摘要](docs/api.md)
