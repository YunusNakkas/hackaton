"""Eğitim taslağı: form → Gemma ile senaryo + rubrik → doğrulama → yayımlama.

Politikalar modelden değil doğrudan yöneticinin formundan gelir; model politika metnini
değiştiremez, yalnızca kimliklerine atıf yapar.
"""

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

Slug = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,47}$")]
Sector = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")]
ShortText = Annotated[str, Field(max_length=300)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FormPolicy(_Strict):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


class BusinessRulesForm(_Strict):
    business_name: str = Field(min_length=1, max_length=120)
    sector: Sector
    language: Literal["tr"]
    policies: list[FormPolicy] = Field(min_length=1, max_length=30)
    customer_situations: list[ShortText] = Field(max_length=20)
    must_do: list[ShortText] = Field(max_length=20)
    must_not_do: list[ShortText] = Field(max_length=20)
    escalation_rule: str | None = Field(None, max_length=1000)
    scenario_count: int = Field(ge=1, le=5)


class PolicyItem(BaseModel):
    id: Slug
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class RubricDimension(BaseModel):
    id: Slug
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    levels: list[str] = Field(min_length=5, max_length=5)
    weight: float = Field(1, gt=0)


class Customer(BaseModel):
    name: str = Field(min_length=1)
    context: str = Field(min_length=1)
    mood: str = Field(min_length=1)
    hidden_goal: str = Field(min_length=1)


class ScenarioDraft(BaseModel):
    key: Slug
    title: str = Field(min_length=1, max_length=200)
    difficulty: Literal["easy", "medium", "hard"]
    summary: str = Field(min_length=1)
    customer: Customer
    opening_line: str = Field(min_length=1)
    success_criteria: list[str] = Field(min_length=1)
    visible_policy_ids: list[str] = []
    max_turns: int = Field(ge=2, le=20)


class Rubric(BaseModel):
    dimensions: list[RubricDimension] = Field(min_length=1, max_length=8)

    @field_validator("dimensions")
    @classmethod
    def _unique(cls, v: list[RubricDimension]) -> list[RubricDimension]:
        if len({d.id for d in v}) != len(v):
            raise ValueError("rubrik boyut kimlikleri benzersiz olmalı")
        return v


class DraftContent(_Strict):
    scenarios: list[ScenarioDraft] = Field(min_length=1, max_length=5)
    policies: list[PolicyItem]
    rubric: Rubric

    @field_validator("scenarios")
    @classmethod
    def _unique_keys(cls, v: list[ScenarioDraft]) -> list[ScenarioDraft]:
        if len({s.key for s in v}) != len(v):
            raise ValueError("senaryo anahtarları benzersiz olmalı")
        return v


class GeneratedPart(BaseModel):
    """Modelin üretmesi beklenen kısım (politikalar formdan eklenir)."""

    scenarios: list[ScenarioDraft] = Field(min_length=1, max_length=5)
    rubric: Rubric


def form_policies(form: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"id": f"policy_{i}", "title": p["title"], "body": p["body"]}
            for i, p in enumerate(form["policies"], 1)]


def validation_problem(exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(x) for x in first["loc"])
    return f"{loc}: {first['msg']}"


def warnings_for(content: dict[str, Any]) -> list[str]:
    """Yayımlamayı engellemeyen ama yöneticinin görmesi gereken tutarsızlıklar."""
    known = {p["id"] for p in content["policies"]}
    out = []
    for s in content["scenarios"]:
        for pid in s["visible_policy_ids"]:
            if pid not in known:
                out.append(f"'{s['title']}' senaryosu var olmayan politikaya atıf yapıyor: {pid}")
    return out


def training_rows(content: dict[str, Any], *, draft_id: str, version: int, sector: str) -> list[dict[str, Any]]:
    """Yayımlanacak Training satırlarının alanları. Bilinmeyen politika atıfları ayıklanır."""
    known = {p["id"] for p in content["policies"]}
    base = f"draft:{draft_id}@v{version}"
    rows = []
    for s in content["scenarios"]:
        scenario = {**s, "visible_policy_ids": [p for p in s["visible_policy_ids"] if p in known]}
        rows.append({
            "title": s["title"], "sector": sector, "language": "tr", "difficulty": s["difficulty"],
            "summary": s["summary"], "estimated_minutes": max(3, round(s["max_turns"] * 0.6)),
            "max_turns": s["max_turns"], "scenario": scenario, "policies": content["policies"],
            "rubric": content["rubric"], "scenario_version": f"{base}#{s['key']}",
            "policy_version": base, "rubric_version": base,
        })
    return rows


def slugify(text: str, fallback: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-z0-9]+", "_", text.translate(table).lower()).strip("_")[:40].strip("_")
    return s if re.match(r"^[a-z][a-z0-9_]{1,47}$", s or "") else fallback


# ---------------------------------------------------------------- model çıktısını onarma
# Ölçüm (eval/draft_bench.py, 10 taslak): geçersizlerin hepsi biçim hatasıydı, içerik değil:
# Türkçe karakterli anahtar ("reçete_sorunu"), sözlük olarak seviyeler ({"0": ...}), metne sızan
# "Politika_1". Bunları modelden tekrar istemek yerine burada düzeltiyoruz.

_POLICY_REF = re.compile(r"\[?\b(?:policy|politika)[\s_-]?(\d+)\b\]?", re.I)


def _unique(slug: str, used: set[str]) -> str:
    out, n = slug, 2
    while out in used:
        out = f"{slug[:44]}_{n}"
        n += 1
    used.add(out)
    return out


# Kimlikten sonra gelen Türkçe hal eki → "politika" kelimesinin doğru çekimi.
_CASES = [  # (ekin başı, bilinen politika için, bilinmeyen için) — uzun ekler önce
    (("ndeki", "ndaki", "deki", "daki", "teki", "taki"), "politikasındaki", "ilgili politikadaki"),
    (("nden", "ndan", "den", "dan", "ten", "tan"), "politikasından", "ilgili politikadan"),
    (("nde", "nda", "de", "da", "te", "ta"), "politikasında", "ilgili politikada"),
    (("nin", "nın", "nun", "nün", "in", "ın", "un", "ün"), "politikasının", "ilgili politikanın"),
    (("yle", "yla", "le", "la"), "politikasıyla", "ilgili politikayla"),
    (("ye", "ya", "e", "a"), "politikasına", "ilgili politikaya"),
    (("yi", "yı", "yu", "yü", "i", "ı", "u", "ü"), "politikasını", "ilgili politikayı"),
]
_REF_IN_TEXT = re.compile(
    r"(?:\bpolitika\s+)?\[?\b(?:policy|politika)[\s_-]?(\d+)\b\]?(?:['’]([a-zçğıöşü]+))?", re.I)


def _replace_policy_refs(text: str, policies: list[dict[str, Any]]) -> str:
    titles = {p["id"]: p["title"] for p in policies}

    def sub(m: re.Match) -> str:
        title = titles.get(f"policy_{m.group(1)}")
        suffix = (m.group(2) or "").lower()
        for starts, known_form, unknown_form in _CASES:
            if suffix and suffix.startswith(starts):
                return f"'{title}' {known_form}" if title else unknown_form
        return f"'{title}' politikası" if title else "ilgili politika"

    return " ".join(_REF_IN_TEXT.sub(sub, text).split())


def repair_generated(raw: dict[str, Any], policies: list[dict[str, Any]],
                     requested: int) -> tuple[dict[str, Any], list[str]]:
    """Doğrulamadan önce biçim hatalarını düzeltir. (düzeltilmiş veri, yöneticiye uyarılar) döner."""
    warnings: list[str] = []
    scenarios = raw.get("scenarios") if isinstance(raw.get("scenarios"), list) else []
    if len(scenarios) > requested:
        warnings.append(f"{requested} senaryo istendi, model {len(scenarios)} üretti; fazlası çıkarıldı.")
        scenarios = scenarios[:requested]
    elif 0 < len(scenarios) < requested:
        warnings.append(f"{requested} senaryo istendi, model yalnızca {len(scenarios)} üretti.")

    known = {p["id"] for p in policies}
    used_keys: set[str] = set()
    for i, s in enumerate(scenarios):
        if not isinstance(s, dict):
            continue
        s["key"] = _unique(slugify(str(s.get("key") or s.get("title") or ""), f"senaryo_{i + 1}"), used_keys)
        for field in ("title", "summary", "opening_line"):
            if isinstance(s.get(field), str):
                s[field] = _replace_policy_refs(s[field], policies)
        if isinstance(s.get("customer"), dict):
            for field in ("context", "mood", "hidden_goal"):
                if isinstance(s["customer"].get(field), str):
                    s["customer"][field] = _replace_policy_refs(s["customer"][field], policies)
        if isinstance(s.get("success_criteria"), list):
            s["success_criteria"] = [_replace_policy_refs(x, policies)
                                     for x in s["success_criteria"] if isinstance(x, str)]
        if isinstance(s.get("visible_policy_ids"), list):  # "Politika_1", "policy 1" → policy_1
            ids = []
            for v in s["visible_policy_ids"]:
                m = _POLICY_REF.fullmatch(str(v).strip())
                ids.append(f"policy_{m.group(1)}" if m else str(v))
            s["visible_policy_ids"] = [v for v in dict.fromkeys(ids) if v in known]

    rubric = raw.get("rubric") if isinstance(raw.get("rubric"), dict) else {}
    used_ids: set[str] = set()
    for i, d in enumerate(rubric.get("dimensions") or []):
        if not isinstance(d, dict):
            continue
        d["id"] = _unique(slugify(str(d.get("id") or d.get("name") or ""), f"boyut_{i + 1}"), used_ids)
        levels = d.get("levels")
        if isinstance(levels, dict):  # {"0": "...", "1": "..."} → sıralı liste
            try:
                d["levels"] = [str(v) for _, v in sorted(levels.items(), key=lambda kv: int(str(kv[0]).strip()[:1]))]
            except ValueError:
                d["levels"] = [str(v) for v in levels.values()]
    return {**raw, "scenarios": scenarios, "rubric": rubric}, warnings
