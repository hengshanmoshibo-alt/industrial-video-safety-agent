# 部署说明

## 本机启动

```bash
docker compose up --build
```

启动后访问：

- 前端：`http://localhost:5173`
- API Gateway：`http://localhost:8000`
- Milvus：`localhost:19531`，metrics/HTTP：`localhost:9092`
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

## 环境变量

复制并调整 `.env.example`：

```bash
copy .env.example .env
```

关键变量：

- `SECRET_KEY`：JWT 签名密钥，生产必须更换。
- `DATABASE_URL`：PostgreSQL 连接。
- `MILVUS_HOST` / `MILVUS_PORT`：Milvus 地址。
- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`：OpenAI-compatible 模型配置。

## 验收

- `docker compose config --quiet` 应通过。
- `GET http://localhost:8000/health` 返回 `ok`。
- 登录前端后，运营看板、网页客服、知识库、工单、终极治理页面可访问。
- 运行 `python scripts/verify_ultimate.py` 应返回 `status: passed`，并验证 RAG、Milvus、质检、审计和核心依赖健康。
