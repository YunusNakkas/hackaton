"""Model servisine erişim sınırı. Worker yalnızca bu arayüzü bilir.

real: model-service'e HTTP (contracts/model-service.yaml).
stub: süreç içi, GPU'suz; çıktılar gerçek model değildir, değerlendirme kanıtı sayılmaz.
"""

import base64
import json
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.services import demo_customer


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


def _last_employee_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


class StubModelClient:
    model_name = "stub"
    runtime = "stub"

    def __init__(self) -> None:
        self._n = 0

    def transcribe(self, wav: bytes, prompt: str) -> str:
        seconds = max(1, (len(wav) - 44) // 32_000)
        return f"[stub transkript] {seconds} saniyelik çalışan konuşması."

    def chat(self, messages, *, max_new_tokens, temperature, purpose, stub_context=None) -> str:
        if purpose == "customer_reply":
            ctx = stub_context or {}
            said = ctx.get("employee_text") or _last_employee_text(messages)
            return demo_customer.reply(ctx.get("scenario") or {}, said, ctx.get("history") or [])
        if purpose in ("evaluation", "evaluation_repair"):
            return json.dumps(_stub_evaluation(stub_context or {}), ensure_ascii=False)
        if purpose in ("draft", "draft_repair"):
            return json.dumps(_stub_draft(stub_context or {}), ensure_ascii=False)
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


def _stub_draft(ctx: dict[str, Any]) -> dict[str, Any]:
    form = ctx.get("form", {})
    situations = form.get("customer_situations") or ["Genel müşteri talebi"]
    policy_ids = [p["id"] for p in ctx.get("policies", [])]
    scenarios = [{
        "key": f"stub_senaryo_{i + 1}", "title": f"[stub] {situations[i % len(situations)]}",
        "difficulty": "medium", "summary": f"[stub] {situations[i % len(situations)]}",
        "customer": {"name": "Örnek Müşteri", "context": "[stub] bağlam", "mood": "sabırsız",
                     "hidden_goal": "[stub] hızlı çözüm"},
        "opening_line": "Merhaba, bir sorunum var.", "success_criteria": ["Politikayı doğru aktarmak"],
        "visible_policy_ids": policy_ids[:1], "max_turns": 6,
    } for i in range(form.get("scenario_count", 1))]
    levels = [f"{n}: [stub] seviye" for n in range(5)]
    dims = [{"id": d, "name": d, "description": "[stub]", "levels": levels, "weight": 1}
            for d in ("empathy", "policy_accuracy", "solution")]
    return {"scenarios": scenarios, "rubric": {"dimensions": dims}}


_stub_singleton: StubModelClient | None = None


def get_model_client(settings: Settings) -> ModelClient:
    global _stub_singleton
    if settings.model_mode == "stub":
        _stub_singleton = _stub_singleton or StubModelClient()
        return _stub_singleton
    return HttpModelClient(settings)
