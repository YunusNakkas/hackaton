# model-service/

Gemma ağırlıklarını bir kez yükleyen FastAPI servisi. Backend worker'ı buraya HTTP ile bağlanır; sözleşme `contracts/model-service.yaml`.

- `app/main.py`: tek uç `POST /v1/generate` (metin + 16 kHz WAV ses). Servis domain bilmez; prompt'lar backend'de sürümlü (`backend/app/services/prompts.py`).
- `app/adapters/transformers_adapter.py`: Transformers runtime. Cihaz otomatik seçilir (CUDA > MPS > CPU), `PM_DEVICE` ile zorlanabilir. Aynı kod Mac ve NVIDIA'da çalışır.
- `app/priority_lock.py`: tek üretim slotu; etkileşimli işler (priority 0) arka plan işlerinin (10) önüne geçer, çalışan üretim kesilmez.

GPU'suz geliştirme için bu servis gerekmez: backend `PM_MODEL_MODE=stub` ile süreç içi sahte modeli kullanır.

## Bilinen sınırlar (16 GB Mac)

- E2B bf16 ~10,2 GB. Boşta kalınca ağırlıkların bir kısmı swap'e gidiyor; sonraki ilk çağrı 14–40 sn sürebiliyor. 4-bit sürüm denenecek.
- Ses girişi en fazla 30 sn.
