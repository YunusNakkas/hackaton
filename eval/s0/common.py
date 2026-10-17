"""S0 ölçümlerinde ortak girdiler: prompt'lar, örnek görüşme ve hata oranı hesapları."""

import re

# Model kartındaki resmî ASR prompt'u, Türkçe için uyarlanmış.
ASR_PROMPT = (
    "Transcribe the following speech segment in Turkish into Turkish text. "
    "Follow these specific instructions for formatting the answer:\n"
    "* Only output the transcription, with no newlines.\n"
    "* When transcribing numbers, write the digits, i.e. write 1.7 and not one point seven, "
    "and write 3 instead of three."
)

CUSTOMER_SYSTEM = (
    "Sen bir mağazada iade yapmak isteyen müşteri Ayşe Hanım'sın. Üç hafta önce bir mont aldın, "
    "fişin yok ama kart ekstren telefonunda. Biraz sinirlisin ama kaba değilsin. Hediye çeki "
    "istemiyorsun, paranı kartına geri istiyorsun. Yalnızca müşteri olarak, kısa ve doğal Türkçe "
    "konuş (en fazla 2 cümle). Asla mağaza çalışanı gibi konuşma."
)
CUSTOMER_HISTORY = [
    {"role": "assistant", "content": "Merhaba, bu montu iade etmek istiyorum ama fişim yok."},
    {"role": "user", "content": "Merhaba, yardımcı olayım. Ödemeyi nasıl yapmıştınız?"},
    {"role": "assistant", "content": "Kartla ödemiştim, ekstrem telefonumda var."},
    {"role": "user", "content": "Kartla ödenen alışverişlerde kayıt bulunursa iadeyi kartınıza yapabiliyoruz."},
]

EVAL_PROMPT = """Aşağıdaki müşteri hizmetleri görüşmesini çalışan açısından değerlendir.

Politika P1 (Fişsiz iade): Kartlı ödemede POS kaydı bulunursa iade karta yapılır, 3 iş günü içinde yansır.

Transkript:
[t1] customer: Merhaba, bu montu iade etmek istiyorum ama fişim yok.
[t2] employee: Merhaba, yardımcı olayım. Ödemeyi nasıl yapmıştınız?
[t3] customer: Kartla ödemiştim, ekstrem telefonumda var.
[t4] employee: Kartla ödenen alışverişlerde kayıt bulunursa iadeyi kartınıza yapabiliyoruz.
[t5] customer: Peki ne kadar sürer?
[t6] employee: Bilmiyorum, muhasebe bakıyor.

Boyutlar: empathy, policy_accuracy, solution, clarity. Her boyuta 0-4 tam sayı puan ver; kanıt yetersizse null.
Kanıt olarak yalnızca transkriptten BİREBİR alıntı yap ve tur kimliğini ver.
YALNIZCA şu JSON'u döndür, başka metin yazma:
{"dimensions":[{"dimension_id":"...","score":0,"rationale":"...","evidence":[{"turn_id":"t2","quote":"..."}],"policy_refs":["P1"]}],"strengths":["..."],"improvements":["..."]}"""

SAMPLING = {"do_sample": True, "temperature": 1.0, "top_p": 0.95, "top_k": 64}


def normalize(text: str) -> list[str]:
    text = text.replace("I", "ı").replace("İ", "i").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]
