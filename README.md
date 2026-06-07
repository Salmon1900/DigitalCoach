# DigitalCoach

An AI-powered API service that analyzes **calisthenics** workout videos with computer
vision and returns technique feedback: a score, timestamped remarks, injury-avoidance
warnings, and coaching tips.

It's built to be consumed by a mobile calisthenics app — the app sends a clip of the
user performing an exercise, and DigitalCoach returns structured, actionable feedback.

## How it works

```
video ──▶ frame sampling (OpenCV) ──▶ pose estimation (MediaPipe) ──▶ per-exercise
                                                                       rule-based analyzer
                                                                            │
                                                          score + remarks + tips (JSON)
```

The analysis is **rule-based geometry**: joint angles and body-line metrics are computed
from MediaPipe pose landmarks, repetitions are segmented, and each exercise is checked
against named form criteria. It's deterministic, explainable, and unit-tested — no
training data required.

## Supported exercises

| Exercise | Type | Checks |
|----------|------|--------|
| Push-up | reps | depth, lockout, body line (hip sag / pike) |
| Pull-up | reps | full dead hang, pull height (chin over bar), swing/kipping |
| Pike Push-up | reps | pike position (hips high), depth |
| Handstand | timed | vertical alignment, straight body (banana-back), balance, hold time |

The client sends the exercise **by name** (matching the app's `exercises` table, e.g.
`"Pike Push-up"`); names are matched case/format-insensitively. Unsupported names return
a `422` listing what's available.

## API

Base path: `/api/v1`

- `POST /api/v1/analyze` — multipart upload (`exercise` field + `video` file).
- `POST /api/v1/analyze/by-reference` — JSON body referencing a video already in
  Supabase Storage: `{ "exercise": "...", "video": { "bucket": "...", "path": "..." } }`.
- `GET /health` — liveness check. Interactive docs at `/docs`.

The response shape is documented in [`sample_analysis.json`](sample_analysis.json):

```json
{
  "exercise": "Push-up", "exercise_slug": "push_up",
  "video_duration_seconds": 12.4, "rep_count": 8, "hold_seconds": null,
  "analysis": {
    "score": 78,
    "remarks": [{ "timestamp_seconds": 3.2, "severity": "warning", "area": "hips", "message": "..." }],
    "tips": ["..."]
  },
  "meta": { "analyzed_frames": 124, "sample_fps": 10.0, "pose_detected_ratio": 0.96, "warnings": [] }
}
```

`severity` is `info | warning | critical` (critical = injury risk).

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements-dev.txt

uvicorn app.main:app --reload --port 8080
python examples/analyze_video.py path/to/pushups.mp4 --exercise "Push-up"
```

See [`examples/`](examples/) for the CLI harness and raw HTTP examples. For push-ups,
film from the **side** with your whole body in frame.

## Tech stack

- **API:** FastAPI (async, Pydantic v2, auto OpenAPI)
- **Computer vision:** MediaPipe Pose (self-hosted), OpenCV, FFmpeg
- **Storage/DB/auth:** Supabase (Storage used for the by-reference input path)
- **Runtime:** Python 3.11+, packaged as a Docker container for Google Cloud Run

## Development

```bash
pytest            # unit + API tests (pure geometry, analyzers on synthetic poses, endpoints)
ruff check .      # lint
ruff format .     # format
```

Architecture follows `routes → services → (cv | db)`. Each exercise is an isolated
analyzer behind a common interface (`app/cv/analyzers/`), so adding a movement doesn't
touch the pipeline. See [`CLAUDE.md`](CLAUDE.md) for conventions.

## Status

MVP: synchronous analysis endpoint with four exercises, returning feedback in the
response. Deliberately deferred: a job-queue/worker for very long videos, auth, and
server-side persistence of results.
