"""Model servisine erişim sınırı. Worker yalnızca bu arayüzü bilir.

real: model-service'e HTTP (contracts/model-service.yaml).
stub: süreç içi, GPU'suz; çıktılar gerçek model değildir, değerlendirme kanıtı sayılmaz.
"""

import base64
import json
from typing import Any, Protocol

import httpx

from app.core.config import Settings


class ModelUnavailable(Exception):
    pass


class ModelClient(Protocol):
    model_name: str
    runtime: str

    def transcribe(self, wav: bytes, prompt: str) -> str: ...

    def chat(self, messages: list[dict[str, Any]], *, max_new_tokens: int, temperature: float,
             purpose: str, stub_context: dict[str, Any] | None = None) -> str: ...


class HttpModelClient:
    runtime = "transformers"

    def __init__(self, settings: Settings):
        self._http = httpx.Client(base_url=settings.model_service_url, timeout=settings.model_timeout_s)
        self.model_name = "unknown"

    def _generate(self, body: dict[str, Any]) -> str:
        try:
            res = self._http.post("/v1/generate", json=body)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise ModelUnavailable(str(exc)) from exc
        data = res.json()
        self.model_name = data.get("model", self.model_name)
        self.runtime = data.get("runtime", self.runtime)
        return data["text"]

    def transcribe(self, wav: bytes, prompt: str) -> str:
        content = [{"type": "text", "text": prompt},
                   {"type": "audio", "audio_b64": base64.b64encode(wav).decode()}]
        return self._generate({"messages": [{"role": "user", "content": content}],
                               "max_new_tokens": 256, "sampling": None, "priority": 0})

    def chat(self, messages, *, max_new_tokens, temperature, purpose, stub_context=None) -> str:
        sampling = {"temperature": temperature, "top_p": 0.95, "top_k": 64}
        priority = 0 if purpose == "customer_reply" else 10
        return self._generate({"messages": messages, "max_new_tokens": max_new_tokens,
                               "sampling": sampling, "priority": priority})


class StubModelClient:
    model_name = "stub"
    runtime = "stub"

    _REPLIES = [
        "Anladım, peki bu durumda ne yapabilirsiniz?",
        "Bu bana pek yeterli gelmedi, başka bir seçenek var mı?",
        "Tamam, teşekkür ederim. Sonraki adım nedir?",
    ]

    def __init__(self) -> None:
        self._n = 0

    def transcribe(self, wav: bytes, prompt: str) -> str:
        seconds = max(1, (len(wav) - 44) // 32_000)
        return f"[stub transkript] {seconds} saniyelik çalışan konuşması."

    def chat(self, messages, *, max_new_tokens, temperature, purpose, stub_context=None) -> str:
        if purpose == "customer_reply":
            self._n += 1
            return self._REPLIES[self._n % len(self._REPLIES)]
        if purpose in ("evaluation", "evaluation_repair"):
            return json.dumps(_stub_evaluation(stub_context or {}), ensure_ascii=False)
        raise ValueError(f"stub bilinmeyen amaç: {purpose}")


def _stub_evaluation(ctx: dict[str, Any]) -> dict[str, Any]:
    employee_turns: list[tuple[str, str]] = ctx.get("employee_turns", [])
    label, text = employee_turns[0] if employee_turns else (None, "")
    quote = " ".join(text.split()[:4])
    return {
        "dimensions": [
            {"dimension_id": d, "score": 2, "rationale": "[stub] Örnek gerekçe.",
             "evidence": [{"turn_id": label, "quote": quote}] if label else [], "policy_refs": []}
            for d in ctx.get("dimension_ids", [])
        ],
        "strengths": ["[stub] Örnek güçlü yön."],
        "improvements": ["[stub] Örnek gelişim alanı."],
        "practice_drill": {"title": "[stub] Tekrar egzersizi", "instructions": "Aynı senaryoyu tekrar deneyin.",
                           "focus_dimension_ids": ctx.get("dimension_ids", [])[:1], "example_phrases": []},
    }


_stub_singleton: StubModelClient | None = None


def get_model_client(settings: Settings) -> ModelClient:
    global _stub_singleton
    if settings.model_mode == "stub":
        _stub_singleton = _stub_singleton or StubModelClient()
        return _stub_singleton
    return HttpModelClient(settings)
