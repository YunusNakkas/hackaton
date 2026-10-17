"""Transformers runtime. Aynı kod MPS (Apple Silicon), CUDA ve CPU'da çalışır.

S0 notu: device_map="auto" bellek az görünürse katmanları diske taşıyıp MPS'te "meta device"
hatası veriyor; bu yüzden cihaz açıkça seçilir. Ayrıntı: docs/s0-spike.md
"""

import logging
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForMultimodalLM, AutoProcessor

log = logging.getLogger("model-service.transformers")


def pick_device() -> str:
    if forced := os.environ.get("PM_DEVICE"):
        return forced
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class TransformersAdapter:
    runtime = "transformers"
    supports_audio = True

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.device = pick_device()
        self.ready = False
        self._model = None
        self._processor = None

    def load(self) -> None:
        t0 = time.perf_counter()
        self._processor = AutoProcessor.from_pretrained(self.model_id)
        self._model = AutoModelForMultimodalLM.from_pretrained(self.model_id, dtype="auto", device_map=self.device)
        self._model.eval()
        log.info("model yüklendi %s %s %.1fs", self.model_id, self.device, time.perf_counter() - t0)

    def warmup(self) -> None:
        # Ses kodlayıcısı ayrı ısınıyor: yalnız metinle ısınınca ilk sesli tur ~28 sn sürdü.
        with tempfile.TemporaryDirectory() as tmp:
            silence = Path(tmp) / "silence.wav"
            with wave.open(str(silence), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16_000)
                w.writeframes(b"\x00\x00" * 16_000)
            content = [{"type": "text", "text": "Transcribe the following speech segment."},
                       {"type": "audio", "audio": str(silence)}]
            self.generate([{"role": "user", "content": content}], max_new_tokens=4, sampling=None)
        self.generate([{"role": "user", "content": "Merhaba"}], max_new_tokens=4, sampling=None)
        self.ready = True
        log.info("ısınma tamam")

    def _sync(self) -> None:
        if self.device == "mps":
            torch.mps.synchronize()
        elif self.device == "cuda":
            torch.cuda.synchronize()

    def generate(self, messages: list[dict[str, Any]], max_new_tokens: int,
                 sampling: dict[str, Any] | None) -> dict[str, Any]:
        inputs = self._processor.apply_chat_template(
            messages, tokenize=True, return_dict=True, return_tensors="pt",
            add_generation_prompt=True, enable_thinking=False,
        ).to(self._model.device)
        input_len = inputs["input_ids"].shape[-1]
        kwargs = {"do_sample": True, **sampling} if sampling else {"do_sample": False}
        t0 = time.perf_counter()
        with torch.inference_mode():
            out = self._model.generate(**inputs, max_new_tokens=max_new_tokens, **kwargs)
        self._sync()
        seconds = time.perf_counter() - t0
        text = self._processor.decode(out[0][input_len:], skip_special_tokens=True).strip()
        return {"text": text, "new_tokens": int(out.shape[-1] - input_len), "input_tokens": int(input_len),
                "seconds": round(seconds, 3)}
