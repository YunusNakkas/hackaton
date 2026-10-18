# ProvaMüşteri

İşletmelerin kendi politika ve ölçütleriyle çalışan sesli müşteri provası ve yönetici inceleme platformu.

> Durum: yönetici arayüzü ve çalışan yazılı prova akışı hazır. Gerçek modelle taslak → yayımlama → atama → prova → tur sesleri → gerekçeli puan düzeltme zinciri test edildi. Açık mavi ve lacivert temalar mevcut.

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
                                 └──────── ses dosyaları (var/media) ◄┘── TTS (Piper / macOS say)
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

### Geçici şifre ve şifre yenileme

Yönetici çalışanı oluştururken bir geçici şifre belirler. Çalışan e-posta ve bu şifreyle giriş yapınca
`/change-password` ekranına yönlenir; geçici şifresini tekrar doğrulayıp en az 8 karakterli yeni şifreyi
iki kez girer. Yeni şifre öncekiyle aynı olamaz. Yenileme tamamlanmadan eğitim API'sine erişim de engellenir.
Başarılı işlem eski şifreyi ve diğer açık oturumları geçersiz kılar; mevcut oturum güvenli cookie ile yenilenir.
Üst menüdeki kilit simgesinden daha sonra da şifre değiştirilebilir.

`b2d8e1f07a93` migration'ı mevcut çalışanları ilk şifre yenilemesine yönlendirir; kullanıcı şifrelerini değiştirmez.
Yöneticiler bu zorunluluktan etkilenmez. Yeni kurulumda CLI ile oluşturulan demo çalışanları da ilk girişte şifre yeniler.
Testlerde kullanılan `seed()` yardımcı fonksiyonu varsayılan olarak hazır test hesapları üretir.

Şifre unutma/e-posta ile kurtarma bu akışın kapsamında değildir; kullanıcı mevcut veya geçici şifresini bilmelidir.

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

### Windows/Linux Türkçe tur sesleri

`backend/.venv/Scripts/python.exe -m pip install -e "./backend[tts]"` ile isteğe bağlı Piper bağımlılığını kurun.
[Türkçe ses modelini](https://huggingface.co/rhasspy/piper-voices/tree/main/tr/tr_TR/dfki/medium) indirin: `.onnx` ve `.onnx.json` aynı klasörde olmalı.
`.env` içinde `PM_TTS_PROVIDER=piper` ve `PM_TTS_MODEL_PATH=<mutlak model dosyası yolu>` ayarlayıp API ve worker'ı yeniden başlatın.
Yeni yazılı turların hem çalışan hem müşteri metinleri WAV olarak saklanır ve yetkili kullanıcı tarafından dinlenir. Önceden oluşturulmuş sessiz oturumlara geriye dönük ses eklenmez.

Ses modeli [MODEL_CARD](https://huggingface.co/rhasspy/piper-voices/blob/main/tr/tr_TR/dfki/medium/MODEL_CARD) içinde CC BY-NC-SA 4.0 veri kümesi lisansı belirtir; ticari kullanım için uygun lisanslı bir ses modeli seçilmelidir. Piper yazılımı GPL lisanslıdır.

Tam yönetici akışı testi: `backend/.venv/Scripts/python.exe eval/manager_flow_real.py`. Gerçek model servisi ve Piper ses modeli gerekir; test geçici DB/media kullanır. İsteğe bağlı yeni bir çıktı klasörü argümanı test verilerini tarayıcıda incelemek için saklar.

## Proje lisansı

Henüz seçilmedi. Gemma kullanım koşullarıyla uyumlu bir lisans seçilip `LICENSE` eklenecek.
