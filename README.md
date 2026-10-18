# ProvaMüşteri

[Türkçe](README.tr.md)

Staff practice real customer conversations against their own store or hotel policies. A local Gemma 4 model plays the customer, transcribes the employee, and writes a scored report a manager can review.

## What you can do

- Six ready scenarios, three retail and three hotel. A manager can also draft new ones from the business's own rules.
- Start a practice as a written chat or a hands-free phone call. On a call, the customer speaks, the microphone opens, and a short silence hands the turn back.
- Open the same scenario as a **strict** customer: one short sentence, no extra information, and no softening until the employee states a concrete step that follows the written rule.
- Easy, medium, and hard stay labels on the scenario. After a scored report, "try again" can make the customer harder on the weak rubric dimensions.
- Male customers (`Bey`) are spoken with a male voice and female customers (`Hanım`) with a female voice.
- Empty practices can be left without a score. History splits into ongoing, scored, and abandoned, and only abandoned ones can be deleted.
- Managers see who is practicing now, listen to turns, and adjust a score with a reason.

## Stack

| Piece | Role |
|---|---|
| React, TypeScript, Vite | Employee and manager UI |
| FastAPI, SQLite, Alembic | API, jobs, media |
| Gemma 4 E4B, 4-bit, MLX | Speech recognition, customer replies, scoring. Runs on the Mac, not a cloud API |
| macOS `say` or Piper | Customer and employee turn audio |

## Architecture

```
browser ──HTTP/cookie──► API (FastAPI) ──SQLite jobs──► worker ──HTTP──► model-service (Gemma 4)
                              ▲                            │
                              └──────── audio (var/media) ◄┘── TTS (Piper / macOS say)
```

The API does not call the model itself. It queues a job and returns `202` plus a `job_id`. The browser polls `GET /jobs/{id}`.

## Run it locally (macOS)

```bash
cp .env.example .env

cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e . pytest pyyaml "jsonschema[format]" openapi-spec-validator
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --reload --port 8000     # terminal 1: API
.venv/bin/python -m app.worker                          # terminal 2: worker
.venv/bin/pytest -q                                      # tests use the stub model, no GPU

cd ../frontend
npm install && npm run dev                               # http://localhost:5173
```

Demo accounts (password is `PM_DEMO_PASSWORD`, or `prova1234` when that is empty):

- `mehmet@demo.test`, manager
- `elif@demo.test` and `can@demo.test`, employees

A manager sets a temporary password when creating an employee. The employee must replace it on first login at `/change-password` before the training API will answer. Managers are not forced through that step. There is no email reset; the person must know the current or temporary password.

### Real model

Set `PM_MODEL_MODE=real` and start the model service. The first launch downloads about 5 GB. Later launches take about 10 seconds.

```bash
cd model-service
python3.12 -m venv .venv-mlx && .venv-mlx/bin/pip install -e ".[mlx]"
.venv-mlx/bin/uvicorn app.main:app --port 8100 --env-file ../.env
```

On a Mac this is Gemma 4 E4B 4-bit (`mlx-community/gemma-4-e4b-it-4bit`, about 5.4 GB). NVIDIA setup is in `model-service/README.md`. Measurements are in `docs/s0-spike.md`.

`PM_MODEL_MODE=stub` keeps the API honest for UI work. Replies are labeled `[stub]` and the history shows them as a fake score, not a real one. `GET /api/v1/health` then reports `model_service: "stub"`.

Smoke tests against the real model use a temporary database: `backend/.venv/bin/python eval/e2e_real.py` and `eval/draft_real.py`.

### Voices

On macOS, `PM_TTS_PROVIDER=local`. `PM_TTS_VOICE` (default `Yelda`) is the female voice. `PM_TTS_VOICE_MALE` (default `Cem`) is the male voice. If the male voice is missing, synthesis falls back to the default voice.

On Windows or Linux, install the optional Piper extra and a Turkish voice model:

```bash
backend/.venv/Scripts/python.exe -m pip install -e "./backend[tts]"
```

Put the [Turkish Piper voice](https://huggingface.co/rhasspy/piper-voices/tree/main/tr/tr_TR/dfki/medium) `.onnx` and `.onnx.json` in the same folder, then set `PM_TTS_PROVIDER=piper` and `PM_TTS_MODEL_PATH` to the model file. Piper is one voice, so it does not switch gender. That voice's [model card](https://huggingface.co/rhasspy/piper-voices/blob/main/tr/tr_TR/dfki/medium/MODEL_CARD) uses a CC BY-NC-SA 4.0 dataset. Piper itself is GPL.

Restart the API and the worker after changing `.env`. New turns are stored as audio. Older silent sessions are not backfilled.

## License

Application code is [MIT](LICENSE). Gemma weights stay under the Gemma Terms of Use. The Piper voice stays under its model card. This repository's license does not cover either of those.
