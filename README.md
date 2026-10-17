# ProvaMüşteri

İşletmelerin kendi politika ve ölçütleriyle çalışan sesli müşteri provası ve yönetici inceleme platformu.

> Durum: backend P0 uçlarının tamamı çalışıyor: çalışan akışı (giriş → sesli tur → değerlendirme) ve yönetici paneli (özet, çalışanlar, inceleme, atama, Gemma ile taslak). Frontend geliştiriliyor.

## Dizinler

| Dizin | Sahibi | İçerik |
|---|---|---|
| `contracts/` | backend (ortak inceleme) | Web API (`openapi.yaml`), model servisi sözleşmesi, fixture'lar |
| `frontend/` | frontend | React + TS + Vite |
| `backend/` | backend | FastAPI API + worker (SQLite, Alembic) |
| `model-service/` | backend | Gemma'yı bir kez yükleyen servis (MLX 4-bit Mac'te, Transformers NVIDIA'da) |
| `data/` | ortak | Senaryo, politika, rubrik (mağaza + otel, 6 senaryo) |
| `eval/` | backend | S0 ölçümleri, gerçek modelle uçtan uca test |
| `docs/` | ortak | `s0-spike.md` ölçüm sonuçları |

## Mimari

```
tarayıcı ──HTTP/cookie──► API (FastAPI) ──SQLite (jobs tablosu)──► worker ──HTTP──► model-service (Gemma)
                                 ▲                                    │
                                 └──────── ses dosyaları (var/media) ◄┘── TTS (macOS say / Yelda)
```

API uzun model çağrısı yapmaz; işi kuyruğa yazar, `202 + job_id` döner. Worker işler, tarayıcı `GET /jobs/{id}` ile yoklar.

## Yerel geliştirme (macOS)

```bash
cp .env.example .env

# backend (Python 3.11+)
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e . pytest pyyaml "jsonschema[format]" openapi-spec-validator
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --reload --port 8000     # terminal 1: API
.venv/bin/python -m app.worker                          # terminal 2: worker
.venv/bin/pytest -q                                      # testler (GPU'suz, stub model)
```

Demo kullanıcıları (şifre `.env` içindeki `PM_DEMO_PASSWORD`, boşsa `prova1234`):
`mehmet@demo.test` (yönetici), `elif@demo.test`, `can@demo.test` (çalışan).

### Gerçek model

`.env` içinde `PM_MODEL_MODE=real` yapın ve model servisini başlatın (ilk açılış modeli indirir, ~5 GB; sonrakiler ~10 sn):

```bash
cd model-service
python3.12 -m venv .venv-mlx && .venv-mlx/bin/pip install -e ".[mlx]"
.venv-mlx/bin/uvicorn app.main:app --port 8100 --env-file ../.env   # terminal 3
```

Mac'te Gemma 4 E4B 4-bit (MLX, ~5,4 GB) kullanılır; NVIDIA için `model-service/README.md`. Ölçümler: `docs/s0-spike.md`.

Gerçek modelle duman testleri (geçici veritabanı kullanır): `backend/.venv/bin/python eval/e2e_real.py` (sesli oturum), `eval/draft_real.py` (taslak üretimi)

### Frontend için

Frontend geliştirmesi gerçek modeli beklemez: `PM_MODEL_MODE=stub` ile API gerçek davranır, model cevapları `[stub]` etiketlidir. `/api/v1/health` → `model_service: "stub"`.

## Lisans

Henüz seçilmedi. Gemma kullanım koşullarıyla uyumlu bir lisans seçilip `LICENSE` eklenecek.
