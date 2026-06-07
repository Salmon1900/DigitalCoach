---
name: scaffold-endpoint
description: Scaffold a new FastAPI endpoint for DigitalCoach following the project's layered conventions (router -> service -> cv/db) with Pydantic v2 schemas and tests. Use when adding or changing API surface.
---

# Scaffold a FastAPI endpoint

Create a new endpoint that follows the repo's layering: **thin route → service →
(cv | db)**, fully typed, async-correct.

## Steps
1. **Schema first** (`app/models/`): define Pydantic v2 request and response models.
   For analysis responses, conform to the `sample_analysis.json` contract.
2. **Service** (`app/services/`): put the orchestration/business logic here. It calls
   into `app/cv/` and `app/db/` behind their interfaces and raises **typed exceptions**
   on failure. No FastAPI imports in services.
3. **Route** (`app/api/routes/`): a thin `async def` handler on an `APIRouter` that
   validates input, resolves dependencies via `Depends` (settings, Supabase client,
   authenticated user), and delegates to the service. Register the router in
   `app/main.py`.
4. **Auth & limits:** derive `user_id` from the verified Supabase JWT (never the client);
   enforce file type/size and `MAX_VIDEO_SECONDS` for uploads at the edge.
5. **Long-running work:** if it triggers video analysis, do **not** block the request —
   accept the job, offload CV to the worker pool, and return a job handle (poll/webhook
   for results).
6. **Errors:** map service exceptions to HTTP responses via central exception handlers,
   not scattered try/except.
7. **Tests:** add pytest coverage with `TestClient`/`AsyncClient`, mocking the cv/db
   boundaries — hand off to `test-engineer`.

## Delegate
- Endpoint/schema design → `fastapi-architect`
- DB/auth/storage details → `supabase-integration`
- CV behavior → `cv-pipeline-engineer`

## Guardrails
- Routes stay thin; no business/CV/DB logic inline.
- Everything typed; response shape matches the documented contract.
- Configuration/planning phase — implement only when explicitly asked.
