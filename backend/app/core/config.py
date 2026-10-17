from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PM_", env_file=("../.env", ".env"), extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./var/provamusteri.sqlite3"
    media_dir: Path = Path("./var/media")
    cors_origins: list[str] = ["http://localhost:5173"]
    cookie_secure: bool = False  # prod'da HTTPS arkasında true
    max_audio_bytes: int = 10 * 1024 * 1024
    max_audio_seconds: int = 30  # Gemma 4 ses girişi en fazla 30 sn
    min_audio_ms: int = 500

    # stub: süreç içi sahte model (GPU'suz geliştirme/CI). real: model-service'e HTTP.
    model_mode: Literal["stub", "real"] = "real"
    model_service_url: str = "http://localhost:8100"
    model_timeout_s: float = 180.0
    eval_temperature: float = 1.0  # resmî öneri; S0'da ±1 sapma görüldü, ayarlanacak

    # local: macOS `say` (yalnız macOS host). none: müşteri sesi üretilmez.
    tts_provider: Literal["local", "none"] = "none"
    tts_voice: str = "Yelda"

    worker_poll_s: float = 0.3


@lru_cache
def get_settings() -> Settings:
    return Settings()
