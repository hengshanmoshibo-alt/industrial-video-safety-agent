from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "aicoding-service"
    environment: str = "local"
    secret_key: str = "please-change-this-secret"
    database_url: str = "postgresql+psycopg://aicoding:aicoding@postgres:5432/aicoding"
    redis_url: str = "redis://redis:6379/0"
    milvus_host: str = "milvus"
    milvus_port: str = "19530"
    milvus_collection: str = "aicoding_knowledge_chunks"
    default_tenant_slug: str = "default"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    auth_service_url: str = "http://auth-service:8000"
    conversation_service_url: str = "http://conversation-service:8000"
    ticket_service_url: str = "http://ticket-service:8000"
    knowledge_service_url: str = "http://knowledge-service:8000"
    ai_orchestrator_url: str = "http://ai-orchestrator:8000"
    channel_service_url: str = "http://channel-service:8000"
    analytics_service_url: str = "http://analytics-service:8000"
    video_audit_service_url: str = "http://video-audit-service:8000"
    worker_url: str = "http://worker:8000"

    storage_backend: str = "local"
    storage_local_root: str = "/app/data/storage"
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "video-audits"

    video_audit_queue: str = "video-audit-tasks"
    video_audit_frame_interval_seconds: float = 2.0
    video_audit_window_seconds: float = 4.0
    video_audit_confidence_threshold: float = 0.45
    video_audit_model_path: str = "/app/models/safety_r3d18.pt"
    video_audit_device: str = "auto"

    vision_enabled: bool = True
    vision_base_url: str = ""
    vision_api_key: str = ""
    vision_model: str = ""
    vision_frame_batch_size: int = 4
    vision_max_frames: int = 24
    vision_timeout_seconds: int = 60

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    feishu_alert_enabled: bool = False
    feishu_webhook_url: str = ""
    feishu_webhook_secret: str = ""
    feishu_alert_risk_levels: str = "high,critical,needs_review"
    feishu_alert_timeout_seconds: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
