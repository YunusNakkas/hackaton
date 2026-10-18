# frontend/

Employee and manager UI: sign-in, trainings, written and phone practice, reports, assignments, and score review.

Stack: React, TypeScript, Vite, Tailwind, TanStack Query, React Router, React Hook Form, Zod.

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. The API and the worker must already be running, as in the root README. CORS origin is `http://localhost:5173`.

- Requests use `credentials: "include"`. State-changing requests send `X-Requested-With: provamusteri`.
- When `/health` reports `model_service: "stub"`, the top bar shows demo mode.
- Phone practice records with `MediaRecorder` and stops on its own after 30 seconds.
- Types follow the contract. Regenerate them with `npm run gen:api` (`src/api/schema.d.ts`).
