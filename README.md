# ProvaMüşteri

İşletmelerin kendi politika ve ölçütleriyle çalışan sesli müşteri provası ve yönetici inceleme platformu.

> Durum: iskelet. Henüz çalışan özellik yok.

## Dizinler

| Dizin | Sahibi | İçerik |
|---|---|---|
| `contracts/` | backend (ortak inceleme) | OpenAPI, fixture'lar, doğrulama scripti |
| `frontend/` | frontend | React + TS + Vite |
| `backend/` | backend | FastAPI API + worker (SQLite) |
| `model-service/` | backend | Gemma wrapper (ASR, müşteri rolü, değerlendirme, taslak) + GPU'suz stub |
| `data/` | ortak | Senaryo, politika, rubrik, golden set |
| `eval/` | backend | Offline model değerlendirme |
| `docs/` | ortak | Kurulum, demo, teslim |

## Geliştirme

```bash
# sözleşme doğrulama
python contracts/scripts/validate_fixtures.py

# backend (Python 3.11+; uv yoksa venv)
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e . pytest pyyaml "jsonschema[format]" openapi-spec-validator
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health
.venv/bin/pytest -q

# compose (api + worker, model servisi stub)
cp .env.example .env && docker compose up
```

## Lisans

Henüz seçilmedi. Gemma kullanım koşullarıyla uyumlu bir lisans seçilip `LICENSE` eklenecek.
