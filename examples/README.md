# DigitalCoach — trying it out

A quick way to run the service locally and analyze a real workout video.

## 1. Install dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements-dev.txt
```

## 2. Start the service

```bash
uvicorn app.main:app --reload --port 8080
```

- Health check: http://localhost:8080/health
- Interactive API docs (Swagger): http://localhost:8080/docs

## 3. Analyze a video

Record a clip of the exercise (for push-ups, **film from the side** with your whole
body in frame, good lighting, plain background). Then:

```bash
python examples/analyze_video.py path/to/your_pushups.mp4 --exercise "Push-up"
```

You'll get JSON back: a `score`, timestamped `remarks` (with `severity` and `area`),
coaching `tips`, the detected `rep_count`, and a `meta` block describing the analysis.

### Supported exercises (so far)

- **Push-up** — depth, lockout, and body-line (hip sag / pike) checks.

More (pull-up, pike push-up, handstand) are being added. Send any exercise name
that matches your app's `exercises` table; unsupported names return a 422 listing
what's available.

## Notes

- `--exercise` accepts the name as it appears in your app (e.g. `"Push-up"`,
  `"Pike Push-up"`); it's matched case/format-insensitively.
- Default video limits: 120s max length, sampled at 10 fps (configurable via env).
- See `sample_request.http` for raw HTTP examples (VS Code REST Client).
