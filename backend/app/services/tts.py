"""Müşteri sesi üretimi. Şimdilik yalnız macOS `say` (Yelda); bulut sağlayıcı sonra eklenecek."""

import subprocess
import tempfile
import wave
from pathlib import Path

from app.core.config import Settings


class TtsError(Exception):
    pass


class TtsResult:
    def __init__(self, path: Path, mime: str, duration_ms: int):
        self.path, self.mime, self.duration_ms = path, mime, duration_ms


def synthesize(settings: Settings, text: str, out_path_no_ext: Path) -> TtsResult | None:
    """Sesi üretip `out_path_no_ext` + uzantı olarak kaydeder. Sağlayıcı yoksa None."""
    if settings.tts_provider == "none":
        return None
    out_path_no_ext.parent.mkdir(parents=True, exist_ok=True)
    out = out_path_no_ext.with_suffix(".m4a")
    with tempfile.TemporaryDirectory() as tmp:
        aiff, wav_path = Path(tmp) / "a.aiff", Path(tmp) / "a.wav"
        try:
            # Metin argv ile değil stdin'den verilir; komut satırı enjeksiyonu olmaz.
            subprocess.run(["say", "-v", settings.tts_voice, "-o", str(aiff), "-f", "-"],
                           input=text.encode(), check=True, capture_output=True, timeout=60)
            subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(out)],
                           check=True, capture_output=True, timeout=60)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav_path)],
                           check=True, capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise TtsError(str(exc)) from exc
        with wave.open(str(wav_path)) as w:
            duration_ms = int(w.getnframes() * 1000 / w.getframerate())
    return TtsResult(out, "audio/mp4", duration_ms)
