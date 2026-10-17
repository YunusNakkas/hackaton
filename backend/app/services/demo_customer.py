"""Demo modeli müşteri cevabı. Senaryoyu ve son cümleyi okur; ezber sıra dönmez.

Gerçek Gemma `PM_MODEL_MODE=real` iken bu dosya kullanılmaz.
"""

from typing import Any


def reply(scenario: dict[str, Any], employee_text: str, history: list[tuple[str, str]]) -> str:
    said = " ".join((employee_text or "").split())
    low = said.lower()
    if len(said) < 8:
        return "Ne dediğinizi tam çıkaramadım. Derdimle ilgili somut ne yapacaksınız?"
    handler = _BY_KEY.get(scenario.get("key", ""), _generic)
    return handler(low, said, history)


_FOLD = str.maketrans("çğıöşü", "cgiosu")


def _has(low: str, *needles: str) -> bool:
    folded = low.translate(_FOLD)
    return any(needle.translate(_FOLD) in folded for needle in needles)


def _vague(low: str) -> bool:
    return _has(low, "kontrol", "bakıyor", "bakacağ", "incel", "bir bak")


def _return_no_receipt(low: str, said: str, history: list[tuple[str, str]]) -> str:
    if "hediye" in low and "kart" not in low:
        return "Hediye çeki istemiyorum. Param kartıma geri yatsın."
    if "kart" in low and ("iş gün" in low or "3 gün" in low or "üç" in low):
        return "Süre net, tamam. Ekstremle kaydı bulun, iade kartıma yatsın."
    if "kart" in low and "iade" in low:
        return "Karta iade olur diyorsunuz. Kaç iş gününde yatar, onu da söyleyin."
    if _vague(low):
        return "Ekstre telefonumda. Kaydı bulup parayı kartıma yatıracak mısınız?"
    if any(word in low for word in ("fiş yok", "yapamam", "olmaz", "mümkün değil")):
        return "Fiş kayboldu diye param yanmasın. Kart ekstresi duruyor, kaydı oradan bulun."
    return "Montun iadesini konuşuyoruz. Fiş yok, ekstre var. Param kartıma nasıl dönecek?"


def _expired_return(low: str, said: str, history: list[tuple[str, str]]) -> str:
    if any(word in low for word in ("hemen iade", "para iadesi yap", "iade ediyorum")) and "müdür" not in low:
        return "Bunu tek başınıza vaat edebiliyor musunuz? Müdür onayı gerekmiyor mu?"
    if "müdür" in low and ("değiş" in low or "görüş" in low):
        return "Müdürle değişimi konuşmak makul. Beni ona bağlayın."
    if "30" in low or "otuz" in low:
        return "30 günü duydum. Hiç giymedim, fiş de burada. Değişim olmaz mı?"
    if _vague(low):
        return "Fiş burada, ayakkabıyı hiç giymedim. Bakın da ne önereceğinizi söyleyin."
    return "45 gün oldu ama ayakkabı yeni. Para olmazsa değişim olur mu?"


def _defective(low: str, said: str, history: list[tuple[str, str]]) -> str:
    if "stok" in low and ("yok" in low or "kalmad" in low) and "iade" in low:
        return "Aynı ceket yoksa paramı geri alın, olur."
    if "değiş" in low:
        return "Aynı ceketi istiyorum. Stokta varsa hemen değiştirelim."
    if "özür" in low or "üzgün" in low:
        return "Teşekkürler. Fermuar bozuldu, değişimi bugün yapabilir misiniz?"
    return "Fermuar ilk giyişte bozuldu. Değişim mi yapacaksınız, yoksa paramı mı alacaksınız?"


def _late_checkin(low: str, said: str, history: list[tuple[str, str]]) -> str:
    if _has(low, "geç gel", "iptal", "düşür", "boşa", "sizin yüz", "sizin sebe"):
        return "Geç geldim diye rezervasyonum düşmez. Deniz manzaralı oda yazıyor, onu istiyorum."
    if "yarın" in low:
        return "Yarın olmaz. Bu gece uyuyacak düzgün bir oda istiyorum."
    if "üst kategori" in low or ("ücretsiz" in low and "oda" in low):
        return "Ücretsiz üst kategori bu geceyse kabul. Ne zaman odaya geçiyorum?"
    if "50" in low or "yüzde" in low or "%50" in low:
        return "İade ve yarına bırakmak yetmez. Bu gece üst kategori oda yok mu?"
    if _vague(low):
        return "Kontrol edin ama sonucu söyleyin. Deniz manzaralı odam bu gece nerede?"
    return "Rezervasyonumda deniz manzarası var, bana arka cephe verdiniz. Bu gece ne yapacaksınız?"


def _broken_ac(low: str, said: str, history: list[tuple[str, str]]) -> str:
    if "oda değiş" in low and any(word in low for word in ("dakika", "saat", "süre")):
        return "Oda değişikliği ve süre netse tamam. Bir de kahvaltı eklerseniz beklerim."
    if "kahvaltı" in low or "geç çıkış" in low:
        return "Telafi iyi. Yine de klima düzelmezse başka odaya ne zaman geçeceğim?"
    if any(word in low for word in ("ekip", "gelecek", "yolluyor", "teknik")) and "dakika" not in low:
        return "İki saat oldu. Ekip kaç dakikaya geliyor, oda değişecek mi?"
    if any(word in low for word in ("sizin yüz", "sizin sebe")):
        return "Klimayı ben bozmadım. İki saat önce söyledim, hâlâ çözülmedi."
    return "Klima hâlâ çalışmıyor. Başka oda verecek misiniz, ne zaman?"


def _late_checkout(low: str, said: str, history: list[tuple[str, str]]) -> str:
    if "14" in low and "ücretsiz" in low:
        return "14'e kadar ücretsiz uyar. Uçağım sekizde, beşi de mümkün mü?"
    if "yarım" in low and ("ücret" in low or "fiyat" in low):
        return "Yarım gün ücretini baştan söylemeniz iyi. Uygun mu, bir bakın."
    if any(word in low for word in ("beş", "17:00", "17")):
        return "Beşe kadar kalırsam ücret ne olur, doluluk uygun mu?"
    return "Uçağım akşam sekiz. Odada beşe kadar kalabilir miyim, kaça mal olur?"


def _generic(low: str, said: str, history: list[tuple[str, str]]) -> str:
    if _vague(low):
        return "Bakmanız yetmez. Sonucu ve benim için ne değişeceğini söyleyin."
    short = said if len(said) <= 70 else said[:69].rstrip() + "…"
    return f"Şunu dediniz: {short} Derdim hâlâ duruyor, somut ne yapacaksınız?"


_BY_KEY = {
    "return_no_receipt": _return_no_receipt,
    "expired_return": _expired_return,
    "defective_exchange": _defective,
    "late_checkin_room_type": _late_checkin,
    "broken_ac": _broken_ac,
    "late_checkout": _late_checkout,
}
