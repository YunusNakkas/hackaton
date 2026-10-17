# contracts/

Frontend ve backend arasındaki tek otorite. Kod buna uyar, tersi değil.

| Dosya | Sahibi | Not |
|---|---|---|
| `openapi.yaml` | backend | Web API v0.1 |
| `fixtures/*.json` | ortak | Her dosya `fixtures/index.json` içinde bir şemaya eşlenir |
| `model-service.yaml` | backend | Henüz yok; S0 spike'ından sonra yazılacak |
| `schemas/` | backend | Senaryo/politika/rubrik veri dosyalarının JSON şemaları (sonra) |

## Değişiklik kuralları

1. Önce `openapi.yaml` değişir, sonra kod. Alan silme veya yeniden adlandırma yapacaksan diğer tarafa PR'da haber ver.
2. Yeni alan ekliyorsan ilgili fixture'ı güncelle.
3. Merge'den önce doğrulama geçmeli:
   ```bash
   python contracts/scripts/validate_fixtures.py
   ```
4. `info.version` değerini kırıcı değişiklikte minor (0.x) olarak artır.

## Frontend tarafı

```bash
npx openapi-typescript ../contracts/openapi.yaml -o src/api/schema.d.ts
```

MSW handler'ları `fixtures/` içindeki dosyaları döndürür. Mock modda olunduğunu UI göstermeli (`/health` → `model_service: "stub"`).

## Akış özeti (çalışan)

```
POST /sessions                     → 201 {session, opening_job_id}
GET  /jobs/{opening_job_id}        → ... ready → müşteri açılış sesi çal
POST /sessions/{id}/turns (audio)  → 202 {job_id, employee_turn_id}
GET  /jobs/{job_id}  (poll_after_ms aralığıyla)
     queued → transcribing → generating → synthesizing → ready
     ready: result.customer_turn → GET .../turns/{turnId}/audio çal
     error: error.retryable ise POST /jobs/{id}/retry
POST /sessions/{id}/finish         → 202 {evaluation_job_id}
GET  /sessions/{id}/evaluation     → pending | ready | needs_review | error
```
