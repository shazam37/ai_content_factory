from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://content_factory:content_factory@db:5432/content_factory"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_quality_model: str = "qwen2.5:7b"

    # Storage
    storage_base_path: str = "./storage"

    # Video settings
    default_video_width: int = 1080
    default_video_height: int = 1920
    default_video_fps: int = 30
    default_niche: str = "science"

    # Voice
    voice_default: str = "en-US-GuyNeural"
    voice_female: str = "en-US-JennyNeural"

    # Image provider
    image_provider: str = "ffmpeg_slides"
    pexels_api_key: str = ""

    # Reddit (optional)
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ContentFactory/1.0"

    # API security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440

    environment: str = "development"
    log_level: str = "INFO"

    @field_validator("image_provider")
    @classmethod
    def validate_image_provider(cls, v: str) -> str:
        allowed = {"ffmpeg_slides", "pexels"}
        if v not in allowed:
            raise ValueError(f"image_provider must be one of {allowed}")
        return v

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def storage_audio(self) -> str:
        return f"{self.storage_base_path}/audio"

    @property
    def storage_images(self) -> str:
        return f"{self.storage_base_path}/images"

    @property
    def storage_videos(self) -> str:
        return f"{self.storage_base_path}/videos"

    @property
    def storage_thumbnails(self) -> str:
        return f"{self.storage_base_path}/thumbnails"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
