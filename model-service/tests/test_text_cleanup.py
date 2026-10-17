from app.text_cleanup import strip_thinking


def test_closed_thought_block_removed():
    assert strip_thinking("<|channel>thought\nAnaliz...\n<channel|>Bulamayız.") == "Bulamayız."


def test_unterminated_thought_means_no_answer():
    # sessiz kayıtta görülen gerçek çıktı: düşünme başlıyor, max_new_tokens'ta kesiliyor
    assert strip_thinking("<|channel>thought\nThinking Process:\n1. **Analyze the Request:** The user") == ""


def test_plain_text_untouched():
    assert strip_thinking("  3 hafta yerine 3 gündür.  ") == "3 hafta yerine 3 gündür."
