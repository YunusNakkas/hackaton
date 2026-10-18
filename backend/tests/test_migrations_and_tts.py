import os
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


def test_migrations_upgrade_populated_database(tmp_path):
    """Dolu tabloda batch migration: FK kontrolü açıkken referans alan tablo yeniden kurulamıyordu."""
    import sqlite3

    db = tmp_path / "dolu.sqlite3"
    env = {**os.environ, "PM_DATABASE_URL": f"sqlite:///{db}"}
    alembic = [sys.executable, "-m", "alembic"]
    run = lambda *a: subprocess.run([*alembic, *a], cwd=BACKEND, env=env, capture_output=True, text=True)  # noqa: E731
    assert run("upgrade", "4429862e877f").returncode == 0
    c = sqlite3.connect(db)
    c.executescript("""
        insert into organizations values ('O1', 'org');
        insert into users values ('U1', 'O1', 'a@b.c', 'A', 'employee', 'x', 1, '2026-01-01');
        insert into trainings values ('T1', 'O1', 't', 'retail', 'tr', 'easy', 's', 3, 4, '{}', '[]', '{}',
                                      'a', 'b', 'c', 1, '2026-01-01');
        insert into practice_sessions values ('S1', 'O1', 'T1', 'U1', null, 'r1', 'active', 'customer@1',
                                              '2026-01-01', null);
        insert into turns values ('N1', 'S1', 0, 'customer', 'ready', 'merhaba', null, null, null, '2026-01-01');
    """)
    c.commit()
    c.close()
    up = run("upgrade", "head")
    assert up.returncode == 0, up.stderr[-800:]
    c = sqlite3.connect(db)
    assert c.execute("select count(*) from turns where session_id='S1'").fetchone()[0] == 1
    assert c.execute("select practice_mode from practice_sessions where id='S1'").fetchone() == (None,)
    assert c.execute("select must_change_password from users where id='U1'").fetchone() == (1,)
    assert not c.execute("select name from sqlite_master where name like '_alembic%'").fetchall()
