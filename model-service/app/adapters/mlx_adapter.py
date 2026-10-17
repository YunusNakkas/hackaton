"""MLX runtime (yalnız Apple Silicon). 4-bit modellerle 16 GB Mac'te swap'siz çalışmak için.

Transformers adapter'ı ile aynı arayüz: load(), warmup(), generate(). Mesajdaki ses parçaları
dosya yolu olarak gelir; sıraları korunarak mlx_vlm.generate'e verilir.
"""

import logging
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import mlx.core as mx
from mlx_vlm import generate as mlx_generate
from mlx_vlm import load as mlx_load

log = logging.getLogger("model-service.mlx")


class MlxAdapter:
    runtime = "mlx"
    supports_audio = True
    device = "mps"

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.ready = False
        self._model = None
        self._processor = None

    def load(self) -> None:
        t0 = time.perf_counter()
        self._model, self._processor = mlx_load(self.model_id)
        log.info("model yüklendi %s %.1fs aktif bellek=%.2f GB", self.model_id, time.perf_counter() - t0,
                 mx.get_active_memory() / 1e9)

    def warmup(self) -> None:
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
        log.info("ısınma tamam, tepe bellek=%.2f GB", mx.get_peak_memory() / 1e9)

    def generate(self, messages: list[dict[str, Any]], max_new_tokens: int,
                 sampling: dict[str, Any] | None) -> dict[str, Any]:
        audio_paths: list[str] = []
        template_msgs = []
        for m in messages:
            if isinstance(m["content"], str):
                template_msgs.append(m)
                continue
            parts = []
            for p in m["content"]:
                if p["type"] == "audio":
                    audio_paths.append(p["audio"])
                    parts.append({"type": "audio"})
                else:
                    parts.append(p)
            template_msgs.append({"role": m["role"], "content": parts})

        prompt = self._processor.apply_chat_template(
            template_msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        kwargs = {"temperature": 0.0}
        if sampling:
            kwargs = {"temperature": sampling["temperature"], "top_p": sampling["top_p"], "top_k": sampling["top_k"]}
        t0 = time.perf_counter()
        res = mlx_generate(self._model, self._processor, prompt, audio=audio_paths or None,
                           max_tokens=max_new_tokens, verbose=False, **kwargs)
        seconds = time.perf_counter() - t0
        return {"text": res.text.strip(), "new_tokens": int(res.generation_tokens),
                "input_tokens": int(res.prompt_tokens), "seconds": round(seconds, 3)}
