"""Sürümlü prompt'lar. Prompt değişirse sürüm artar; oturum başladığı sürümü saklar."""

from typing import Any

CUSTOMER_VERSION = "customer@1"
EVALUATOR_VERSION = "evaluator@1"
ASR_VERSION = "asr@1"
END_MARKER = "[GÖRÜŞME_BİTTİ]"


def asr_prompt(hint_terms: list[str]) -> str:
    # Model kartındaki resmî ASR prompt'u, Türkçe için uyarlanmış.
    prompt = (
        "Transcribe the following speech segment in Turkish into Turkish text. "
        "Follow these specific instructions for formatting the answer:\n"
        "* Only output the transcription, with no newlines.\n"
        "* When transcribing numbers, write the digits, i.e. write 1.7 and not one point seven, "
        "and write 3 instead of three."
    )
    if hint_terms:
        prompt += "\n* The conversation may contain these words: " + ", ".join(hint_terms) + "."
    return prompt


def customer_messages(scenario: dict[str, Any], policies: list[dict[str, Any]],
                      turns: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """turns: (speaker, text) sırası. Müşteri = assistant, çalışan = user."""
    c = scenario["customer"]
    visible = [p for p in policies if p["id"] in set(scenario.get("visible_policy_ids", []))]
    known = "\n".join(f"- {p['title']}: {p['body']}" for p in visible) or "- Mağaza kurallarını bilmiyorsun."
    system = (
        f"Sen bir müşteri hizmetleri provasında MÜŞTERİ rolündesin. Adın: {c['name']}.\n"
        f"Durumun: {c['context']}\nRuh hâlin: {c['mood']}\n"
        f"Gizli hedefin (asla doğrudan söyleme, davranışınla göster): {c['hidden_goal']}\n"
        f"Bir müşterinin bilebileceği bilgiler:\n{known}\n\n"
        "Kurallar:\n"
        "- Yalnızca müşteri olarak konuş; asla çalışan, asistan veya yapay zekâ gibi konuşma.\n"
        "- Kısa ve doğal Türkçe konuş, en fazla 2 cümle.\n"
        "- Çalışan iyi bir çözüm sunarsa yumuşa; geçiştirirse ısrar et.\n"
        f"- Sorunun çözüldüyse veya görüşmeyi bırakmak istiyorsan cevabının sonuna {END_MARKER} ekle."
    )
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for speaker, text in turns:
        msgs.append({"role": "assistant" if speaker == "customer" else "user", "content": text})
    return msgs


def evaluation_messages(scenario: dict[str, Any], policies: list[dict[str, Any]],
                        rubric: dict[str, Any], labeled_turns: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    """labeled_turns: (etiket, speaker, text); etiketler t0, t1, ..."""
    policy_txt = "\n".join(f"[{p['id']}] {p['title']}: {p['body']}" for p in policies)
    dims_txt = "\n".join(
        f"- {d['id']} ({d['name']}): {d['description']}\n"
        + "\n".join(f"    {score}: {level}" for score, level in enumerate(d["levels"]))
        for d in rubric["dimensions"]
    )
    transcript = "\n".join(f"[{label}] {speaker}: {text}" for label, speaker, text in labeled_turns)
    dim_ids = ", ".join(d["id"] for d in rubric["dimensions"])
    prompt = f"""Bir müşteri hizmetleri prova görüşmesini ÇALIŞAN (employee) açısından değerlendir.

Senaryo: {scenario['title']} — {scenario['summary']}
Başarı ölçütleri: {"; ".join(scenario.get("success_criteria", []))}

İşletme politikaları:
{policy_txt}

Rubrik boyutları (0-4 puan):
{dims_txt}

Transkript (ses tanıma çıktısıdır, küçük yazım hataları olabilir):
{transcript}

Kurallar:
- Her boyut için ({dim_ids}) 0-4 tam sayı puan ver. Transkriptte yeterli kanıt yoksa score null olsun.
- Kanıt olarak yalnızca çalışan turlarından BİREBİR alıntı yap ve tur etiketini (ör. t1) ver.
- policy_refs yalnızca yukarıdaki politika kimliklerini içersin.
- Türkçe yaz. YALNIZCA aşağıdaki şekilde JSON döndür, başka metin yazma:
{{"dimensions":[{{"dimension_id":"...","score":0,"rationale":"...","evidence":[{{"turn_id":"t1","quote":"..."}}],"policy_refs":["..."]}}],"strengths":["..."],"improvements":["..."],"practice_drill":{{"title":"...","instructions":"...","focus_dimension_ids":["..."],"example_phrases":["..."]}}}}"""
    return [{"role": "user", "content": prompt}]


def repair_messages(bad_output: str, problem: str) -> list[dict[str, Any]]:
    prompt = (
        "Aşağıdaki çıktı istenen JSON şemasına uymuyor. Sorun: " + problem + "\n"
        "İçeriği değiştirmeden yalnızca geçerli JSON olarak tekrar yaz, başka metin ekleme.\n\n" + bad_output
    )
    return [{"role": "user", "content": prompt}]
