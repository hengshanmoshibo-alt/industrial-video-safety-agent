from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AiCoding Smart Customer Service"
    environment: str = "local"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 720
    database_url: str = "sqlite:///./aicoding.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
