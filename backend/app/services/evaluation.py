"""Model değerlendirme çıktısını doğrular ve sözleşmedeki EvaluationReport'a çevirir.

Toplam puanı model değil bu kod hesaplar. Kanıt, tur etiketi + birebir alıntı + konuşmacı ile
doğrulanır; doğrulanamayan kanıt raporu `needs_review` durumuna düşürür.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

# Bu bayraklardan biri varsa rapor yönetici incelemesi olmadan kesin sayılmaz.
REVIEW_FLAGS = {"unverified_evidence", "dropped_evidence", "score_without_verified_evidence",
                "schema_repaired", "unknown_policy_ref"}


@dataclass
class LabeledTurn:
    turn_id: str
    speaker: str
    text: str


class EvaluationShapeError(ValueError):
    pass


def parse_json_output(text: str) -> dict[str, Any]:
    raw = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise EvaluationShapeError("JSON nesnesi bulunamadı")
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        raise EvaluationShapeError(f"geçersiz JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise EvaluationShapeError("kök JSON nesne olmalı")
    return data


def _valid_score(v: Any) -> bool:
    return v is None or (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 4)


def check_shape(data: dict[str, Any], dimension_ids: list[str]) -> None:
    dims = data.get("dimensions")
    if not isinstance(dims, list):
        raise EvaluationShapeError("'dimensions' listesi yok")
    got = [d.get("dimension_id") for d in dims if isinstance(d, dict)]
    if sorted(got) != sorted(dimension_ids):
        raise EvaluationShapeError(f"boyutlar tam olarak şunlar olmalı: {', '.join(dimension_ids)}")
    for d in dims:
        if not _valid_score(d.get("score")):
            raise EvaluationShapeError(f"{d.get('dimension_id')}: score 0-4 tam sayı veya null olmalı")
        if not isinstance(d.get("evidence", []), list) or not isinstance(d.get("policy_refs", []), list):
            raise EvaluationShapeError(f"{d.get('dimension_id')}: evidence ve policy_refs liste olmalı")


def _norm(s: str) -> str:
    s = s.replace("I", "ı").replace("İ", "i").lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())


def quote_in(quote: str, text: str) -> bool:
    q = _norm(quote)
    return bool(q) and q in _norm(text)


def compute_total(scores: dict[str, int | None], rubric: dict[str, Any]) -> dict[str, Any]:
    weights = {d["id"]: float(d.get("weight", 1)) for d in rubric["dimensions"]}
    scored = [k for k, v in scores.items() if v is not None]
    complete = len(scored) == len(weights)
    total = sum(scores[k] * weights[k] for k in scored) if complete else None
    return {
        "score": round(total, 2) if total is not None else None,
        "max_score": round(sum(4 * w for w in weights.values()), 2),
        "complete": complete,
        "scored_dimensions": len(scored),
        "total_dimensions": len(weights),
    }


def build_report(data: dict[str, Any], *, rubric: dict[str, Any], rubric_version: str,
                 policies: list[dict[str, Any]], turns_by_label: dict[str, LabeledTurn],
                 model_run: dict[str, Any], employee_turn_count: int,
                 focus_ids: list[str] | None = None) -> tuple[dict[str, Any], str]:
    """Doğrulanmış rapor ve durum (ready | needs_review) döner. Şekil önceden check_shape ile kontrol edilmiş olmalı."""
    flags: set[str] = set()
    if model_run.get("repaired"):
        flags.add("schema_repaired")
    if employee_turn_count < 2:
        flags.add("short_session")
    policy_by_id = {p["id"]: p for p in policies}
    by_id = {d.get("dimension_id"): d for d in data["dimensions"]}

    dimensions = []
    for rd in rubric["dimensions"]:
        d = by_id[rd["id"]]
        evidence = []
        for ev in d.get("evidence", []):
            if not isinstance(ev, dict):
                continue
            turn = turns_by_label.get(str(ev.get("turn_id")))
            quote = str(ev.get("quote", "")).strip()
            if turn is None or not quote:
                flags.add("dropped_evidence")
                continue
            verified = turn.speaker == "employee" and quote_in(quote, turn.text)
            if not verified:
                flags.add("unverified_evidence")
            evidence.append({"turn_id": turn.turn_id, "speaker": turn.speaker, "quote": quote, "verified": verified})
        refs = []
        for pid in d.get("policy_refs", []):
            pid = pid.get("policy_id") if isinstance(pid, dict) else pid
            policy = policy_by_id.get(str(pid))
            if policy is None:
                flags.add("unknown_policy_ref")
            refs.append({"policy_id": str(pid), "title": policy["title"] if policy else "Bilinmeyen politika",
                         "quote": None, "verified": policy is not None})
        score = d.get("score")
        if score is not None and not any(e["verified"] for e in evidence):
            flags.add("score_without_verified_evidence")
        dimensions.append({
            "dimension_id": rd["id"], "name": rd["name"], "score": score, "max_score": 4,
            "insufficient_evidence": score is None, "rationale": str(d.get("rationale", "")),
            "evidence": evidence, "policy_refs": refs,
        })

    drill = data.get("practice_drill")
    if isinstance(drill, dict) and drill.get("title") and drill.get("instructions"):
        known = {rd["id"] for rd in rubric["dimensions"]}
        drill = {
            "title": str(drill["title"]), "instructions": str(drill["instructions"]),
            "focus_dimension_ids": [x for x in drill.get("focus_dimension_ids", []) if x in known],
            "example_phrases": [str(x) for x in drill.get("example_phrases", [])][:5],
        }
    else:
        drill = None

    report = {
        "rubric_version": rubric_version,
        "dimensions": dimensions,
        "total": compute_total({d["dimension_id"]: d["score"] for d in dimensions}, rubric),
        "strengths": [str(x) for x in data.get("strengths", []) if x][:5],
        "improvements": [str(x) for x in data.get("improvements", []) if x][:5],
        "practice_drill": drill,
        "flags": sorted(flags),
        "model_run": model_run,
        "focus_dimension_ids": [f for f in (focus_ids or []) if f in by_id],
    }
    return report, "needs_review" if flags & REVIEW_FLAGS else "ready"


def apply_review(report: dict[str, Any], review: dict[str, Any] | None, rubric: dict[str, Any]) -> dict[str, Any]:
    """Saklanan rapora en son yönetici incelemesini ve geçerli toplamı ekler (saklananı değiştirmez)."""
    scores = {d["dimension_id"]: d["score"] for d in report["dimensions"]}
    if review:
        for adj in review["adjustments"]:
            if adj["dimension_id"] in scores:
                scores[adj["dimension_id"]] = adj["score"]
    # focus_dimension_ids v0.2.0'da eklendi; eski raporlarda yok.
    return {"focus_dimension_ids": [], **report, "manager_review": review,
            "effective_total": compute_total(scores, rubric) if review else report["total"]}
