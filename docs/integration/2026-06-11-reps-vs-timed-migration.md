# Migration: DigitalCoach reps-vs-timed response changes

> Hand this whole file to Claude Code (or another agent/dev) **in the consumer app**
> that calls the DigitalCoach API. It describes a backwards-incompatible change to
> the analysis API and exactly what to update on the client side.

## TL;DR

The DigitalCoach analysis API now distinguishes **reps-based** exercises (push-up,
pull-up, pike push-up) from **timed holds** (handstand). Two endpoints changed shape:

1. `POST /api/v1/analyze` (and `POST /api/v1/analyze/by-reference`) gained a `type`
   field and a `total_hold_seconds` field, and **redefined the meaning of
   `hold_seconds`**.
2. `GET /api/v1/exercises` changed from a list of name strings to a list of objects
   `{name, slug, type}`.

---

## 1. Analyze response (`/api/v1/analyze`, `/api/v1/analyze/by-reference`)

### New / changed fields

| Field | Before | After |
|---|---|---|
| `type` | — (didn't exist) | **NEW.** `"reps"` or `"timed"`. Branch on this. |
| `rep_count` | `number \| null` | unchanged. Populated for `reps`, `null` for `timed`. |
| `hold_seconds` | `number \| null` = total tracked time | **MEANING CHANGED.** Now the **longest continuous correct-position hold**, in seconds. Populated for `timed`, `null` for `reps`. |
| `total_hold_seconds` | — (didn't exist) | **NEW.** `number \| null`. **Total** correct-position time in seconds (timed only; `null` for reps). |

Everything else (`session_id`, `exercise`, `exercise_slug`, `video_duration_seconds`,
`analysis`, `meta`) is unchanged.

### Reps example (push-up)

```json
{
  "session_id": "0c5b6e2a-9f3d-4a1b-8c7e-2d4f6a8b1c3e",
  "exercise": "Push-up",
  "exercise_slug": "push_up",
  "type": "reps",
  "video_duration_seconds": 12.4,
  "rep_count": 8,
  "hold_seconds": null,
  "total_hold_seconds": null,
  "analysis": { "score": 78, "remarks": [ /* … */ ], "tips": [ /* … */ ] },
  "meta": { "analyzed_frames": 124, "sample_fps": 10.0, "pose_detected_ratio": 0.96, "warnings": [] }
}
```

### Timed example (handstand)

```json
{
  "session_id": "7b3e1c54-2a9d-4f60-9c1a-8e5d2f0b6a14",
  "exercise": "Handstand",
  "exercise_slug": "handstand",
  "type": "timed",
  "video_duration_seconds": 11.0,
  "rep_count": null,
  "hold_seconds": 6.2,
  "total_hold_seconds": 8.1,
  "analysis": { "score": 82, "remarks": [ /* … */ ], "tips": [ /* … */ ] },
  "meta": { "analyzed_frames": 110, "sample_fps": 10.0, "pose_detected_ratio": 0.98, "warnings": [] }
}
```

### What the two hold numbers mean

- `hold_seconds` — the **single longest unbroken** correct handstand. This is the
  "held for X seconds" headline number. (A brief tracking blip mid-hold is tolerated,
  so this can be marginally larger than the count of clean frames — treat it as a
  duration, not a frame count.)
- `total_hold_seconds` — the **sum** of all correct-position time across the clip,
  even if the athlete fell and re-entered the handstand. `total_hold_seconds >=
  hold_seconds` always.

Pick whichever fits your UI. A typical display: headline `hold_seconds`, with
`total_hold_seconds` as a secondary "total in position" stat.

---

## 2. Exercises listing (`GET /api/v1/exercises`)

### Before

```json
{ "exercises": ["Handstand", "Pike Push-up", "Pull-up", "Push-up"] }
```

### After

```json
{
  "exercises": [
    { "name": "Handstand",    "slug": "handstand",     "type": "timed" },
    { "name": "Pike Push-up", "slug": "pike_push_up",  "type": "reps"  },
    { "name": "Pull-up",      "slug": "pull_up",       "type": "reps"  },
    { "name": "Push-up",      "slug": "push_up",        "type": "reps"  }
  ]
}
```

- `name` — display label (what you previously got as the raw string).
- `slug` — stable machine key (safe to store / switch on).
- `type` — `"reps"` or `"timed"`, so the client can pre-sort or pre-label without
  running an analysis.

---

## Consumer-side checklist

1. **Models / DTOs.** Add `type` and `total_hold_seconds` to the analysis response
   type. Keep `hold_seconds`, `total_hold_seconds`, and `rep_count` all nullable.
   If you use an enum, model `type` as `reps | timed`.
2. **Branch on `type`** wherever you render or store a result:
   - `type === "reps"` → use `rep_count` (e.g. "8 reps").
   - `type === "timed"` → use `hold_seconds` for the headline ("held 6.2s") and
     optionally `total_hold_seconds` ("8.1s total in position").
   - Do **not** rely on "whichever field is non-null" — branch on `type` explicitly.
3. **Audit every existing read of `hold_seconds`.** Its meaning changed from "total
   tracked time" to "longest continuous correct hold." Anything that treated it as a
   total must switch to `total_hold_seconds` (or be re-evaluated).
4. **Update `/exercises` parsing.** Stop treating entries as strings. Map each
   object's `name` / `slug` / `type`. Fix any dropdown, list, or picker that rendered
   the old string array (a naive `.map(name => …)` will now show `[object Object]`).
5. **Persistence / analytics.** If you store hold duration, decide which number to
   persist (longest vs. total) and migrate historical rows if the distinction matters
   for your charts.
6. **Zero-hold case.** A handstand with no correct frames returns `hold_seconds: 0`
   and `total_hold_seconds: 0` (with form remarks still present in `analysis.remarks`).
   Handle the zero case in your UI rather than assuming a timed result always has a
   positive hold.

---

## Notes

- Field additions to the analyze response are additive except for the redefinition of
  `hold_seconds`; the safest path is to branch on `type` everywhere and re-check any
  `hold_seconds` usage.
- The `analysis` block (score, remarks, tips) and `meta` are unchanged — no work
  needed there.
- See `sample_analysis.json` (reps) and `sample_analysis_handstand.json` (timed) in
  the DigitalCoach repo for full, schema-valid examples.
