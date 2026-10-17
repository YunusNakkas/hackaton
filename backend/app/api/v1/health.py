from fastapi import APIRouter

from app.core.config import get_settings
from app.services.capabilities import model_status

router = APIRouter(tags=["system"])


@router.get("/health")
def get_health():
    settings = get_settings()
    status = model_status(settings)
    return {
        "status": "ok" if status.service != "down" else "degraded",
        "version": settings.version,
        "model_service": status.service,
        "audio_input": status.audio_input,
        # local TTS cihazda kalır; bulut sağlayıcı eklenince UI metnin dışarı gittiğini gösterecek.
        "tts_provider": None if settings.tts_provider == "none" else settings.tts_provider,
    }
