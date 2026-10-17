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

## Sürüm notları

### v0.2.1
- `/health` → `audio_input` (zorunlu). `false` ise mikrofon düğmesi gösterilmez, yalnız yazılı cevap sunulur.
- Yeni hata kodu `audio_unsupported`: ses desteklemeyen kurulumda `POST /sessions/{id}/turns` 422 döner.
- Fixture: `health.real.json`, `health.text_only.json`.

### v0.2.0
- **Tekrar dene:** `POST /sessions` isteğine isteğe bağlı `practice` (`of_session_id`, `mode: same | adaptive`, `focus_dimension_ids`).
  Rapordaki iki düğme: *Aynı senaryoyu tekrar dene* (`same`) ve *Zorlaştırılmış tekrar* (`adaptive`). Odak boyutlar için
  önceki raporun `practice_drill.focus_dimension_ids` değeri kullanılır. Açılış cümlesi senaryodan aynen gelir; zorlaştırma
  müşterinin sonraki cevaplarında başlar.
- `Session.practice` (ekranda "Bu sefer şuna odaklan"), `SessionSummary.practice_mode`, `EvaluationReport.focus_dimension_ids` eklendi (zorunlu; normal oturumda `null` / `[]`).
- **Fotoğraftan politika çıkarma:** `POST /admin/policy-extractions` (1–3 fotoğraf), `GET /admin/policy-extractions/{id}`,
  `GET .../images/{imageId}`. Yeni iş türü `policy_extraction`, yeni hata kodu `image_undecodable`.
  *Backend'de henüz uygulanmadı; fixture'larla mock'lanabilir.*
- Fixture'lar: `sessions.practice_adaptive.json`, `admin.policy_extraction.{processing,ready}.json`, `jobs.policy_extraction.ready.json`.

### v0.1.2
- `no_speech` hata kodu (sessiz kayıt).

### v0.1.1
- Ses kaydı en fazla 30 sn; `pending_job_id` hata alan son işi de gösterir.
