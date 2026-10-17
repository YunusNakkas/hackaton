"""Sürümlü prompt'lar. Prompt değişirse sürüm artar; oturum başladığı sürümü saklar."""

from typing import Any

CUSTOMER_VERSION = "customer@1"
EVALUATOR_VERSION = "evaluator@1"
ASR_VERSION = "asr@1"
END_MARKER = "[GÖRÜŞME_BİTTİ]"
ROLE_REMINDER = (
    "Hatırlatma: Sen anlatıcı veya koç değilsin, MÜŞTERİSİN. Çalışanın son cümlesi anlamsız, kaba veya "
    "eksik olsa bile müşteri olarak, birinci tekil şahısla, en fazla 2 cümleyle doğrudan çalışana cevap ver."
)


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


# Zorlaştırılmış tekrarda odak boyuta göre müşteri davranışı. Bilinmeyen (taslaktan gelen) boyutlar için
# boyutun kendi açıklamasından genel bir yönerge üretilir.
_ADAPTIVE = {
    "empathy": ("Duygunu her cevapta açıkça söyle (ör. 'çok sinirlendim', 'kendimi hiç önemsenmemiş hissediyorum'). "
                "Çalışan duygunu adıyla kabul etmeden çözümden bahsederse daha da sertleş ve bunu ona söyle "
                "(ör. 'Beni dinlemiyorsunuz bile'). Ancak duygun gerçekten kabul edilirse biraz yumuşa."),
    "policy_accuracy": ("Kuralları sorgula ve istisna iste (ör. 'Başka mağazada yapıyorlar', 'Bir kereliğine olsun'). "
                        "Çalışan yanlış veya eksik bilgi verirse hemen yakala ve itiraz et."),
    "solution": ("Somut bir çözüm, süre ve sonraki adım duymadıkça kabul etme; 'Ne zaman? Kim? Nasıl?' diye sor. "
                 "Belirsiz cevaplarda ısrar et."),
    "clarity": "Uzun veya karışık cevaplarda kafan karışsın ve tekrar açıklama iste; kısa ve net cevap bekle.",
}


def adaptive_instructions(rubric: dict[str, Any], focus_ids: list[str]) -> str:
    dims = {d["id"]: d for d in rubric["dimensions"]}
    lines = []
    for fid in focus_ids:
        d = dims.get(fid)
        if d is None:
            continue
        lines.append(_ADAPTIVE.get(fid) or
                     f"Çalışanın '{d['name']}' konusunda kendini göstermesini zorlaştır ({d['description']}).")
    if not lines:
        return ""
    return ("Bu bir TEKRAR provası; normalden ZOR bir müşterisin, çalışanı zorla ama gerçekçi kal:\n"
            + "\n".join(f"- {x}" for x in lines) + "\n")


def customer_messages(scenario: dict[str, Any], policies: list[dict[str, Any]],
                      turns: list[tuple[str, str]], adaptive: str = "") -> list[dict[str, Any]]:
    """turns: (speaker, text) sırası. Müşteri = assistant, çalışan = user. adaptive: adaptive_instructions()."""
    c = scenario["customer"]
    visible = [p for p in policies if p["id"] in set(scenario.get("visible_policy_ids", []))]
    known = "\n".join(f"- {p['title']}: {p['body']}" for p in visible) or "- Mağaza kurallarını bilmiyorsun."
    # Zorlaştırma yönergesi ruh hâlinin hemen ardından gelir; prompt sonuna konduğunda etkisi zayıftı.
    system = (
        f"Sen bir müşteri hizmetleri provasında MÜŞTERİ rolündesin. Adın: {c['name']}.\n"
        f"Durumun: {c['context']}\nRuh hâlin: {c['mood']}\n"
        + adaptive
        + f"Gizli hedefin (asla doğrudan söyleme, davranışınla göster): {c['hidden_goal']}\n"
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
                        rubric: dict[str, Any], labeled_turns: list[tuple[str, str, str]],
                        focus_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """labeled_turns: (etiket, speaker, text); etiketler t0, t1, ..."""
    policy_txt = "\n".join(f"[{p['id']}] {p['title']}: {p['body']}" for p in policies)
    dims_txt = "\n".join(
        f"- {d['id']} ({d['name']}): {d['description']}\n"
        + "\n".join(f"    {score}: {level}" for score, level in enumerate(d["levels"]))
        for d in rubric["dimensions"]
    )
    transcript = "\n".join(f"[{label}] {speaker}: {text}" for label, speaker, text in labeled_turns)
    dim_ids = ", ".join(d["id"] for d in rubric["dimensions"])
    focus_names = [d["name"] for d in rubric["dimensions"] if d["id"] in set(focus_ids or [])]
    focus_txt = (f"Bu bir tekrar provası. Çalışan özellikle şu boyutları geliştirmeye çalışıyor: {', '.join(focus_names)}. "
                 "Bu boyutlarda gerekçeyi ayrıntılı yaz; gelişim önerileri ve tekrar egzersizi bunlara odaklansın.\n\n"
                 if focus_names else "")
    prompt = f"""Bir müşteri hizmetleri prova görüşmesini ÇALIŞAN (employee) açısından değerlendir.

Senaryo: {scenario['title']} — {scenario['summary']}
Başarı ölçütleri: {"; ".join(scenario.get("success_criteria", []))}

İşletme politikaları:
{policy_txt}

Rubrik boyutları (0-4 puan):
{dims_txt}

Transkript (ses tanıma çıktısıdır, küçük yazım hataları olabilir):
{transcript}

{focus_txt}Kurallar:
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


DRAFT_VERSION = "draft@1"


def draft_messages(form: dict[str, Any], policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Yöneticinin formundan senaryo + rubrik üretimi. Politikalar kimlikleriyle verilir, değiştirilmez."""
    policy_txt = "\n".join(f"[{p['id']}] {p['title']}: {p['body']}" for p in policies)
    bullets = lambda xs: "\n".join(f"- {x}" for x in xs) or "- (belirtilmedi)"  # noqa: E731
    prompt = f"""Bir işletme için müşteri hizmetleri prova eğitimi hazırla.

İşletme: {form['business_name']} (sektör: {form['sector']})

Politikalar (kimlikleriyle; metinlerini DEĞİŞTİRME, yalnızca kimlikle atıf yap):
{policy_txt}

Prova edilecek müşteri durumları:
{bullets(form['customer_situations'])}

Çalışan şunları YAPMALI:
{bullets(form['must_do'])}

Çalışan şunları YAPMAMALI:
{bullets(form['must_not_do'])}

Yöneticiye aktarma kuralı: {form.get('escalation_rule') or '(belirtilmedi)'}

Görev: tam olarak {form['scenario_count']} senaryo ve bir değerlendirme rubriği üret.
- Her senaryoda müşteri gerçekçi bir kişi olsun; hidden_goal müşterinin gizli beklentisidir.
- opening_line müşterinin ilk cümlesidir (1-2 cümle, doğal Türkçe).
- visible_policy_ids: müşterinin bilebileceği (ör. ilan edilmiş) politikaların kimlikleri; iç kurallar olmasın.
- success_criteria çalışanın yapması gerekenler; politikalara ve "yapmalı/yapmamalı" listelerine dayansın.
- difficulty: easy, medium veya hard. max_turns: 4-12. key: küçük harf, rakam ve alt çizgi.
- Rubrik 3-5 boyut olsun; her boyutun 0'dan 4'e tam olarak 5 seviye tanımı olsun (levels dizisi, index = puan).
Türkçe yaz. YALNIZCA şu şekilde JSON döndür, başka metin yazma:
{{"scenarios":[{{"key":"...","title":"...","difficulty":"medium","summary":"...","customer":{{"name":"...","context":"...","mood":"...","hidden_goal":"..."}},"opening_line":"...","success_criteria":["..."],"visible_policy_ids":["policy_1"],"max_turns":8}}],"rubric":{{"dimensions":[{{"id":"empathy","name":"Empati","description":"...","levels":["0: ...","1: ...","2: ...","3: ...","4: ..."],"weight":1}}]}}}}"""
    return [{"role": "user", "content": prompt}]
