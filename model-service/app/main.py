"""Gemma model servisi. Ağırlıklar bir kez yüklenir; aynı anda tek üretim yapılır.

Çalıştırma (model-service/ içinden):
  PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/uvicorn app.main:app --port 8100

Sözleşme: contracts/model-service.yaml
"""

import base64
import binascii
import logging
import os
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.priority_lock import PriorityLock
from app.text_cleanup import strip_thinking

log = logging.getLogger("model-service")
RUNTIME = os.environ.get("PM_RUNTIME", "transformers")  # transformers | mlx
MODEL_ID = os.environ.get("PM_MODEL_ID", "google/gemma-4-E2B-it")
MAX_AUDIO_B64 = 4 * 1024 * 1024  # ~30 sn 16 kHz WAV ≈ 1 MB

adapter = None
slot = PriorityLock()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global adapter
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if RUNTIME == "mlx":  # ağır bağımlılıklar yalnız seçilen runtime için import edilir
        from app.adapters.mlx_adapter import MlxAdapter
        adapter = MlxAdapter(MODEL_ID)
    else:
        from app.adapters.transformers_adapter import TransformersAdapter
        adapter = TransformersAdapter(MODEL_ID)
    adapter.load()
    adapter.warmup()  # ilk çağrı ~18 sn sürüyor (S0); kullanıcı beklemesin
    yield


app = FastAPI(title="ProvaMüşteri model servisi", lifespan=lifespan)


class TextPart(BaseModel):
    type: Literal["text"]
    text: str


class AudioPart(BaseModel):
    type: Literal["audio"]
    audio_b64: str = Field(max_length=MAX_AUDIO_B64)


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[TextPart | AudioPart]


class Sampling(BaseModel):
    temperature: float = Field(1.0, ge=0, le=2)
    top_p: float = Field(0.95, gt=0, le=1)
    top_k: int = Field(64, ge=1)


class GenerateRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    max_new_tokens: int = Field(256, ge=1, le=2048)
    sampling: Sampling | None = None  # None: greedy (ASR için)
    priority: int = Field(10, ge=0, le=100)  # küçük olan önce


@app.get("/v1/health")
def health():
    if adapter is None or not adapter.ready:
        raise HTTPException(503, "model yükleniyor")
    return {"status": "ok", "model": adapter.model_id, "runtime": adapter.runtime, "device": adapter.device}


@app.post("/v1/generate")
def generate(req: GenerateRequest):
    if adapter is None or not adapter.ready:
        raise HTTPException(503, "model yükleniyor")
    with tempfile.TemporaryDirectory() as tmp:
        messages = []
        for i, m in enumerate(req.messages):
            if isinstance(m.content, str):
                messages.append({"role": m.role, "content": m.content})
                continue
            parts = []
            for j, p in enumerate(m.content):
                if p.type == "text":
                    parts.append({"type": "text", "text": p.text})
                else:
                    try:
                        raw = base64.b64decode(p.audio_b64, validate=True)
                    except binascii.Error as exc:
                        raise HTTPException(422, "audio_b64 geçersiz") from exc
                    path = Path(tmp) / f"{i}_{j}.wav"
                    path.write_bytes(raw)
                    parts.append({"type": "audio", "audio": str(path)})
            messages.append({"role": m.role, "content": parts})

        waited = time.perf_counter()
        with slot.acquire(req.priority):
            queue_s = time.perf_counter() - waited
            out = adapter.generate(messages, req.max_new_tokens, req.sampling.model_dump() if req.sampling else None)
    out["text"] = strip_thinking(out["text"])
    log.info("üretim p=%d kuyruk=%.2fs süre=%.2fs token=%d", req.priority, queue_s, out["seconds"], out["new_tokens"])
    return {**out, "queue_seconds": round(queue_s, 3), "model": adapter.model_id, "runtime": adapter.runtime}
