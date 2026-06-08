# Deploy DigitalCoach to Google Cloud Run — Design

**Date:** 2026-06-08
**Status:** Approved
**Goal:** Replace the laptop-bound Cloudflare quick-tunnel with a stable, always-reachable
HTTPS URL on Google Cloud Run, deploying the existing **synchronous** service.

## Decisions

| Decision | Choice |
|---|---|
| Platform | Google Cloud Run (per CLAUDE.md) |
| GCP project | `calisthenics-498018` (billing enabled, gcloud authed) |
| Region | `me-west1` (Tel Aviv) |
| Scope | Synchronous service as-is; worker/queue deferred |
| Cost posture | Scale to zero (`min-instances=0`), `max-instances=3` |
| Secrets | None — multipart-upload path only; Supabase deferred |
| Build mechanism | `gcloud run deploy --source .` → Cloud Build (no local Docker) |

## Repo changes (small)

1. **`.gcloudignore`** (new) — mirror `.dockerignore` so the source upload excludes
   `.venv/`, `.git/`, media, caches.
2. **`scripts/deploy.ps1`** (new) — repeatable deploy wrapper capturing all Cloud Run flags.
3. **`Dockerfile`** — no change; already Cloud Run–ready (`$PORT`, FFmpeg, `libgl1`,
   headless OpenCV).
4. **`DIGITALCOACH_API.md`** — post-deploy, record the live Cloud Run URL.

No application code changes.

## Cloud Run service config

| Setting | Value | Why |
|---|---|---|
| service name | `digitalcoach` | |
| region | `me-west1` | Tel Aviv |
| auth | `--allow-unauthenticated` | API contract is no-auth |
| memory | `2Gi` | MediaPipe + OpenCV + frame buffers |
| cpu | `2` | CV is CPU-bound |
| timeout | `600s` | 120s video + analysis headroom |
| concurrency | `4` | CV runs in anyio threadpool (releases GIL); tune later |
| min-instances | `0` | scale to zero |
| max-instances | `3` | cap cost on a public endpoint |

## Steps

User-done (prereqs): account, project, billing, gcloud install + auth — **complete**.

Automated this session:
1. Enable APIs: `run`, `cloudbuild`, `artifactregistry`.
2. Add `.gcloudignore` + `scripts/deploy.ps1`.
3. Deploy via Cloud Build.
4. Verify `GET /health` and `GET /api/v1/exercises` on the live URL.
5. Update `DIGITALCOACH_API.md` with the live URL.

## Cost expectation

~$0 idle (scale to zero). Pay only CPU/RAM-seconds during analysis + a few cents/month for
the Artifact Registry image. Cold start after idle: ~20–40s (heavy image).

## Deferred (future work)

- Redis-backed job queue + separate worker deployable (CLAUDE.md target architecture).
- Supabase Storage by-reference path (needs secrets in Secret Manager).
- Auth, result persistence, image slimming.
