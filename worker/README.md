# Worker

当前版本的异步任务入口预留在 `worker/`。知识库导入和重新索引已通过后端同步接口实现，后续可把大文件解析、Embedding 和公开数据转换迁移到 RQ/Celery worker。
