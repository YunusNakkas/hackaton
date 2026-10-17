# frontend/

Çalışan arayüzü: giriş, eğitimler, sesli prova, değerlendirme. Yönetici inceleme uçları backend'de olmadığı için burada yok.

Stack: React, TypeScript, Vite, Tailwind, TanStack Query, React Router, React Hook Form, Zod.

```bash
cd frontend
npm install
npm run dev
```

Vite `/api` isteklerini `http://127.0.0.1:8000` adresine iletir. API ve worker README'deki gibi ayakta olmalı. CORS kökeni `http://localhost:5173`.

- İstekler `credentials: "include"` kullanır. Durum değiştiren istekler `X-Requested-With: provamusteri` taşır.
- `/health` → `model_service: "stub"` ise üst barda "Demo modu" görünür.
- Ses kaydı `MediaRecorder` ile yapılır; 30 saniyede kendisi durur.
- Türler sözleşmeye göre elde tutulur. Yenilemek için: `npm run gen:api` (`src/api/schema.d.ts`).
