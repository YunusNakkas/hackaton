"""Gerçek modelle uçtan uca duman testi: giriş → oturum → 2 sesli tur → bitir → değerlendirme.

Önkoşul: model servisi çalışıyor (localhost:8100). macOS gerekli (çalışan sesi `say` ile üretilir).
Kullanım (repo kökünden): backend/.venv/bin/python eval/e2e_real.py
Geçici veritabanı kullanır; geliştirme veritabanına dokunmaz.
"""

import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pm-e2e-"))
os.environ.update(PM_ENV="test", PM_DATABASE_URL=f"sqlite:///{TMP / 'e2e.sqlite3'}", PM_MEDIA_DIR=str(TMP / "media"),
                  PM_MODEL_MODE="real", PM_TTS_PROVIDER="local")
sys.path.insert(0, str(ROOT / "backend"))

import app.models  # noqa: E402,F401
from app.db import Base, get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed  # noqa: E402
from app.worker.jobs import run_once  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CSRF = {"X-Requested-With": "provamusteri"}
EMPLOYEE_LINES = [
    "Merhaba Ayşe Hanım, yaşadığınız durumu anlıyorum. Kart ekstrenizle satın alma kaydınızı hemen bulabiliriz.",
    "Kayıt bulunursa iade kartınıza yapılır ve üç iş günü içinde hesabınıza yansır.",
]


def say_m4a(text: str, out: Path) -> bytes:
    aiff = out.with_suffix(".aiff")
    subprocess.run(["say", "-v", "Yelda", "-o", str(aiff), text], check=True)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(out)], check=True)
    return out.read_bytes()


def drain(label: str) -> float:
    t0 = time.perf_counter()
    while run_once():
        pass
    secs = time.perf_counter() - t0
    print(f"  {label}: {secs:.1f} sn")
    return secs


def main() -> None:
    Base.metadata.create_all(get_engine())
    with get_sessionmaker()() as db:
        seed(db, "e2e-sifre")
    c = TestClient(create_app())
    login = {"email": "elif@demo.test", "password": "e2e-sifre"}
    assert c.post("/api/v1/auth/login", headers=CSRF, json=login).status_code == 200
    h = c.get("/api/v1/health").json()
    print("health:", h)
    assert h["model_service"] == "up", "model servisi çalışmıyor"

    training = next(t for t in c.get("/api/v1/trainings").json()["items"] if t["title"] == "Fişsiz iade talebi")
    created = c.post("/api/v1/sessions", headers=CSRF,
                     json={"training_id": training["id"], "client_request_id": str(uuid.uuid4())}).json()
    sid = created["session"]["id"]
    print(f"\nmüşteri (açılış): {created['session']['turns'][0]['text']}")
    drain("açılış sesi (TTS)")

    for i, line in enumerate(EMPLOYEE_LINES):
        audio = say_m4a(line, TMP / f"emp{i}.m4a")
        r = c.post(f"/api/v1/sessions/{sid}/turns", headers=CSRF, data={"client_request_id": str(uuid.uuid4())},
                   files={"audio": (f"emp{i}.m4a", audio, "audio/mp4")})
        assert r.status_code == 202, r.text
        print(f"\nçalışan (söylenen): {line}")
        drain("tur (ASR + cevap + TTS)")
        job = c.get(f"/api/v1/jobs/{r.json()['job_id']}").json()
        assert job["status"] == "ready", job
        res = job["result"]
        print(f"çalışan (ASR):      {res['employee_turn']['text']}")
        print(f"müşteri:            {res['customer_turn']['text']}  (ses={res['customer_turn']['has_audio']}, "
              f"bitir={res['session_should_end']})")

    assert c.post(f"/api/v1/sessions/{sid}/finish", headers=CSRF).status_code == 202
    print()
    drain("değerlendirme")
    ev = c.get(f"/api/v1/sessions/{sid}/evaluation").json()
    print(f"\ndeğerlendirme durumu: {ev['status']}")
    if ev["report"]:
        rep = ev["report"]
        for d in rep["dimensions"]:
            evid = ", ".join(f"{'✓' if e['verified'] else '✗'} \"{e['quote'][:50]}\"" for e in d["evidence"])
            print(f"  {d['dimension_id']:16} {d['score']}  {evid}")
        print(f"  toplam: {rep['total']}  bayraklar: {rep['flags']}  onarım: {rep['model_run']['repaired']}")
        print(f"  gelişim: {rep['improvements'][:2]}")
    else:
        print("  hata:", ev["error"])
    print(f"\ngeçici dosyalar: {TMP}")


if __name__ == "__main__":
    main()
