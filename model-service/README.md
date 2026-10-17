# model-service/

Gemma ağırlıklarını bir kez yükleyen FastAPI servisi. Backend worker'ı buraya HTTP ile bağlanır; sözleşme `contracts/model-service.yaml`. Servis domain bilmez; prompt'lar backend'de sürümlü tutulur (`backend/app/services/prompts.py`).

## Runtime seçimi (`PM_RUNTIME`)

| Donanım | Runtime | Model (`PM_MODEL_ID`) | Kurulum |
|---|---|---|---|
| Apple Silicon (önerilen) | `mlx` | `mlx-community/gemma-4-e4b-it-4bit` (5,2 GB) | `pip install -e ".[mlx]"` |
| NVIDIA GPU | `transformers` | `google/gemma-4-E4B-it` veya `-E2B-it` | `pip install -e ".[transformers]"` |
| Apple Silicon, bf16 | `transformers` | `google/gemma-4-E2B-it` (10,2 GB) | 16 GB Mac'te swap yapıyor, önerilmez |

Neden MLX: 16 GB M5'te E4B 4-bit, E2B bf16'dan hem daha doğru hem daha hızlı ve boşta bekledikten sonra yavaşlamıyor. Ölçümler: `docs/s0-spike.md`.

## Çalıştırma

```bash
cd model-service
python3.12 -m venv .venv-mlx && .venv-mlx/bin/pip install -e ".[mlx]"
.venv-mlx/bin/uvicorn app.main:app --port 8100 --env-file ../.env
```

İlk açılış modeli indirir (~5 GB); sonraki açılışlar ~10 sn. `GET /v1/health` 200 dönünce hazırdır.

## Dosyalar

- `app/main.py`: tek uç `POST /v1/generate` (metin + 16 kHz WAV ses).
- `app/adapters/mlx_adapter.py`, `app/adapters/transformers_adapter.py`: aynı arayüz (`load`, `warmup`, `generate`). Transformers cihazı otomatik seçer (CUDA > MPS > CPU), `PM_DEVICE` ile zorlanabilir.
- `app/priority_lock.py`: tek üretim slotu; etkileşimli işler (priority 0) arka plan işlerinin (10) önüne geçer, çalışan üretim kesilmez.

GPU'suz geliştirme için bu servis gerekmez: backend `PM_MODEL_MODE=stub` ile süreç içi sahte modeli kullanır.

## Bilinen sınırlar

- Ses girişi en fazla 30 sn (Gemma 4).
- Değerlendirme sürerken (~30 sn) gelen tur cevabı onun bitmesini bekler.
