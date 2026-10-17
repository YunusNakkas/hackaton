from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    model_service: Literal["up", "down", "stub"]
    tts_provider: str | None = None


@router.get("/health", response_model=Health)
def get_health() -> Health:
    settings = get_settings()
    # TODO: real modda model servisine ping atıp up/down belirle.
    return Health(
        status="ok",
        version=settings.version,
        model_service="stub" if settings.model_mode == "stub" else "up",
        tts_provider=None if settings.tts_provider == "none" else settings.tts_provider,
    )
