import re

# Gemma 4 düşünme kanalı: <|channel>thought ... <channel|>cevap
# enable_thinking=False olsa da E4B belirsiz girdide (ör. sessiz ses) düşünme bloğu üretebiliyor.
_THOUGHT_BLOCK = re.compile(r"<\|channel>.*?<channel\|>", re.S)
_THOUGHT_START = "<|channel>"


def strip_thinking(text: str) -> str:
    """Kapanmış düşünme bloklarını siler; kapanmamış blok varsa ondan sonrasını atar (cevap yok demektir)."""
    text = _THOUGHT_BLOCK.sub("", text)
    if _THOUGHT_START in text:
        text = text.split(_THOUGHT_START, 1)[0]
    return text.strip()
