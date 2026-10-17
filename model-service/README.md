# model-service/

Gemma ağırlıklarını tek kez yükleyen ayrı FastAPI servisi. Backend worker'ı buraya HTTP ile bağlanır.

- `adapters/`: runtime adapter'ları (ilk aday Transformers). ASR, metin, görüntü desteği tek tek doğrulanır.
- `prompts/`: sürümlü prompt dosyaları (`customer@1`, `evaluator@1`, `draft@1`).
- `stub/`: GPU'suz geliştirme ve CI için sabit/kurallı cevaplar. Aynı arayüzü uygular.

Arayüz `contracts/model-service.yaml` içinde tanımlanacak (S0 spike'ından sonra).
Planlanan uçlar: `POST /v1/transcribe`, `POST /v1/customer-reply`, `POST /v1/evaluate`, `POST /v1/draft-training`.
