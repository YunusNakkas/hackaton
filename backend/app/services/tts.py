"""Tur metinlerini yerel Piper veya macOS `say` ile dinlenebilir sese dönüştürür."""

import re
import subprocess
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings


class TtsError(Exception):
    pass


class TtsResult:
    def __init__(self, path: Path, mime: str, duration_ms: int):
        self.path, self.mime, self.duration_ms = path, mime, duration_ms


@lru_cache(maxsize=2)
def _piper_voice(model_path: str):
    from piper import PiperVoice

    return PiperVoice.load(model_path, use_cuda=False)


def voice_for_customer(settings: Settings, customer_name: str) -> str:
    """Senaryodaki 'Bey' erkek, 'Hanım' kadın sesi seçer. Piper tek modeldir, bu ayrım `say` içindir."""
    if re.search(r"\bbey\b", customer_name, re.I):
        return settings.tts_voice_male
    return settings.tts_voice


def synthesize(settings: Settings, text: str, out_path_no_ext: Path, voice: str | None = None) -> TtsResult | None:
    """Sesi üretip `out_path_no_ext` + uzantı olarak kaydeder. Sağlayıcı yoksa None."""
    if settings.tts_provider == "none":
        return None
    out_path_no_ext.parent.mkdir(parents=True, exist_ok=True)
    if settings.tts_provider == "piper":
        if settings.tts_model_path is None:
            raise TtsError("Yerel ses modeli için PM_TTS_MODEL_PATH ayarlanmalı.")
        out = out_path_no_ext.with_suffix(".wav")
        try:
            piper = _piper_voice(str(settings.tts_model_path.resolve()))
            with wave.open(str(out), "wb") as wav_file:
                piper.synthesize_wav(text, wav_file)
            with wave.open(str(out), "rb") as wav_file:
                duration_ms = int(wav_file.getnframes() * 1000 / wav_file.getframerate())
        except Exception as exc:
            raise TtsError(f"Yerel Türkçe ses üretilemedi: {exc}") from exc
        return TtsResult(out, "audio/wav", duration_ms)
    out = out_path_no_ext.with_suffix(".m4a")
    chosen = voice or settings.tts_voice
    with tempfile.TemporaryDirectory() as tmp:
        aiff, wav_path = Path(tmp) / "a.aiff", Path(tmp) / "a.wav"
        try:
            try:
                _say(chosen, text, aiff)
            except (OSError, subprocess.SubprocessError):
                if chosen == settings.tts_voice:
                    raise
                _say(settings.tts_voice, text, aiff)
        except (OSError, subprocess.SubprocessError) as exc:
            raise TtsError(str(exc)) from exc
        try:
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(out)],
                           check=True, capture_output=True, timeout=60)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav_path)],
                           check=True, capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise TtsError(str(exc)) from exc
        with wave.open(str(wav_path)) as w:
            duration_ms = int(w.getnframes() * 1000 / w.getframerate())
    return TtsResult(out, "audio/mp4", duration_ms)


def _say(voice: str, text: str, aiff: Path) -> None:
    # Metin argv ile değil stdin'den verilir; komut satırı enjeksiyonu olmaz.
    subprocess.run(["say", "-v", voice, "-o", str(aiff), "-f", "-"],
                   input=text.encode(), check=True, capture_output=True, timeout=60)
