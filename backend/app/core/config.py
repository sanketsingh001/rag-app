# app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Broker / cache
    redis_url: str = "redis://redis:6379/0"

    # Placeholder URLs for later services
    qdrant_url: str = "http://qdrant:6333"
    minio_endpoint: str = "http://minio:9000"

    # External APIs & auth
    gemini_api_key: str | None = None
    jwt_secret: str = "supersecretjwtkey"

    class Config:
        env_file = ".env"        # Pydantic will read variables from .env


@lru_cache
def get_settings() -> Settings:
    """Singleton Settings object — import from anywhere."""
    return Settings()
