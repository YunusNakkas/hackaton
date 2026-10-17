# model-service/

Gemma ağırlıklarını bir kez yükleyen FastAPI servisi. Backend worker'ı buraya HTTP ile bağlanır; sözleşme `contracts/model-service.yaml`. Servis domain bilmez; prompt'lar backend'de sürümlü tutulur (`backend/app/services/prompts.py`).

## Runtime seçimi (`PM_RUNTIME`)

| Donanım | Runtime | Model (`PM_MODEL_ID`) | Kurulum |
|---|---|---|---|
| Apple Silicon (önerilen) | `mlx` | `mlx-community/gemma-4-e4b-it-4bit` (5,2 GB) | `pip install -e ".[mlx]"` |
| NVIDIA GPU | `transformers` | `google/gemma-4-E4B-it` veya `-E2B-it` | `pip install -e ".[transformers]"` |
| Windows, sınırlı GPU belleği | `ollama` | `gemma4:e2b` (sıkıştırılmış) | Ollama + temel Python bağımlılıkları |
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

## Windows: yerel Ollama ile yazılı prova

Ollama'nın resmî Windows standalone paketini çalışma alanındaki `tools/ollama/` klasörüne açın. Model dosyalarını aynı klasörün `models/` altına indirin:

```powershell
$env:OLLAMA_MODELS = 'D:\hck\tools\ollama\models'
# Önce ayrı bir terminalde: D:\hck\tools\ollama\ollama.exe serve
D:\hck\tools\ollama\ollama.exe pull gemma4:e2b
# Proje kökünden, ek ağırlık indirmeden yalnız metin tanımı oluşturun:
.\model-service\prepare-ollama-text.ps1
```

Proje `.env` ayarları:

```dotenv
PM_MODEL_MODE=real
PM_MODEL_SERVICE_URL=http://127.0.0.1:8100
PM_RUNTIME=ollama
PM_MODEL_ID=gemma4-e2b-text:latest
PM_OLLAMA_URL=http://127.0.0.1:11434
PM_OLLAMA_CONTEXT_LENGTH=8192
PM_MODEL_TIMEOUT_S=600
PM_TTS_PROVIDER=none
```

Proje kökünden `.\start-model.ps1` ile Ollama ve model servisini arka planda başlatın. Script mevcut backend sanal ortamını kullanır; `fastapi`, `uvicorn`, `httpx`, `python-dotenv` kurulu olmalıdır. `.env` değiştiğinde API ve worker da yeniden başlatılmalıdır. Model servisi `/v1/health` yanıtında gerçek model adını ve `runtime: ollama` bilgisini döndürür. Loglar çalışma alanının `run-logs/` klasöründedir.

Bu adapter yazılı prova, raporlama ve taslak üretimini destekler. Ses girdisini desteklemediğinde açık bir 422 hatası verir; metne dönüştürmüş gibi davranmaz. Sesli prova için Transformers veya MLX adapter'ı gerekir. GPU belleğine sığmayan katmanlar Ollama tarafından RAM/CPU üzerinde çalıştırılabilir; hız donanıma ve girdi uzunluğuna bağlıdır.

`gemma4-e2b-text`, indirilen Gemma 4 E2B'nin aynı gerçek metin ağırlıklarını kullanır; görüntü/ses projector'ı ve spekülatif üretim ağırlıkları yüklenmez. Şablon, renderer ve lisans taban modelden korunur. Bu, sınırlı RAM ve VRAM bulunan Windows bilgisayarlarda yazılı akışı hafifletir. Orijinal `gemma4:e2b` modeli de diskte kalır.

Gerçek modelle üç akışı geçici veritabanında sınamak için proje kökünden `backend/.venv/Scripts/python.exe eval/text_real.py` çalıştırın. Mevcut kullanıcılar, eğitimler ve raporlar değiştirilmez.

## Bilinen sınırlar

- Ses girişi en fazla 30 sn (Gemma 4).
- Değerlendirme sürerken (~30 sn) gelen tur cevabı onun bitmesini bekler.
