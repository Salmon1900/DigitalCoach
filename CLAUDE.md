# DigitalCoach

AI-powered API service that analyzes workout videos (focus: **calisthenics**) using
computer vision and returns technique feedback and coaching tips.

## What this service does

1. **Upload** — client submits a workout video via the REST API.
2. **Store** — video lands in Supabase Storage.
3. **Analyze** — frames are sampled and run through MediaPipe pose estimation; joint
   angles / movement patterns are evaluated against per-exercise form rules.
4. **Feedback** — API returns a structured, timestamped analysis (see
   `sample_analysis.json` for the response contract): a score, per-moment remarks, and
   actionable tips.

## Tech stack

- **Language/runtime:** Python 3.11+
- **API framework:** FastAPI (async, Pydantic v2 models, auto OpenAPI docs)
- **Database/auth/storage:** Supabase (Postgres + Auth + Storage). Access via the
  `supabase-py` client. **Use the existing Supabase project — do not stand up a new DB.**
- **Computer vision:** MediaPipe (self-hosted pose estimation), OpenCV for frame ops,
  FFmpeg for video decoding/frame extraction.

## Deployment & runtime architecture

- **Host:** the Python service runs as a **Docker container on Google Cloud Run** (CPU-bound
  CV needs real CPU/RAM and long timeouts — *not* a serverless/edge JS platform).
- **Async job pattern:** upload endpoint validates + stores to Supabase Storage, then
  **enqueues** an analysis job; a **separate worker** (RQ/arq/Celery on Redis) runs the
  MediaPipe pipeline off the request path and writes results back to Supabase. The API
  returns a job id; clients poll/get notified. Never run analysis inside the HTTP request.
- **Two deployables, one image:** the FastAPI web service and the worker run from the same
  container image with different entrypoints (`uvicorn app.main:app` vs the worker command).
- **System deps:** the image must install **FFmpeg** (and OpenCV's runtime libs); pin these
  in the Dockerfile, not just pip.
- **Vercel** is reserved for a possible future **frontend/dashboard** only — not this API.
- First file to create when coding starts: a `Dockerfile` (+ `.dockerignore`).

## Conventions (follow these when writing code later)

- **Async-first:** API route handlers are `async def`. Push CPU-bound CV work to a
  worker/thread pool — never block the event loop with frame processing.
- **Typed everywhere:** full type hints; request/response bodies are Pydantic models.
- **Layering:** `routes -> services -> (cv | db)`. Routes stay thin (validation +
  delegation); business logic lives in services; CV and Supabase access are isolated
  modules so they can be tested/swapped independently.
- **Config via env:** all secrets/settings come from environment variables (see
  `.env.example`), loaded through a single settings module. No hardcoded keys, ever.
- **One exercise = one analyzer:** each supported movement (pull-up, push-up, squat,
  plank, …) gets its own form-checker module exposing a common interface, so adding an
  exercise doesn't touch the pipeline. Use the `add-exercise-analyzer` skill.
- **Errors:** raise typed exceptions in services; translate to HTTP at the route edge.

## Security rules (hard constraints)

- **Never** read, print, edit, or commit `.env` or any real secret. `.env` is
  gitignored and access is hook-blocked.
- The Supabase **service-role key is server-only** and bypasses RLS — never expose it in
  responses, logs, or client-facing code.
- Uploaded videos are user PII — don't log raw frames or video paths with user
  identifiers; don't commit media files (gitignored).

## Project layout (target — build incrementally, no code yet)

```
app/
  main.py            # FastAPI app factory + router registration
  config.py          # env-backed settings (pydantic-settings)
  api/routes/        # thin HTTP handlers
  services/          # orchestration / business logic
  cv/                # MediaPipe pose estimation, frame extraction, form rules
  db/                # supabase-py client + queries
  models/            # Pydantic request/response schemas
tests/               # pytest
```

## Commands (planned — tools not installed yet)

- Run dev server: `uvicorn app.main:app --reload`
- Tests: `pytest`
- Lint/format: `ruff check .` and `ruff format .`

## Working agreements for Claude

- **Status:** MVP implemented — synchronous `POST /api/v1/analyze` (multipart) and
  `/analyze/by-reference` (Supabase Storage) returning feedback for push-up, pull-up,
  pike push-up, and handstand. Rule-based analyzers live in `app/cv/analyzers/`. Deferred:
  job-queue/worker, auth, result persistence. Dev env: `.venv` (MediaPipe pinned to
  `0.10.14` for the bundled `solutions.pose` API).
- Use the specialized subagents for their domains: `cv-pipeline-engineer` (video/pose),
  `fastapi-architect` (endpoints/schemas), `supabase-integration` (DB/auth/storage),
  `test-engineer` (pytest), `deployment-engineer` (Docker/Cloud Run).
- The **`supabase` MCP server** is connected (see `.mcp.json`) — use it for live schema
  inspection, migrations, SQL, logs, and advisors during development. `supabase-py` is for
  app runtime code. Delegate DB work to the `supabase-integration` agent.
- When unsure about FastAPI / Supabase / MediaPipe APIs, fetch current docs via the
  **context7** MCP server rather than relying on memory.
- Keep `sample_analysis.json` as the source of truth for the response shape; update it
  deliberately if the contract changes.
