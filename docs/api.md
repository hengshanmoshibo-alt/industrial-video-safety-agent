# API 摘要

基础地址：`http://localhost:8000/api`

## 认证

- `POST /auth/login`

## 访客聊天

- `POST /chat/sessions`
- `POST /chat/sessions/{id}/messages`
- `GET /chat/sessions/{id}/messages`
- `POST /chat/sessions/{id}/handoff`
- `POST /chat/sessions/{id}/satisfaction`

## 坐席工作台

- `GET /agent/conversations`
- `POST /agent/conversations/{id}/accept`
- `POST /agent/conversations/{id}/reply`
- `POST /agent/conversations/{id}/close`

## 工单

- `POST /tickets`
- `GET /tickets`
- `PATCH /tickets/{id}`
- `POST /tickets/{id}/comments`
- `GET /tickets/{id}/flow-logs`

## 知识库

- `POST /kb/documents`
- `POST /kb/documents/upload`
- `GET /kb/documents`
- `POST /kb/documents/{id}/reindex`
- `DELETE /kb/documents/{id}`
- `GET /kb/search`
- `POST /kb/seed/ecommerce`
- `POST /kb/import/open-dataset`
- `GET /kb/versions`
- `GET /kb/approvals`
- `POST /kb/approvals`
- `POST /kb/publish`

## 运营与审计

- `GET /analytics/overview`
- `GET /audit/logs`

## 终极版治理

- `GET /tenants`
- `POST /tenants`
- `GET /departments`
- `POST /departments`
- `GET /roles`
- `POST /roles`
- `GET /channels`
- `POST /channels`
- `POST /channels/{id}/simulate-webhook`
- `GET /models/providers`
- `POST /models/providers`
- `GET /models/routes`
- `POST /models/routes`
- `GET /prompts/versions`
- `POST /prompts/versions`
- `GET /model-call-logs`
- `GET /quality/rules`
- `POST /quality/rules`
- `GET /quality/reports`
- `POST /quality/reports/run`
- `GET /system/health`

## Worker

- `POST http://localhost:8010/tasks/reindex`
- `POST http://localhost:8010/tasks/evaluate`
