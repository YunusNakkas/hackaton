import httpx
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def get_health():
    settings = get_settings()
    if settings.model_mode == "stub":
        model_service = "stub"
    else:
        try:
            ok = httpx.get(f"{settings.model_service_url}/v1/health", timeout=2).status_code == 200
        except httpx.HTTPError:
            ok = False
        model_service = "up" if ok else "down"
    return {
        "status": "ok" if model_service != "down" else "degraded",
        "version": settings.version,
        "model_service": model_service,
        # local TTS cihazda kalır; bulut sağlayıcı eklenince UI metnin dışarı gittiğini gösterecek.
        "tts_provider": None if settings.tts_provider == "none" else settings.tts_provider,
    }
