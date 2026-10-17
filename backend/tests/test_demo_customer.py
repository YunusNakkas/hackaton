from app.services.demo_customer import reply

HOTEL = {"key": "late_checkin_room_type"}
RETAIL = {"key": "return_no_receipt"}


def test_late_guest_blame_is_rejected_even_without_turkish_letters():
    said = "sizin gec gelmis olmaniz yuzunden sistem sizi dusuruyor rezervasyon bosa dusuyor"
    text = reply(HOTEL, said, [])
    assert "deniz" in text.lower()
    assert "düşmez" in text.lower() or "dusmez" in text.lower()


def test_only_checking_asks_for_the_room_result():
    text = reply(HOTEL, "Hemen kontrol ediyorum efendim", [])
    assert "deniz" in text.lower()
    assert "nerede" in text.lower()


def test_upgrade_offer_is_accepted():
    text = reply(HOTEL, "Bu gece ücretsiz üst kategori oda verebiliriz", [])
    assert "kabul" in text.lower()


def test_gift_card_is_refused_on_a_return():
    text = reply(RETAIL, "Fiş olmadığı için hediye çeki düzenleyebiliriz", [])
    assert "hediye çeki istemiyorum" in text.lower()
