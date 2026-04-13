from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/helpers_system"
    redis_url: str = "redis://localhost:6379"
    jwt_secret: str = "change-me"
    jwt_expire_hours: int = 24
    bot_token_encryption_key: str = Field(
        default="",
        validation_alias=AliasChoices("BOT_TOKEN_ENCRYPTION_KEY"),
    )
    telegram_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "BOT_TOKEN"),
    )
    telegram_mini_app_url: str = Field(
        default="https://t.me/YourBot/App",
        validation_alias=AliasChoices("TELEGRAM_MINI_APP_URL", "MINI_APP_URL"),
    )
    super_admin_telegram_id: int | None = None
    sqlalchemy_echo: bool = False
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
