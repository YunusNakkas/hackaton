import io
import math
from pathlib import Path

import av
import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

SPEC = yaml.safe_load((Path(__file__).resolve().parents[2] / "contracts/openapi.yaml").read_text(encoding="utf-8"))
CSRF = {"X-Requested-With": "provamusteri"}
PASSWORD = "test-sifre-123"


def assert_contract(schema_name: str, body) -> None:
    """Yanıtı contracts/openapi.yaml içindeki şemaya karşı doğrular."""
    root = {**SPEC, "$ref": f"#/components/schemas/{schema_name}"}
    errors = sorted(Draft202012Validator(root, format_checker=FormatChecker()).iter_errors(body), key=str)
    assert not errors, "\n".join(f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in errors)


def make_audio(seconds: float = 2.0, fmt: str = "webm") -> bytes:
    """Gerçek tarayıcı kaydı gibi opus/webm (veya wav) üretir; çözme yolu gerçekten test edilir."""
    rate = 48_000
    t = np.arange(int(rate * seconds)) / rate
    pcm = (0.3 * np.sin(2 * math.pi * 220 * t) * 32767).astype(np.int16)
    buf = io.BytesIO()
    codec = "libopus" if fmt == "webm" else "pcm_s16le"
    with av.open(buf, "w", format=fmt) as out:
        stream = out.add_stream(codec, rate=rate, layout="mono")
        for start in range(0, len(pcm), 960):
            chunk = pcm[start:start + 960]
            frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout="mono")
            frame.rate = rate
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    return buf.getvalue()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_ENV", "test")
    monkeypatch.setenv("PM_DATABASE_URL", f"sqlite:///{tmp_path / 'test.sqlite3'}")
    monkeypatch.setenv("PM_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("PM_MODEL_MODE", "stub")
    monkeypatch.setenv("PM_TTS_PROVIDER", "none")

    from app import db as dbmod
    from app.core import config
    from app.core.security import login_limiter
    from app.services import model_client

    for fn in (config.get_settings, dbmod.get_engine, dbmod.get_sessionmaker):
        fn.cache_clear()
    model_client._stub_singleton = None
    login_limiter._fails.clear()

    import app.models  # noqa: F401
    dbmod.Base.metadata.create_all(dbmod.get_engine())
    from app.seed import seed

    with dbmod.get_sessionmaker()() as s:
        seed(s, PASSWORD)
    yield tmp_path
    dbmod.get_engine().dispose()
    for fn in (config.get_settings, dbmod.get_engine, dbmod.get_sessionmaker):
        fn.cache_clear()


def _client(email: str) -> TestClient:
    from app.main import create_app

    c = TestClient(create_app())
    res = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}, headers=CSRF)
    assert res.status_code == 200, res.text
    return c


@pytest.fixture()
def elif_client(env):
    return _client("elif@demo.test")


@pytest.fixture()
def can_client(env):
    return _client("can@demo.test")


@pytest.fixture()
def manager_client(env):
    return _client("mehmet@demo.test")


@pytest.fixture()
def anon_client(env):
    from app.main import create_app

    return TestClient(create_app())
