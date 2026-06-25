# 知识治理

## 能力

- 知识文档：`/api/kb/documents`
- 版本列表：`/api/kb/versions`
- 审批列表：`/api/kb/approvals`
- 发布接口：`/api/kb/publish`
- 重建索引：`/api/kb/documents/{id}/reindex`

## 流程

1. 管理员或知识库管理员创建文档。
2. 文档默认进入草稿状态。
3. 审批通过后可发布。
4. 发布时切片并写入 Milvus。
5. AI Orchestrator 通过 Knowledge Service 检索已索引切片。

## 数据策略

默认种子知识库是项目自建中文电商客服知识。外部公开数据只用于测试、评估和问法扩展，不默认作为生产知识库。
## Hybrid RAG

- `/api/kb/search` returns a backward-compatible source list by default.
- `/api/kb/search?include_trace=true` returns `sources`, `confidence`, and `retrieval_trace`.
- Retrieval flow: deterministic embedding -> Milvus vector recall + PostgreSQL keyword recall -> merge/deduplicate -> weighted rerank.
- `/api/kb/seed/ecommerce` reindexes existing seed documents into Milvus, so an existing local Docker volume remains verifiable.
