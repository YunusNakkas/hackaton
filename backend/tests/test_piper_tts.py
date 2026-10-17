import uuid
import wave

import pytest

from app.core.config import Settings, get_settings
from app.services import tts
from app.worker.jobs import run_once
from tests.conftest import CSRF
from tests.test_session_flow import _start


class TestVoice:
    __test__ = False

    def synthesize_wav(self, text, wav):
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\x01\x00" * 22050)


def test_piper_writes_wav_and_reports_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "_piper_voice", lambda path: TestVoice())
    result = tts.synthesize(Settings(tts_provider="piper", tts_model_path=tmp_path / "voice.onnx"),
                            "Merhaba", tmp_path / "nested" / "turn")
    assert result.path.suffix == ".wav" and result.mime == "audio/wav" and result.duration_ms == 1000
    with wave.open(str(result.path), "rb") as wav:
        assert wav.getnframes() == 22050


def test_missing_piper_model_has_clear_error(tmp_path):
    with pytest.raises(tts.TtsError, match="PM_TTS_MODEL_PATH"):
        tts.synthesize(Settings(tts_provider="piper", tts_model_path=None), "Merhaba", tmp_path / "turn")


def test_written_turns_have_audio_and_retry_does_not_duplicate(elif_client, monkeypatch, tmp_path):
    monkeypatch.setenv("PM_TTS_PROVIDER", "piper")
    monkeypatch.setenv("PM_TTS_MODEL_PATH", str(tmp_path / "voice.onnx"))
    get_settings.cache_clear()
    voice = TestVoice()
    monkeypatch.setattr(tts, "_piper_voice", lambda path: voice)
    sid = _start(elif_client)["session"]["id"]
    assert run_once()  # açılış sesi
    accepted = elif_client.post(f"/api/v1/sessions/{sid}/messages", headers=CSRF, json={
        "text": "Fişinizi kontrol edebilir miyim?", "client_request_id": str(uuid.uuid4())}).json()
    original = voice.synthesize_wav
    calls = 0

    def fail_customer_once(text, wav):
        nonlocal calls
        calls += 1
        if calls == 2:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            raise RuntimeError("geçici ses hatası")
        original(text, wav)

    monkeypatch.setattr(voice, "synthesize_wav", fail_customer_once)
    assert run_once()
    job_url = f"/api/v1/jobs/{accepted['job_id']}"
    assert elif_client.get(job_url).json()["error"]["retryable"]
    assert elif_client.post(job_url + "/retry", headers=CSRF).status_code == 202
    assert run_once()
    job = elif_client.get(job_url).json()
    assert job["status"] == "ready", job
    session = elif_client.get(f"/api/v1/sessions/{sid}").json()
    assert len(session["turns"]) == 3
    for turn in session["turns"]:
        assert turn["has_audio"]
        audio = elif_client.get(f"/api/v1/sessions/{sid}/turns/{turn['id']}/audio")
        assert audio.status_code == 200 and audio.headers["content-type"] == "audio/wav"
