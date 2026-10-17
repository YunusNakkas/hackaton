"""Tarayıcı kayıtlarını doğrular ve modele uygun 16 kHz mono WAV'a çevirir (PyAV, sistem ffmpeg'i gerekmez)."""

import io
import wave
from dataclasses import dataclass

import av
import numpy as np

from app.core.errors import ApiError

ALLOWED_MIME = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg"}
TARGET_RATE = 16_000
# Sessizlik eşiği: 100 ms pencerede RMS (int16). Dahili Mac mikrofonunda sessiz oda ~50-200, konuşma ~1000+.
# Sessiz kayıtta hem Gemma hem Whisper metin uyduruyor (gerçek mikrofon denemesi, 2026-10-18).
VOICED_RMS = 300
MIN_VOICED_MS = 300
_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3"}


@dataclass
class DecodedAudio:
    wav_bytes: bytes
    duration_ms: int
    container: str


def base_mime(content_type: str | None) -> str:
    return (content_type or "").split(";")[0].strip().lower()


def extension_for(mime: str) -> str:
    return _EXT.get(mime, "wav")


def voiced_ms(pcm: np.ndarray) -> int:
    win = TARGET_RATE // 10
    n = len(pcm) // win
    if n == 0:
        return 0
    frames = pcm[: n * win].astype(np.float64).reshape(n, win)
    return int((np.sqrt((frames ** 2).mean(axis=1)) > VOICED_RMS).sum() * 100)


def decode_to_wav(data: bytes, *, min_ms: int, max_s: int) -> DecodedAudio:
    try:
        with av.open(io.BytesIO(data)) as container:
            stream = next((s for s in container.streams if s.type == "audio"), None)
            if stream is None:
                raise ApiError(422, "audio_undecodable", "Dosyada ses bulunamadı.")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_RATE)
            chunks = []
            for frame in container.decode(stream):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().reshape(-1))
            fmt = container.format.name
    except ApiError:
        raise
    except Exception as exc:  # PyAV çok çeşitli hata tipleri fırlatır
        raise ApiError(422, "audio_undecodable", "Ses dosyası okunamadı.") from exc

    pcm = np.concatenate(chunks).astype(np.int16) if chunks else np.zeros(0, dtype=np.int16)
    duration_ms = int(len(pcm) * 1000 / TARGET_RATE)
    if duration_ms < min_ms:
        raise ApiError(422, "audio_too_short", "Kayıt çok kısa. Lütfen tekrar konuşun.")
    if duration_ms > max_s * 1000 + 500:  # konteyner yuvarlamasına küçük tolerans
        raise ApiError(422, "audio_too_long", f"Kayıt en fazla {max_s} saniye olabilir.")
    if voiced_ms(pcm) < MIN_VOICED_MS:
        raise ApiError(422, "no_speech", "Ses algılanamadı. Mikrofona yakın konuşup tekrar deneyin.")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TARGET_RATE)
        w.writeframes(pcm.tobytes())
    return DecodedAudio(buf.getvalue(), duration_ms, fmt)
