# Reps vs. Timed-Hold Differentiation — Design

Date: 2026-06-11
Status: Approved (pending spec review)

## Problem

DigitalCoach analyzes both **reps-based** movements (push-up, pull-up, pike push-up)
and **static holds** (handstand). The analyzer interface already carries a
`kind: "reps" | "timed"` flag and the response already has nullable `rep_count` /
`hold_seconds` fields — but two gaps remain:

1. **`hold_seconds` measures the wrong thing.** The handstand analyzer computes
   `hold_seconds = len(tilts) / sample_fps` — i.e. every frame in which *any* pose
   was trackable, regardless of form. That is "time the athlete was visible," not
   "time spent in a correct handstand." It is not analogous to rep counting, where
   only *valid* reps count.

2. **Consumers can't cleanly branch on reps vs. timed.** The response exposes the
   distinction only implicitly (which of `rep_count` / `hold_seconds` is non-null).
   A downstream app must infer it.

## Goals

- For timed exercises, `hold_seconds` reflects time spent **in the correct
  position**, frame-by-frame — the hold analogue of counting valid reps.
- Expose **both** a longest-continuous-hold number and a total-correct-time number.
- Add an explicit `type` field to the analysis response so consumers branch on it
  directly.
- Enrich the `/exercises` endpoint so consumers know which exercises are timed
  *before* analyzing.
- Reps-based analyzers (push-up, pull-up, pike push-up) are behaviorally unchanged.

## Non-goals

- No new exercises.
- No change to the rep-counting algorithm or reps analyzers' logic.
- No persistence / job-queue / auth work (still deferred per project status).

## Design

### "Correct position" gate (handstand)

The hold timer changes from "every tracked frame" to "every correct-position
frame." A frame is **in position** when, on that frame:

- a pose is detected, **and**
- `body_vertical_tilt(frame) ≤ max_tilt_deg` (near-vertical / balanced), **and**
- `body_line_angle(frame) ≥ min_straight_deg` (not arched / no "banana back").

If either metric is unmeasurable on a frame (missing landmarks → `None`/`NaN`), the
frame is **not** in position (we cannot confirm correctness).

**Sway stays a whole-clip quality signal**, not a per-frame gate. It still
contributes to the score and can still raise a balance remark, but it does not
decide whether an individual frame counts toward the hold. (Rationale: sway is
currently derived from the spread of shoulder-x across the whole clip; making it
per-frame is a larger change and was explicitly out of scope.)

### Timeline, runs, and the two numbers

Classification runs over the **full series timeline** (`series.frames`, in order),
not just detected frames — undetected frames count as "not in position," so the
hold duration reflects real wall-clock continuity rather than skipping gaps.

Because frames are uniformly sampled at `sample_fps`, a contiguous span of `n`
timeline frames represents `n / sample_fps` seconds.

- `hold_seconds` = (**wall-clock span** of the longest in-position run) /
  `sample_fps`, where a run's span is the frame count from its first to its last
  in-position frame **inclusive** (so any bridged gap frames inside the run are part
  of the span — the hold was continuous in time).
- `total_hold_seconds` = (count of frames that are **actually** in position) /
  `sample_fps`.

**Small-gap tolerance.** A new threshold `max_gap_frames` (default `1`) allows up
to that many consecutive non-in-position frames *inside* a run without breaking it,
so a single jittered or dropped frame does not shatter a genuine hold. Consequences,
made explicit to avoid ambiguity:
- Bridged gap frames **do** count toward `hold_seconds` (they are inside the
  longest run's continuous span).
- Bridged gap frames **do not** count toward `total_hold_seconds` (only truly
  in-position frames do).
- Therefore, in the presence of bridged gaps, `hold_seconds` for a single
  continuous hold can slightly exceed the in-position frames it contains — this is
  intended ("how long the hold lasted" vs. "how many frames were clean").

### Score and remarks

Form remarks (balance / arch / sway) and the score continue to be computed over the
**detected** frames exactly as today, so feedback is unaffected by the new gate. In
particular:

- A handstand with detected frames but **zero** in-position frames still produces
  its balance/arch warnings and a score — and reports `hold_seconds: 0.0`,
  `total_hold_seconds: 0.0`. We do **not** early-return or suppress feedback in that
  case.
- The existing "tracking failed" guard (`< 3` measurable tilt frames → score 0,
  one critical remark) is unchanged.
- `short_hold` now compares the **longest** hold (`hold_seconds`) against
  `min_hold_seconds` (previously it compared the total tracked time, which was the
  only number available). The "Solid, stable handstand held for ~Xs" / "Held for
  ~Xs — work toward longer holds" remarks reference `hold_seconds` (the longest run).

### Data types

`ExerciseAnalysisResult` (`app/cv/analyzers/base.py`) gains:

```python
total_hold_seconds: float | None = None
```

Redefined semantics (documented in the docstring):
- `hold_seconds` — longest continuous in-position hold (was: total tracked time).
- `total_hold_seconds` — sum of all in-position time.

Both remain `None` for reps analyzers.

`HandstandThresholds` gains `max_gap_frames: int = 1`. Existing `max_tilt_deg`
(12.0) and `min_straight_deg` (165.0) are reused as the per-frame gate thresholds.

### Response contract

`AnalysisResponse` (`app/models/analysis.py`) gains:

```python
type: Literal["reps", "timed"]
total_hold_seconds: float | None = None
```

`hold_seconds` keeps its name; its meaning is now "longest correct hold."
`rep_count` is unchanged. The service sets `type=analyzer.kind` and passes
`total_hold_seconds` through (rounded to 2 dp, like `hold_seconds`).

Reps result (unchanged shape, new fields):

```json
{
  "type": "reps",
  "rep_count": 8,
  "hold_seconds": null,
  "total_hold_seconds": null
}
```

Timed (handstand) result:

```json
{
  "type": "timed",
  "rep_count": null,
  "hold_seconds": 6.2,
  "total_hold_seconds": 8.1
}
```

### `/exercises` endpoint

Changes from a list of names to a list of objects so consumers can pre-sort
timed vs. reps:

Before:
```json
{ "exercises": ["Handstand", "Pike Push-up", "Pull-up", "Push-up"] }
```

After:
```json
{
  "exercises": [
    { "name": "Handstand",     "slug": "handstand",     "type": "timed" },
    { "name": "Pike Push-up",  "slug": "pike_push_up",  "type": "reps"  },
    { "name": "Pull-up",       "slug": "pull_up",       "type": "reps"  },
    { "name": "Push-up",       "slug": "push_up",       "type": "reps"  }
  ]
}
```

The registry gains a helper (e.g. `supported_exercises()`) returning
`[{name, slug, type}]` sorted by name; the route returns it under the existing
`exercises` key. `app/web/index.html`'s dropdown loader is updated to read
`name` from each object.

### In-repo demo (`app/web/index.html`)

`renderResult` branches on `data.type`:
- `reps` → "N reps" (as today).
- `timed` → "Xs hold (Ys total)" using `hold_seconds` and `total_hold_seconds`.

The dropdown loader (`loadExercises`) maps each exercise **object** to an
`<option>` using its `name`.

### Sample contract files

- `sample_analysis.json` (push-up, the canonical example) gains `"type": "reps"`
  and `"total_hold_seconds": null`.
- New `sample_analysis_handstand.json` documents the timed shape
  (`type: "timed"`, `rep_count: null`, populated `hold_seconds` and
  `total_hold_seconds`). `sample_analysis.json` remains the primary source of
  truth referenced by `CLAUDE.md`.

## Testing (TDD)

- Extend `tests/conftest.py` so a handstand clip can mix in-position and
  out-of-position segments (e.g. a builder that concatenates a "good" stretch, a
  "bad" stretch from high tilt/arch, and another good stretch — or a helper that
  concatenates two `PoseSeries`). Needed because `build_handstand_series` currently
  holds tilt/arch constant for the whole clip.
- New / updated handstand tests:
  - All-correct clip → `hold_seconds ≈ total_hold_seconds ≈ duration`.
  - Good/bad/good clip → `total_hold_seconds` ≈ sum of both good stretches;
    `hold_seconds` ≈ the longer single stretch (and `< total`).
  - A single bad frame inside a hold (≤ `max_gap_frames`) does not split the
    longest run.
  - Detected but never-correct clip (e.g. constant high tilt) → `hold_seconds == 0`
    and `total_hold_seconds == 0`, **and** the balance remark still fires.
  - Existing tests adjusted to the new semantics where needed (the good-handstand
    and short-hold cases should still pass as-is).
- API test (`tests/api/test_analyze.py`): response includes `type` and
  `total_hold_seconds`; a reps exercise reports `type == "reps"` with both hold
  fields `null`.
- `/exercises` test: returns objects with `name`, `slug`, `type`.

## Deliverable: migration doc for the downstream app

After implementation, write a standalone migration prompt
(`docs/integration/2026-06-11-reps-vs-timed-migration.md`) the user can hand to
Claude Code in their other app. It must cover:

- The new `type` field and how to branch on it (`reps` vs `timed`).
- The **redefined** meaning of `hold_seconds` (now longest correct hold, not total
  tracked time) and the new `total_hold_seconds`.
- The `/exercises` shape change (list of strings → list of `{name, slug, type}`).
- Before/after JSON for both `/analyze` and `/exercises`.
- A short checklist of consumer-side changes (model/DTO updates, UI display logic,
  any code that read `hold_seconds` as "total time").

## Risks / edge cases

- **Redefining `hold_seconds` is a silent semantic change** for any existing
  consumer (same field name, different meaning). Mitigated by the `type` field, the
  migration doc, and `total_hold_seconds` preserving access to a total.
- **`/exercises` shape change** breaks naive consumers that treat entries as
  strings. Mitigated by the migration doc; in-repo `index.html` updated in lockstep.
- **Gap tolerance tuning:** `max_gap_frames = 1` at the default 10 fps tolerates a
  ~0.1 s blip. If sample_fps is much lower, one frame is a larger time slice; this
  is acceptable for an MVP and is a named constant for later tuning.
```
