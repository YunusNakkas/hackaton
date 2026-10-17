# frontend/

Frontend sahibinin alanı. Stack: React + TypeScript + Vite, Tailwind, TanStack Query, React Router, React Hook Form + Zod, MSW.

Backend'e bağımlılık yalnızca `../contracts/` üzerinden:

```bash
npx openapi-typescript ../contracts/openapi.yaml -o src/api/schema.d.ts
```

- MSW handler'ları `../contracts/fixtures/*.json` dosyalarını döndürsün; fixture'ları kopyalamayın, import edin.
- Bütün istekler `credentials: "include"` ve mutasyonlarda `X-Requested-With: provamusteri` başlığı taşır.
- `/health` → `model_service: "stub"` ise ekranda "demo/mock modu" etiketi gösterilir.
- Ses kaydı: `MediaRecorder` (Chrome/Firefox `audio/webm;codecs=opus`, Safari `audio/mp4`).
- Akış özeti için `../contracts/README.md` dosyasına bakın.
