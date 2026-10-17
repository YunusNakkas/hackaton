"""Gerçek modelle taslak üretimi: yönetici formu → Gemma → doğrulanmış senaryo + rubrik.

Önkoşul: model servisi çalışıyor (localhost:8100).
Kullanım (repo kökünden): backend/.venv/bin/python eval/draft_real.py [--runs 2]
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pm-draft-"))
os.environ.update(PM_ENV="test", PM_DATABASE_URL=f"sqlite:///{TMP / 'd.sqlite3'}", PM_MEDIA_DIR=str(TMP / "media"),
                  PM_MODEL_MODE="real", PM_TTS_PROVIDER="none")
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.db import Base, get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed  # noqa: E402
from app.worker.jobs import run_once  # noqa: E402

CSRF = {"X-Requested-With": "provamusteri"}
FORM = {
    "business_name": "Kahve Durağı", "sector": "cafe", "language": "tr",
    "policies": [
        {"title": "Yanlış sipariş", "body": "Yanlış hazırlanan içecek ücretsiz ve öncelikli olarak yeniden yapılır. "
                                            "Para iadesi yalnızca vardiya sorumlusu onayıyla yapılır."},
        {"title": "Sadakat kartı", "body": "Her 10 kahvede 1 kahve bedavadır. Kart kaybolursa puanlar telefon "
                                           "numarasıyla geri yüklenir."},
        {"title": "Alerjen", "body": "Çalışan alerjen içermediğini garanti edemez; içerik listesini gösterir."},
    ],
    "customer_situations": ["Siparişi yanlış hazırlanan ve acelesi olan müşteri",
                            "Fıstık alerjisi olduğunu söyleyen müşteri"],
    "must_do": ["Özür dile", "İçerik listesini göster"],
    "must_not_do": ["Alerjen içermediğini garanti etme", "Onaysız para iadesi vaat etme"],
    "escalation_rule": "Para iadesi isteyen müşteriyi vardiya sorumlusuna yönlendir.",
    "scenario_count": 2,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()
    Base.metadata.create_all(get_engine())
    with get_sessionmaker()() as db:
        seed(db, "draft-sifre")
    c = TestClient(create_app())
    login = {"email": "mehmet@demo.test", "password": "draft-sifre"}
    assert c.post("/api/v1/auth/login", headers=CSRF, json=login).status_code == 200
    assert c.get("/api/v1/health").json()["model_service"] == "up", "model servisi çalışmıyor"

    for run in range(args.runs):
        d = c.post("/api/v1/admin/training-drafts", headers=CSRF, json={"form": FORM}).json()
        t0 = time.perf_counter()
        while run_once():
            pass
        secs = time.perf_counter() - t0
        d = c.get(f"/api/v1/admin/training-drafts/{d['id']}").json()
        job = c.get(f"/api/v1/jobs/{d['generation_job_id']}").json()
        print(f"\n=== koşu {run + 1}: {d['status']} ({secs:.1f} sn, deneme {job['attempt']})")
        if d["status"] != "ready":
            print("  hata:", job["error"])
            continue
        for s in d["content"]["scenarios"]:
            cu = s["customer"]
            print(f"  [{s['difficulty']}] {s['title']} — {cu['name']}, {cu['mood']}")
            print(f"     açılış: {s['opening_line']}")
            print(f"     gizli hedef: {cu['hidden_goal']}")
            print(f"     ölçütler: {s['success_criteria']}  görünür politika: {s['visible_policy_ids']}")
        print("  rubrik:", [(x["id"], x["name"]) for x in d["content"]["rubric"]["dimensions"]])
        print("  uyarılar:", d["warnings"])
        if run == 0:
            pub = c.post(f"/api/v1/admin/training-drafts/{d['id']}/publish", headers=CSRF,
                         json={"version": d["version"]})
            print("  yayımlandı:", pub.status_code, [t["title"] for t in pub.json()["trainings"]])


if __name__ == "__main__":
    main()
