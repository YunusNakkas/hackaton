"""Yerel Ollama üzerinden sıkıştırılmış Gemma ile yazılı üretim."""

import os
from typing import Any

import httpx


class OllamaAdapter:
    runtime = "ollama"
    supports_audio = False  # yerel metin modeli; ses girişi 422 ile reddedilir

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.device = "auto"
        self.ready = False
        self._http = httpx.Client(
            base_url=os.environ.get("PM_OLLAMA_URL", "http://127.0.0.1:11434"),
            timeout=float(os.environ.get("PM_MODEL_TIMEOUT_S", "600")),
        )
        self.context_length = int(os.environ.get("PM_OLLAMA_CONTEXT_LENGTH", "8192"))

    def load(self) -> None:
        response = self._http.post("/api/show", json={"model": self.model_id})
        response.raise_for_status()

    def check_health(self) -> None:
        self._http.get("/api/version", timeout=1).raise_for_status()

    def warmup(self) -> None:
        self.generate([{"role": "user", "content": "Merhaba"}], max_new_tokens=4, sampling=None)
        response = self._http.get("/api/ps")
        response.raise_for_status()
        for model in response.json().get("models", []):
            if model.get("name") == self.model_id or model.get("model") == self.model_id:
                vram = model.get("size_vram", 0)
                self.device = "gpu+cpu" if 0 < vram < model.get("size", 0) else "gpu" if vram else "cpu"
        self.ready = True

    def generate(self, messages: list[dict[str, Any]], max_new_tokens: int,
                 sampling: dict[str, Any] | None) -> dict[str, Any]:
        text_messages = []
        for message in messages:
            content = message["content"]
            if isinstance(content, list):
                if any(part["type"] != "text" for part in content):
                    raise ValueError("Ollama runtime'ı bu uygulamada yalnız yazılı prova destekler.")
                content = "\n".join(part["text"] for part in content)
            text_messages.append({"role": message["role"], "content": content})
        options = {"num_predict": max_new_tokens, "num_ctx": self.context_length,
                   **(sampling if sampling is not None else {"temperature": 0})}
        response = self._http.post("/api/chat", json={
            "model": self.model_id, "messages": text_messages, "stream": False,
            "think": False, "keep_alive": "30m", "options": options,
        })
        response.raise_for_status()
        data = response.json()
        text = data.get("message", {}).get("content", "").strip()
        if not data.get("done") or not text:
            raise RuntimeError("Ollama tamamlanmış bir metin yanıtı üretmedi.")
        return {"text": text, "new_tokens": data.get("eval_count", 0),
                "input_tokens": data.get("prompt_eval_count", 0),
                "seconds": round(data.get("eval_duration", 0) / 1e9, 3)}
