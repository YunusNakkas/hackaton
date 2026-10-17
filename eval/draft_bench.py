"""Taslak üretimi kalite ölçümü: 5 farklı işletme formu × N koşu, gerçek modelle.

Ölçülenler: geçerli taslak oranı, istenen senaryo sayısına uyum, kullanıcıya görünen metinlere
sızan iç politika kimlikleri ("policy_1", "Politika_2"…), süre. Türkçe kalitesi otomatik
ölçülemediği için her koşunun metinleri rapora yazılır, elle incelenir.

Önkoşul: model servisi çalışıyor (localhost:8100).
Kullanım (repo kökünden): backend/.venv/bin/python eval/draft_bench.py --label once --runs 2
Çıktı: var/draft-bench/<label>.json
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pm-draftbench-"))
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
OUT = ROOT / "var/draft-bench"
ID_LEAK = re.compile(r"\bpolicy_\d+\b|\bpolitika[_ ]?\d+\b|\[policy", re.I)


def form(name, sector, policies, situations, must_do, must_not, escalation, count):
    return {"business_name": name, "sector": sector, "language": "tr",
            "policies": [{"title": t, "body": b} for t, b in policies], "customer_situations": situations,
            "must_do": must_do, "must_not_do": must_not, "escalation_rule": escalation, "scenario_count": count}


FORMS = [
    form("Kahve Durağı", "cafe",
         [("Yanlış sipariş", "Yanlış hazırlanan içecek ücretsiz ve öncelikli yeniden yapılır. Para iadesi yalnızca vardiya sorumlusu onayıyla yapılır."),
          ("Sadakat kartı", "Her 10 kahvede 1 kahve bedava. Kart kaybolursa puanlar telefon numarasıyla geri yüklenir."),
          ("Alerjen", "Çalışan alerjen içermediğini garanti edemez; içerik listesini gösterir.")],
         ["Siparişi yanlış hazırlanan acelesi olan müşteri", "Fıstık alerjisi olan müşteri"],
         ["Özür dile", "İçerik listesini göster"], ["Alerjen garantisi verme", "Onaysız para iadesi vaat etme"],
         "Para iadesi isteyen müşteriyi vardiya sorumlusuna yönlendir.", 2),
    form("Yıldız Eczanesi", "pharmacy",
         [("Reçeteli ilaç", "Reçete gerektiren ilaç reçetesiz verilmez. E-reçete numarası ve T.C. kimlik numarası gerekir."),
          ("İade", "Açılmış ilaç ve soğuk zincir ürünleri iade alınmaz. Açılmamış dermokozmetik ürünler 14 gün içinde fişle iade edilir.")],
         ["Reçetesiz antibiyotik isteyen müşteri", "Açılmış kremi iade etmek isteyen müşteri", "Stokta olmayan ilacı soran müşteri"],
         ["Nedenini açıkla", "Alternatif öner (doktora yönlendirme, sipariş)"], ["Teşhis koyma", "Reçeteli ilacı reçetesiz verme"],
         None, 3),
    form("Mavi Kargo Şubesi", "logistics",
         [("Gecikme", "Teslimat 3 iş gününü aşarsa müşteri kargo ücretinin iadesini talep edebilir. İade 5 iş gününde yapılır."),
          ("Hasarlı paket", "Hasarlı paket teslim alınırken tutanak tutulur. Tutanak yoksa hasar talebi kabul edilmez.")],
         ["Kargosu 5 gündür gelmeyen müşteri", "Hasarlı paketi tutanaksız teslim almış müşteri"],
         ["Takip numarasını sor", "Net süre ver"], ["Kesin teslim saati vaat etme"],
         "Hasar tazminatı taleplerini bölge müdürlüğüne ilet.", 2),
    form("Form Spor Salonu", "gym",
         [("Üyelik dondurma", "Yıllık üyelikte yılda bir kez, en fazla 30 gün dondurma yapılabilir. Sağlık raporuyla 60 güne çıkar."),
          ("İptal", "Üyelik iptalinde kalan ayların ücretinin %50'si iade edilir. İlk 7 günde tam iade yapılır.")],
         ["Ameliyat olacağı için üyeliğini dondurmak isteyen üye", "Taşındığı için üyeliğini iptal etmek isteyen üye"],
         ["Seçenekleri karşılaştırmalı anlat"], ["Kural dışı indirim vaat etme"], None, 2),
    form("Kent Bank Şubesi", "bank",
         [("Kart aidatı", "Kart aidatı iadesi yalnızca son 12 ay içinde ve müşterinin yazılı talebiyle yapılır."),
          ("Kayıp kart", "Kayıp kart hemen bloke edilir. Yeni kart 5 iş gününde adrese gönderilir. Acil durumda şubeden aynı gün geçici kart verilir.")],
         ["Kartını kaybetmiş ve yurt dışına çıkacak müşteri", "Kart aidatına itiraz eden müşteri"],
         ["Kimlik doğrula", "Kartı hemen bloke et"], ["Şifre sorma"], "Aidat itirazlarını müşteri hizmetlerine yönlendir.", 1),
]


def user_texts(scn: dict) -> list[str]:
    c = scn["customer"]
    return [scn["title"], scn["summary"], scn["opening_line"], c["context"], c["mood"], c["hidden_goal"],
            *scn["success_criteria"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()
    Base.metadata.create_all(get_engine())
    with get_sessionmaker()() as db:
        seed(db, "bench")
    c = TestClient(create_app())
    assert c.post("/api/v1/auth/login", headers=CSRF, json={"email": "mehmet@demo.test", "password": "bench"}).status_code == 200
    assert c.get("/api/v1/health").json()["model_service"] == "up", "model servisi çalışmıyor"

    rows = []
    for f in FORMS:
        for run in range(args.runs):
            d = c.post("/api/v1/admin/training-drafts", headers=CSRF, json={"form": f}).json()
            t0 = time.perf_counter()
            while run_once():
                pass
            secs = time.perf_counter() - t0
            d = c.get(f"/api/v1/admin/training-drafts/{d['id']}").json()
            job = c.get(f"/api/v1/jobs/{d['generation_job_id']}").json()
            row = {"business": f["business_name"], "run": run, "status": d["status"], "seconds": round(secs, 1),
                   "attempt": job["attempt"], "requested": f["scenario_count"], "warnings": d["warnings"]}
            if d["status"] == "ready":
                scns = d["content"]["scenarios"]
                leaks = [t for s in scns for t in user_texts(s) if ID_LEAK.search(t)]
                row.update(produced=len(scns), count_ok=len(scns) == f["scenario_count"], id_leaks=leaks,
                           dims=[x["name"] for x in d["content"]["rubric"]["dimensions"]],
                           scenarios=[{"title": s["title"], "opening_line": s["opening_line"],
                                       "hidden_goal": s["customer"]["hidden_goal"], "criteria": s["success_criteria"],
                                       "visible": s["visible_policy_ids"]} for s in scns])
            rows.append(row)
            print(f"{f['business_name']:18} #{run} {d['status']:6} {secs:5.1f}s istenen={f['scenario_count']} "
                  f"üretilen={row.get('produced', '-')} sızıntı={len(row.get('id_leaks', []))} uyarı={len(d['warnings'])}",
                  flush=True)

    ready = [r for r in rows if r["status"] == "ready"]
    summary = {
        "label": args.label, "n": len(rows), "ready_rate": round(len(ready) / len(rows), 2),
        "count_ok_rate": round(sum(r["count_ok"] for r in ready) / max(1, len(ready)), 2),
        "drafts_with_id_leak": sum(bool(r["id_leaks"]) for r in ready),
        "leaked_texts": sum(len(r["id_leaks"]) for r in ready),
        "median_s": sorted(r["seconds"] for r in rows)[len(rows) // 2],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{args.label}.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print("\nÖZET", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
