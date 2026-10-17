import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def test_migrations_match_models(tmp_path):
    """Alembic migration'ları modellerle aynı şemayı üretmeli (unutulmuş migration'ı yakalar)."""
    import os
    env = {**os.environ, "PM_DATABASE_URL": f"sqlite:///{tmp_path / 'm.sqlite3'}"}
    alembic = [sys.executable, "-m", "alembic"]
    up = subprocess.run([*alembic, "upgrade", "head"], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert up.returncode == 0, up.stderr
    check = subprocess.run([*alembic, "check"], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr


@pytest.mark.skipif(shutil.which("say") is None, reason="macOS `say` yok")
def test_local_tts_produces_playable_audio(tmp_path):
    from app.core.config import Settings
    from app.services.tts import synthesize

    res = synthesize(Settings(tts_provider="local"), "Merhaba, iade için geldim.", tmp_path / "x")
    assert res is not None and res.path.exists() and res.path.stat().st_size > 1000
    assert res.mime == "audio/mp4" and 500 < res.duration_ms < 10_000
