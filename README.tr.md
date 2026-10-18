# ProvaMüşteri

[English](README.md)

Çalışanlar, mağaza veya otelin kendi kurallarına göre gerçek bir müşteriyle prova yapar. Yerel Gemma 4 müşteriyi oynar, çalışanı yazar ve yöneticinin inceleyebileceği puanlı bir rapor üretir.

## Ne yapılabilir

- Altı hazır senaryo: üçü mağaza, üçü otel. Yönetici işletmenin kendi kurallarından yeni senaryo da taslaklayabilir.
- Prova yazılı mesaj ya da eller serbest telefon olur. Aramada müşteri konuşur, mikrofon açılır, kısa bir sessizlik sözü müşteriye geri verir.
- Aynı senaryo **sert müşteri** olarak da açılır. Cevap tek cümledir, fazla bilgi vermez ve çalışan kurala uygun somut bir adım söyleyene kadar yumuşamaz.
- Kolay, orta ve zor senaryonun etiketidir. Rapor çıktıktan sonra "tekrar dene", zayıf rubrik boyutunda müşteriyi zorlaştırır.
- Erkek müşteriler (`Bey`) erkek sesle, kadın müşteriler (`Hanım`) kadın sesle konuşur.
- Cevapsız prova puansız bırakılabilir. Geçmiş süren, raporlu ve bırakılan olarak ayrılır. Yalnız bırakılanlar silinebilir.
- Yönetici kimin prova yaptığını görür, turları dinler ve puanı gerekçeyle düzeltir.

## Parçalar

| Parça | İş |
|---|---|
| React, TypeScript, Vite | Çalışan ve yönetici arayüzü |
| FastAPI, SQLite, Alembic | API, iş kuyruğu, ses dosyaları |
| Gemma 4 E4B, 4-bit, MLX | Konuşmayı yazıya dökme, müşteri cevabı, puanlama. Mac'te çalışır, bulut API'si değildir |
| macOS `say` veya Piper | Müşteri ve çalışan turlarının sesi |

## Mimari

```
tarayıcı ──HTTP/cookie──► API (FastAPI) ──SQLite işleri──► worker ──HTTP──► model-service (Gemma 4)
                                ▲                              │
                                └──────── ses (var/media) ◄────┘── TTS (Piper / macOS say)
```

API modeli kendisi çağırmaz. İşi kuyruğa yazar, `202` ve `job_id` döner. Tarayıcı `GET /jobs/{id}` ile yoklar.

## Yerelde çalıştırma (macOS)

```bash
cp .env.example .env

cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e . pytest pyyaml "jsonschema[format]" openapi-spec-validator
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --reload --port 8000     # terminal 1: API
.venv/bin/python -m app.worker                          # terminal 2: worker
.venv/bin/pytest -q                                      # testler stub model kullanır, GPU gerekmez

cd ../frontend
npm install && npm run dev                               # http://localhost:5173
```

Demo hesaplar (şifre `PM_DEMO_PASSWORD`, boşsa `prova1234`):

- `mehmet@demo.test`, yönetici
- `elif@demo.test` ve `can@demo.test`, çalışan

Yönetici çalışanı oluştururken geçici bir şifre verir. Çalışan ilk girişte `/change-password` ekranında bunu değiştirmeden eğitim API'sine giremez. Yöneticiler bu zorunluluktan geçmez. E-posta ile şifre kurtarma yoktur; kişi mevcut ya da geçici şifreyi bilmelidir.

### Gerçek model

`.env` içinde `PM_MODEL_MODE=real` yapın ve model servisini başlatın. İlk açılış yaklaşık 5 GB indirir. Sonrakiler yaklaşık 10 saniye sürer.

```bash
cd model-service
python3.12 -m venv .venv-mlx && .venv-mlx/bin/pip install -e ".[mlx]"
.venv-mlx/bin/uvicorn app.main:app --port 8100 --env-file ../.env
```

Mac'te bu, Gemma 4 E4B 4-bit'tir (`mlx-community/gemma-4-e4b-it-4bit`, yaklaşık 5,4 GB). NVIDIA kurulumu `model-service/README.md` içindedir. Ölçümler `docs/s0-spike.md` dosyasındadır.

`PM_MODEL_MODE=stub` arayüz işi için API'yi ayakta tutar. Cevaplar `[stub]` etiketlidir ve geçmişte gerçek puan değil, sahte puan olarak görünür. `GET /api/v1/health` bu durumda `model_service: "stub"` der.

Gerçek model duman testleri geçici veritabanı kullanır: `backend/.venv/bin/python eval/e2e_real.py` ve `eval/draft_real.py`.

### Sesler

macOS'ta `PM_TTS_PROVIDER=local`. `PM_TTS_VOICE` (varsayılan `Yelda`) kadın sestir. `PM_TTS_VOICE_MALE` (varsayılan `Cem`) erkek sestir. Erkek ses yoksa üretim varsayılan sese döner.

Windows veya Linux'ta isteğe bağlı Piper ekini ve bir Türkçe ses modelini kurun:

```bash
backend/.venv/Scripts/python.exe -m pip install -e "./backend[tts]"
```

[Türkçe Piper sesinin](https://huggingface.co/rhasspy/piper-voices/tree/main/tr/tr_TR/dfki/medium) `.onnx` ve `.onnx.json` dosyaları aynı klasörde olsun. `PM_TTS_PROVIDER=piper` ve `PM_TTS_MODEL_PATH` model dosyasını göstersin. Piper tek sestir, cinsiyet değiştirmez. Bu sesin [model kartı](https://huggingface.co/rhasspy/piper-voices/blob/main/tr/tr_TR/dfki/medium/MODEL_CARD) CC BY-NC-SA 4.0 veri kümesi kullanır. Piper yazılımı GPL'dir.

`.env` değişince API ve worker yeniden başlatılır. Yeni turlar ses olarak saklanır. Eski sessiz oturumlara geriye dönük ses eklenmez.

## Lisans

Uygulama kodu [MIT](LICENSE) lisanslıdır. Gemma ağırlıkları Gemma kullanım koşullarında, Piper sesi kendi model kartında kalır. Bu deponun lisansı ikisini de kapsamaz.
