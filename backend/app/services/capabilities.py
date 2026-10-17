"""Model servisinin durumu ve yetenekleri (ses girişi var mı). /health ve ses yükleme bunu kullanır.

Model servisi her istekte sorgulanmasın diye sonuç kısa süre önbellekte tutulur.
"""

import time
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import Settings

CACHE_S = 10.0
AUDIO_UNSUPPORTED_MSG = "Bu kurulumda sesli cevap desteklenmiyor. Cevabını yazarak gönderebilirsin."


@dataclass(frozen=True)
class ModelStatus:
    service: Literal["up", "down", "stub"]
    audio_input: bool


_cache: tuple[float, str, ModelStatus] | None = None


def model_status(settings: Settings) -> ModelStatus:
    global _cache
    if settings.model_mode == "stub":
        return ModelStatus("stub", True)  # stub ASR her kurulumda çalışır
    now = time.monotonic()
    if _cache and _cache[1] == settings.model_service_url and now - _cache[0] < CACHE_S:
        return _cache[2]
    try:
        res = httpx.get(f"{settings.model_service_url}/v1/health", timeout=2)
        if res.status_code == 200:
            # Alan yoksa (eski servis) güvenli taraf: ses yok varsayılır.
            status = ModelStatus("up", bool(res.json().get("audio_input", False)))
        else:
            status = ModelStatus("down", False)
    except (httpx.HTTPError, ValueError):
        status = ModelStatus("down", False)
    _cache = (now, settings.model_service_url, status)
    return status


def clear_cache() -> None:
    global _cache
    _cache = None
