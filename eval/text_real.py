"""Gerçek modelle yazılı prova, rapor ve taslak duman testi; geçici DB kullanır.

Proje kökünden: backend/.venv/Scripts/python.exe eval/text_real.py
Model servisi önceden hazır olmalıdır. Mevcut uygulama verileri değiştirilmez.
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    (ROOT / "var").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="text-real-", dir=ROOT / "var") as temp:
        os.environ.update(PM_DATABASE_URL=f"sqlite:///{Path(temp) / 'test.sqlite3'}",
                          PM_MEDIA_DIR=str(Path(temp) / "media"), PM_MODEL_MODE="real", PM_TTS_PROVIDER="none")
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
            seed(db, "smoke-test-only-123")
        model = get_model_client(get_settings())
        headers = {"X-Requested-With": "provamusteri"}
        try:
            with TestClient(create_app()) as client:
                response = client.post("/api/v1/auth/login", headers=headers,
                                       json={"email": "elif@demo.test", "password": "smoke-test-only-123"})
                assert response.status_code == 200, response.text
                training = client.get("/api/v1/trainings?sector=retail").json()["items"][0]
                response = client.post("/api/v1/sessions", headers=headers,
                                       json={"training_id": training["id"], "client_request_id": str(uuid.uuid4())})
                assert response.status_code == 201, response.text
                sid = response.json()["session"]["id"]
                response = client.post(f"/api/v1/sessions/{sid}/messages", headers=headers, json={
                    "text": "Merhaba, yaşadığınız sorun için üzgünüm. Fişinizi veya kart ekstrenizi kontrol ederek işletmemizin kurallarına uygun çözüm bulabiliriz.",
                    "client_request_id": str(uuid.uuid4()),
                })
                assert response.status_code == 202, response.text
                print("Gerçek müşteri yanıtı üretiliyor…", flush=True)
                assert run_once(model=model)
                job = client.get("/api/v1/jobs/" + response.json()["job_id"]).json()
                assert job["status"] == "ready", job
                customer = job["result"]["customer_turn"]["text"]
                print(f"Müşteri: {customer}", flush=True)
                assert customer and "[stub]" not in customer

                response = client.post(f"/api/v1/sessions/{sid}/finish", headers=headers)
                assert response.status_code == 202, response.text
                print("Gerçek değerlendirme üretiliyor…", flush=True)
                assert run_once(model=model)
                evaluation = client.get(f"/api/v1/sessions/{sid}/evaluation").json()
                assert evaluation["status"] in ("ready", "needs_review"), evaluation
                assert evaluation["report"]["model_run"]["runtime"] != "stub", evaluation
                print(f"Rapor: {evaluation['status']}; model={evaluation['report']['model_run']}", flush=True)

                response = client.post("/api/v1/auth/login", headers=headers,
                                       json={"email": "mehmet@demo.test", "password": "smoke-test-only-123"})
                assert response.status_code == 200, response.text
                response = client.post("/api/v1/admin/training-drafts", headers=headers, json={"form": {
                    "business_name": "Yerel Test İşletmesi", "sector": "retail", "language": "tr",
                    "policies": [{"title": "Değişim", "body": "Fişli ürünler 14 gün içinde değiştirilebilir."}],
                    "customer_situations": ["Ürününü değiştirmek isteyen müşteri"],
                    "must_do": ["Fişi kontrol et"], "must_not_do": ["Politika dışında söz verme"],
                    "escalation_rule": None, "scenario_count": 1,
                }})
                assert response.status_code == 202, response.text
                did = response.json()["id"]
                print("Gerçek eğitim taslağı üretiliyor…", flush=True)
                assert run_once(model=model)
                draft = client.get(f"/api/v1/admin/training-drafts/{did}").json()
                assert draft["status"] == "ready", draft
                assert len(draft["content"]["scenarios"]) == draft["form"]["scenario_count"], draft
                print(f"Taslak: {draft['content']['scenarios'][0]['title']}", flush=True)
                print("Gerçek modelle üç akış başarılı.", flush=True)
        finally:
            get_engine().dispose()


if __name__ == "__main__":
    main()
