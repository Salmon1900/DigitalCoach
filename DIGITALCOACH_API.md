# DigitalCoach API — Integration Guide

> **For Claude Code working in the mobile app repo.** This document is a *directive*:
> read it, then build the integration into this app following the app's own existing
> conventions (folder layout, navigation, state management, networking). Do **not**
> blindly paste the snippets below — they exist to pin down the exact wire contract so
> you get the request/response shapes right. Adapt the implementation to fit this codebase.

DigitalCoach is an AI service that analyzes a **calisthenics workout video** and returns
**timestamped technique feedback** — a score, per-moment remarks, and coaching tips. The
app's job: let the user pick/record a video, send it to the service for one exercise, and
present the feedback.

---

## 1. Connection & configuration

The service is plain HTTP/JSON. **No authentication, no API key, no CORS concern** for a
React Native *native* build (RN bypasses browser CORS). If this app also runs on **Expo
Web**, CORS would apply — flag it if so, but assume native for now.

**Base URL must be configurable** — read it from app config / env (e.g. an Expo `extra`
field or `EXPO_PUBLIC_DIGITALCOACH_URL`), never hardcode it across the app:

- **Production (stable):** Google Cloud Run —
  `https://digitalcoach-1099019766503.me-west1.run.app`
  This is the stable, always-on URL (region `me-west1`, scale-to-zero). Use this. Note the
  service scales to zero when idle, so the **first request after a quiet period may take
  ~20–40s** (cold start) before the container is warm; subsequent requests are fast.
- **Legacy (dev only):** a temporary Cloudflare quick-tunnel was used before deployment.
  Quick-tunnel URLs are ephemeral and rotate on restart — superseded by the Cloud Run URL above.

Build a single source of truth for the base URL (one constant/config read), no string
literals scattered across the app.

---

## 2. Endpoint reference (the wire contract)

Base path for analysis endpoints is `/api/v1`. All responses are JSON.

### `GET /health`
Liveness check. Returns `{ "status": "ok" }`. Use it for a connectivity smoke test.

### `GET /api/v1/exercises`
Returns the exercises the service can analyze **right now**:
```json
{ "exercises": ["Handstand", "Pike Push-up", "Pull-up", "Push-up"] }
```
**Fetch this live** to populate any exercise picker — do **not** hardcode the list. The set
grows over time, and the exact display-name string is what you send back in `analyze`.

### `POST /api/v1/analyze`  ← **the app uses this one**
**`multipart/form-data`** with exactly two fields:

| Field      | Type   | Notes                                              |
|------------|--------|----------------------------------------------------|
| `exercise` | string | The display name, e.g. `"Push-up"`. Sent verbatim. |
| `video`    | file   | The workout video (e.g. `video/mp4`).              |

Returns an **`AnalysisResponse`** (see §3). This call is **synchronous** — see §5.

### `POST /api/v1/analyze/by-reference`  *(not used by this app)*
JSON path for videos already in Supabase Storage. The app uploads directly, so ignore this
unless requirements change. Documented only for completeness:
`{ "exercise": "Push-up", "video": { "path": "...", "bucket": "..."(optional) } }`.

---

## 3. Response contract: `AnalysisResponse`

This is the shape every successful `analyze` call returns. Model the app's types on it
exactly.

```jsonc
{
  "session_id": "0c5b6e2a-...",        // string, unique per analysis
  "exercise": "Push-up",                // echoed display name
  "exercise_slug": "push_up",           // normalized key
  "video_duration_seconds": 12.4,       // number
  "rep_count": 8,                        // number | null (null for holds like Handstand)
  "hold_seconds": null,                 // number | null (set for holds, null for reps)
  "analysis": {
    "score": 78,                         // integer 0–100
    "remarks": [                         // timestamped observations
      {
        "timestamp_seconds": 3.2,        // number — when in the clip
        "severity": "warning",           // "info" | "warning" | "critical"
        "area": "hips",                  // body area / criterion, e.g. "hips", "depth"
        "message": "Hips are sagging — brace your core..."
      }
    ],
    "tips": [                            // string[] — general coaching advice
      "Keep your body in one straight line from head to heels."
    ]
  },
  "meta": {
    "analyzed_frames": 124,              // integer
    "sample_fps": 10.0,                  // number
    "pose_detected_ratio": 0.96,         // 0.0–1.0, how much of the clip was trackable
    "warnings": []                       // string[], non-fatal notes
  }
}
```

**TypeScript types** (paste-ready reference — match these, adapt naming to app style):

```ts
export type Severity = "info" | "warning" | "critical";

export interface Remark {
  timestamp_seconds: number;
  severity: Severity;
  area: string;
  message: string;
}

export interface Analysis {
  score: number;        // 0–100
  remarks: Remark[];
  tips: string[];
}

export interface AnalysisMeta {
  analyzed_frames: number;
  sample_fps: number;
  pose_detected_ratio: number; // 0–1
  warnings: string[];
}

export interface AnalysisResponse {
  session_id: string;
  exercise: string;
  exercise_slug: string;
  video_duration_seconds: number;
  rep_count: number | null;
  hold_seconds: number | null;
  analysis: Analysis;
  meta: AnalysisMeta;
}
```

**UI mapping hints:** drive a results screen off `analysis.score` (headline), render
`remarks` as a timeline sorted by `timestamp_seconds` and color-coded by `severity`
(`info`=neutral, `warning`=amber, `critical`=red), list `tips` as bullets. Show
`rep_count` *or* `hold_seconds` depending on which is non-null. `meta.pose_detected_ratio`
below ~0.8 is worth a soft "tracking was partial" note.

---

## 4. Error contract

Errors come back as the matching HTTP status with a JSON body `{ "detail": "<message>" }`.
The `detail` strings are **user-facing and friendly by design** — prefer showing them
directly over inventing your own copy.

| Status | Meaning                          | Body                              | App handling                                                        |
|--------|----------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `413`  | Video too long (>120s)           | `{ detail }`                      | Tell user to trim to ≤120s before retrying.                         |
| `422`  | Unsupported exercise             | `{ detail, supported: string[] }` | Shouldn't happen if the picker uses `/exercises`. Show `supported`. |
| `422`  | Invalid / undecodable video      | `{ detail }`                      | Ask user to re-record or pick a different file.                     |
| `422`  | Pose not detected                | `{ detail }`                      | Show `detail` (it explains: full body visible, good lighting).      |
| `502`  | Storage download failed          | `{ detail }`                      | Only on the by-reference path — not expected for this app.          |
| `500`  | Unexpected server error          | `{ detail }`                      | Generic "something went wrong, try again."                          |

Build one error-mapping helper that turns a non-2xx response into a typed app error with a
display message (use the server `detail` when present), plus a network/timeout branch.

---

## 5. Constraints & gotchas (read before building)

- **Synchronous = slow request.** Analysis runs *inside* the HTTP request (no job queue
  yet). A clip can take **tens of seconds** to come back. Set a generous client timeout
  (**at least 60s, ideally 120s**), show an indeterminate progress/"Analyzing your set…"
  state, and disable re-submit while in flight. There is **no polling / job-id flow** —
  one request, one response. (This may change later; isolate the call so a future async
  flow is a localized change.)
- **120-second video cap.** Longer videos are rejected with `413`. Consider enforcing/
  warning client-side before upload to save the user a long round-trip.
- **Multipart field names are exact:** `exercise` and `video`. Getting these wrong yields
  a 422 from FastAPI.
- **React Native `FormData` file shape.** Append the video as an object, not a Blob:
  ```ts
  const form = new FormData();
  form.append("exercise", exerciseName);
  form.append("video", {
    uri: videoUri,            // file:// URI from expo-image-picker / camera
    name: "workout.mp4",
    type: "video/mp4",
  } as any);
  // Do NOT set Content-Type manually — let fetch add the multipart boundary.
  await fetch(`${baseUrl}/api/v1/analyze`, { method: "POST", body: form });
  ```
- **Exercise string round-trips.** Send the exact display name you got from `/exercises`
  (e.g. `"Pike Push-up"`); the server normalizes it. Don't slugify on the client.
- **PII / privacy.** The uploaded clip is the user's body. Don't log the video URI with
  user identifiers; don't persist frames. Treat `session_id` as the handle for a result.

---

## 6. What to build into the app

Following this app's existing conventions, implement (names are suggestions — match local style):

1. **Config:** base-URL resolution from env (dev tunnel → prod), single source of truth.
2. **API client module** (e.g. `digitalCoachClient`): typed `getExercises()` and
   `analyze(exerciseName, videoUri)`; centralizes base URL, timeout, and the
   non-2xx → typed-error mapping from §4. No UI concerns here.
3. **Types:** the §3 interfaces (or generate from the live OpenAPI at `/docs` /
   `/openapi.json` if that fits the app's tooling better).
4. **State/hook** (e.g. `useAnalyze`): wraps the client call with `idle → loading →
   success/error` states, exposes the `AnalysisResponse`, prevents double-submit.
5. **Screens/wiring:** an exercise picker fed by `getExercises()`, a record/pick + submit
   step, and a results view that renders score, the remark timeline, and tips per §3.
6. **Edge cases:** loading state for the long request, the §4 errors surfaced to the user,
   the 120s pre-check, and an offline/timeout path.

Keep the network layer isolated so that when the backend gains an async job queue (upload →
job id → poll/notify) and auth, only the client module changes — not the screens.

---

## Appendix: quick manual smoke test

```bash
# Liveness
curl https://consists-complete-classification-ict.trycloudflare.com/health

# Supported exercises
curl https://consists-complete-classification-ict.trycloudflare.com/api/v1/exercises

# Analyze a local clip
curl -X POST \
  -F "exercise=Push-up" \
  -F "video=@/path/to/pushups.mp4" \
  https://consists-complete-classification-ict.trycloudflare.com/api/v1/analyze
```

Interactive API docs (when the tunnel/prod is up): `<base-url>/docs`.
