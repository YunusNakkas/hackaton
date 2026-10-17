from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PM_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./var/provamusteri.sqlite3"
    media_dir: str = "./var/media"
    session_secret: str = "change-me"
    cors_origins: list[str] = ["http://localhost:5173"]
    max_audio_bytes: int = 10 * 1024 * 1024
    max_audio_seconds: int = 30  # Gemma 4 ses girişi en fazla 30 sn

    model_service_url: str = "http://localhost:8100"
    model_mode: Literal["stub", "real"] = "stub"
    tts_provider: Literal["elevenlabs", "local", "none"] = "none"


@lru_cache
def get_settings() -> Settings:
    return Settings()
