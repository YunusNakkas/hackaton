"""Mehmet → taslak → atama → Can → sesli inceleme → puan düzeltme.

backend/.venv/Scripts/python.exe eval/manager_flow_real.py
Gerçek model servisi ve PM_TTS_MODEL_PATH gerekir. Geçici DB/media kullanır.
"""
import io
import os
import sys
import tempfile
import uuid
import wave
from contextlib import nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    (ROOT / "var").mkdir(exist_ok=True)
    # İsteğe bağlı çıktı klasörü, aynı test verisini tarayıcıda incelemek içindir.
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
        if (output / "test.sqlite3").exists():
            raise SystemExit("Yeni ve boş bir çıktı klasörü seçin.")
    with (nullcontext(str(output)) if output else tempfile.TemporaryDirectory(prefix="manager-flow-", dir=ROOT / "var")) as temp:
        os.environ.update(PM_DATABASE_URL=f"sqlite:///{Path(temp) / 'test.sqlite3'}",
                          PM_MEDIA_DIR=str(Path(temp) / "media"), PM_MODEL_MODE="real", PM_TTS_PROVIDER="piper")
        from fastapi.testclient import TestClient
        from app import models  # noqa: F401
        from app.core.config import get_settings
        from app.db import Base, get_engine, get_sessionmaker
        from app.main import create_app
        from app.seed import seed
        from app.services.model_client import get_model_client
        from app.worker.jobs import run_once

        Base.metadata.create_all(get_engine())
        with get_sessionmaker()() as db:
            seed(db, "manager-flow-test-only")
        model = get_model_client(get_settings())
        headers = {"X-Requested-With": "provamusteri"}

        def request(client, method, path, expected=200, body=None):
            response = client.request(method, f"/api/v1{path}", headers=headers, **({"json": body} if body is not None else {}))
            assert response.status_code == expected, response.text
            return response.json()

        def login(client, email):
            request(client, "POST", "/auth/login", body={"email": email, "password": "manager-flow-test-only"})

        try:
            with TestClient(create_app()) as manager, TestClient(create_app()) as can:
                login(manager, "mehmet@demo.test")
                login(can, "can@demo.test")
                request(can, "GET", "/admin/overview", expected=403)
                print("Mehmet yönetici; Can yönetici uçlarına giremiyor.", flush=True)
                draft = request(manager, "POST", "/admin/training-drafts", 202, {"form": {
                    "business_name": "Akış Testi", "sector": "retail", "language": "tr",
                    "policies": [{"title": "Değişim", "body": "Fişli ürünler 14 gün içinde değiştirilebilir."}],
                    "customer_situations": ["Ürününü değiştirmek isteyen müşteri"],
                    "must_do": ["Fişi kontrol et"], "must_not_do": ["Politika dışında söz verme"],
                    "escalation_rule": None, "scenario_count": 1,
                }})
                print("Gerçek model taslağı üretiyor…", flush=True)
                assert run_once(model=model)
                url = f"/admin/training-drafts/{draft['id']}"
                draft = request(manager, "GET", url)
                assert draft["status"] == "ready", draft
                content = draft["content"]
                content["scenarios"][0]["title"] = "Akış testi: fişli değişim"
                updated = request(manager, "PATCH", url, body={"version": draft["version"], "content": content})
                conflict = request(manager, "PATCH", url, 409, {"version": draft["version"], "content": content})
                assert conflict["error"]["code"] == "version_mismatch"
                request(manager, "POST", url + "/publish", 409, {"version": draft["version"]})
                published = request(manager, "POST", url + "/publish", body={"version": updated["version"]})
                tid = published["draft"]["published_training_ids"][0]
                assert request(manager, "POST", url + "/publish", body={"version": updated["version"]})["draft"]["published_training_ids"] == [tid]
                print("Taslak düzenleme, kaydetme/yayımlama 409 ve tekrarlı yayımlama başarılı.", flush=True)
                employee_id = request(can, "GET", "/me")["user"]["id"]
                assignment = request(manager, "POST", "/admin/assignments", 201, {
                    "training_id": tid, "employee_ids": [employee_id], "due_at": "2026-10-25T18:00:00Z",
                })["created"][0]
                assert any(a["id"] == assignment["id"] for a in request(can, "GET", "/assignments")["items"])
                session = request(can, "POST", "/sessions", 201, {"training_id": tid,
                    "assignment_id": assignment["id"], "client_request_id": str(uuid.uuid4())})["session"]
                sid = session["id"]
                assert run_once(model=model)  # açılış sesi
                for text in ["Merhaba, yaşadığınız sorun için üzgünüm. Fişinizi kontrol edebilir miyim?",
                             "Fişiniz varsa 14 gün içinde değişim yapabiliriz. Size uygun ürünü birlikte seçebiliriz."]:
                    request(can, "POST", f"/sessions/{sid}/messages", 202, {"text": text, "client_request_id": str(uuid.uuid4())})
                    assert run_once(model=model)
                session = request(manager, "GET", f"/sessions/{sid}")
                assert len(session["turns"]) == 5, session
                for turn in session["turns"]:
                    assert turn["has_audio"], turn
                    audio_url = f"/api/v1/sessions/{sid}/turns/{turn['id']}/audio"
                    audio = manager.get(audio_url)
                    assert audio.status_code == 200 and "audio/wav" in audio.headers["content-type"]
                    with wave.open(io.BytesIO(audio.content), "rb") as wav:
                        assert wav.getnframes() > wav.getframerate() / 2
                    partial = manager.get(audio_url, headers={"Range": "bytes=0-99"})
                    assert partial.status_code == 206 and partial.content == audio.content[:100]
                print("Can provayı yaptı; tüm 5 turda oynatılabilir WAV ve Range yanıtı doğrulandı.", flush=True)
                request(can, "POST", f"/sessions/{sid}/finish", 202)
                assert run_once(model=model)
                report = request(manager, "GET", f"/sessions/{sid}/evaluation")["report"]
                assert report and report["model_run"]["runtime"] != "stub"
                dimension = report["dimensions"][0]
                new_score = 1 if dimension["score"] != 1 else 2
                review = request(manager, "POST", f"/admin/sessions/{sid}/reviews", 201, {
                    "decision": "adjusted", "comment": "Transkript ve tur sesleri incelendi.",
                    "adjustments": [{"dimension_id": dimension["dimension_id"], "score": new_score,
                                     "reason": "İlk turda müşterinin durumunu kabul etti; açıklama daha somut olabilir."}],
                })
                visible = request(can, "GET", f"/sessions/{sid}/evaluation")["report"]
                assert visible["manager_review"]["id"] == review["id"]
                assert visible["manager_review"]["adjustments"][0]["score"] == new_score
                assert visible["dimensions"] == report["dimensions"]
                assert request(can, "GET", f"/sessions/{sid}")["review_status"] == "reviewed"
                assert next(a for a in request(can, "GET", "/assignments")["items"] if a["id"] == assignment["id"])["status"] == "completed"
                print("Mehmet puanı gerekçeyle düzeltti; Can güncellenmiş raporu gördü. Atama tamamlandı.", flush=True)
                print("AKIŞ BAŞARILI", flush=True)
                if output:
                    (output / "session-id.txt").write_text(sid, encoding="utf-8")
        finally:
            get_engine().dispose()


if __name__ == "__main__":
    main()
