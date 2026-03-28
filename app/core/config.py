from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/helpers_system"
    redis_url: str = "redis://localhost:6379"
    jwt_secret: str = "change-me"
    jwt_expire_hours: int = 24
    telegram_bot_token: str = ""
    super_admin_telegram_id: int | None = None
    sqlalchemy_echo: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
