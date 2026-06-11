# Reps vs. Timed-Hold Differentiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make timed (static-hold) exercises report how long the athlete held the *correct* position, expose both a longest-continuous and a total hold number, and add an explicit `type` field so consumers can branch reps-vs-timed.

**Architecture:** A new pure `hold_metrics` primitive (the holds analogue of `segmentation.count_reps`) turns a per-frame "in correct position?" boolean signal into `(longest_seconds, total_seconds)`. The handstand analyzer classifies each frame as in-position (balanced + straight) and feeds that signal in. The response model gains `type` and `total_hold_seconds`; `/exercises` is enriched to carry each exercise's type.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, NumPy, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-11-reps-vs-timed-holds-design.md`

---

## File Structure

- Create: `app/cv/holds.py` — pure `hold_metrics(in_position, sample_fps, max_gap_frames) -> HoldMetrics`.
- Create: `tests/cv/test_holds.py` — unit tests for `hold_metrics`.
- Create: `sample_analysis_handstand.json` — documents the timed response shape.
- Create: `docs/integration/2026-06-11-reps-vs-timed-migration.md` — migration prompt for the downstream app.
- Modify: `app/cv/analyzers/base.py` — add `total_hold_seconds` to `ExerciseAnalysisResult`.
- Modify: `app/cv/analyzers/handstand.py` — per-frame in-position gate + two hold numbers + `max_gap_frames`.
- Modify: `app/models/analysis.py` — add `type` and `total_hold_seconds` to `AnalysisResponse`.
- Modify: `app/services/analysis_service.py` — set `type=analyzer.kind`, pass `total_hold_seconds`.
- Modify: `app/cv/analyzers/registry.py` — add `supported_exercises()`.
- Modify: `app/api/routes/analyze.py` — `/exercises` returns `[{name, slug, type}]`.
- Modify: `app/web/index.html` — dropdown reads objects; result branches on `type`.
- Modify: `sample_analysis.json` — add `type` and `total_hold_seconds`.
- Modify: `tests/conftest.py` — add `concat_series` helper.
- Modify: `tests/cv/analyzers/test_handstand.py` — in-position gating tests.
- Modify: `tests/api/test_analyze.py` — `type` + `total_hold_seconds` assertions; fix `_fake_response`.
- Modify: `tests/api/test_analyze_by_reference.py` — fix `_fake_response` for required `type`.
- Modify: `tests/cv/analyzers/test_registry.py` — test `supported_exercises()`.

---

## Task 1: `hold_metrics` primitive

**Files:**
- Create: `app/cv/holds.py`
- Test: `tests/cv/test_holds.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cv/test_holds.py`:

```python
"""Tests for hold-duration metrics (the timed-exercise analogue of count_reps)."""

import pytest

from app.cv.holds import HoldMetrics, hold_metrics


def test_all_in_position_longest_equals_total():
    flags = [True] * 30
    m = hold_metrics(flags, sample_fps=10.0, max_gap_frames=1)
    assert m == HoldMetrics(longest_seconds=3.0, total_seconds=3.0)


def test_none_in_position_is_zero():
    m = hold_metrics([False] * 20, sample_fps=10.0, max_gap_frames=1)
    assert m == HoldMetrics(longest_seconds=0.0, total_seconds=0.0)


def test_two_separate_holds_longest_is_the_longer_run():
    # 20 in, 10 out, 15 in  -> longest = 2.0s, total = 3.5s
    flags = [True] * 20 + [False] * 10 + [True] * 15
    m = hold_metrics(flags, sample_fps=10.0, max_gap_frames=1)
    assert m.longest_seconds == pytest.approx(2.0)
    assert m.total_seconds == pytest.approx(3.5)
    assert m.longest_seconds < m.total_seconds


def test_single_frame_gap_is_bridged():
    # One bad frame inside a hold does not split it; the bridged frame counts
    # toward the longest span but NOT the total.
    flags = [True] * 3 + [False] + [True] * 2  # span = 6 frames, clean = 5
    m = hold_metrics(flags, sample_fps=10.0, max_gap_frames=1)
    assert m.longest_seconds == pytest.approx(0.6)
    assert m.total_seconds == pytest.approx(0.5)


def test_gap_larger_than_tolerance_splits_the_hold():
    flags = [True] * 2 + [False] * 2 + [True]  # two runs: span 2 and span 1
    m = hold_metrics(flags, sample_fps=10.0, max_gap_frames=1)
    assert m.longest_seconds == pytest.approx(0.2)
    assert m.total_seconds == pytest.approx(0.3)


def test_trailing_run_is_counted():
    flags = [False] * 5 + [True] * 4
    m = hold_metrics(flags, sample_fps=10.0, max_gap_frames=1)
    assert m.longest_seconds == pytest.approx(0.4)
    assert m.total_seconds == pytest.approx(0.4)


def test_invalid_fps_raises():
    with pytest.raises(ValueError):
        hold_metrics([True], sample_fps=0.0, max_gap_frames=1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cv/test_holds.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cv.holds'`.

- [ ] **Step 3: Implement `app/cv/holds.py`**

```python
"""Hold-duration metrics for timed (static-hold) exercises.

The reps side has ``segmentation.count_reps``; this is its analogue for holds.
Given a per-frame boolean signal (was the athlete in the correct position on this
frame?), sampled uniformly at ``sample_fps``, it reports how long the hold lasted.

Two numbers, because they answer different questions:
- ``longest_seconds`` — the longest single continuous hold, measured as the
  wall-clock span of the longest run (first to last in-position frame inclusive),
  tolerating up to ``max_gap_frames`` dropped/jittered frames inside it.
- ``total_seconds`` — total time actually spent in position (clean frames only).

Kept pure (a plain sequence in, a NamedTuple out) so it is trivial to unit-test.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple


class HoldMetrics(NamedTuple):
    longest_seconds: float
    total_seconds: float


def hold_metrics(
    in_position: Sequence[bool],
    sample_fps: float,
    max_gap_frames: int = 1,
) -> HoldMetrics:
    """Compute longest-continuous and total hold seconds from a per-frame signal.

    ``in_position[i]`` is True when frame ``i`` met the correct-position criteria.
    A run may bridge up to ``max_gap_frames`` consecutive out-of-position frames
    without breaking; the longest run is measured as its wall-clock span (first to
    last in-position frame, inclusive of bridged gaps). ``total_seconds`` counts
    only frames that are actually in position.
    """
    if sample_fps <= 0:
        raise ValueError("sample_fps must be > 0")
    if max_gap_frames < 0:
        raise ValueError("max_gap_frames must be >= 0")

    total_frames = sum(1 for ok in in_position if ok)

    longest_span = 0
    run_start: int | None = None
    run_end: int | None = None
    gap = 0
    for i, ok in enumerate(in_position):
        if ok:
            if run_start is None:
                run_start = i
            run_end = i
            gap = 0
        elif run_start is not None:
            gap += 1
            if gap > max_gap_frames:
                longest_span = max(longest_span, run_end - run_start + 1)
                run_start = run_end = None
                gap = 0
    if run_start is not None:
        longest_span = max(longest_span, run_end - run_start + 1)

    return HoldMetrics(
        longest_seconds=longest_span / sample_fps,
        total_seconds=total_frames / sample_fps,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/cv/test_holds.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add app/cv/holds.py tests/cv/test_holds.py
git commit -m "feat(cv): add hold_metrics primitive for timed exercises"
```

---

## Task 2: Handstand counts only correct-position time

**Files:**
- Modify: `app/cv/analyzers/base.py`
- Modify: `app/cv/analyzers/handstand.py`
- Modify: `tests/conftest.py`
- Test: `tests/cv/analyzers/test_handstand.py`

- [ ] **Step 1: Add `total_hold_seconds` to the result dataclass**

In `app/cv/analyzers/base.py`, replace the `ExerciseAnalysisResult` dataclass:

```python
@dataclass
class ExerciseAnalysisResult:
    score: int
    remarks: list[Remark] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)
    rep_count: int | None = None
    # For timed exercises only. ``hold_seconds`` is the longest continuous
    # correct-position hold; ``total_hold_seconds`` is the sum of all correct
    # time. Both are ``None`` for reps-based exercises.
    hold_seconds: float | None = None
    total_hold_seconds: float | None = None
```

- [ ] **Step 2: Add the `concat_series` test helper**

In `tests/conftest.py`, add at the end of the file:

```python
def concat_series(*parts: PoseSeries) -> PoseSeries:
    """Join several clips into one, re-timestamping frames at the first clip's fps."""
    fps = parts[0].sample_fps
    frames = [
        PoseFrame(timestamp=i / fps, landmarks=f.landmarks)
        for i, f in enumerate(fr for part in parts for fr in part.frames)
    ]
    return PoseSeries(frames=frames, sample_fps=fps)
```

- [ ] **Step 3: Write the failing handstand tests**

In `tests/cv/analyzers/test_handstand.py`, update the import line and append the new tests:

```python
from tests.conftest import build_handstand_series, concat_series
```

Append these tests:

```python
def test_hold_counts_only_correct_position_time():
    # 2.0s good, 1.0s off-balance (tilt 25 > threshold), 1.5s good.
    series = concat_series(
        build_handstand_series(seconds=2.0, tilt=4, arch=0.0),
        build_handstand_series(seconds=1.0, tilt=25, arch=0.0),
        build_handstand_series(seconds=1.5, tilt=4, arch=0.0),
    )
    result = HandstandAnalyzer().analyze(series)
    # Total correct time is both good stretches (~3.5s); the longest single
    # continuous hold is only the longer stretch (~2.0s).
    assert abs(result.total_hold_seconds - 3.5) < 0.3
    assert abs(result.hold_seconds - 2.0) < 0.3
    assert result.hold_seconds < result.total_hold_seconds


def test_never_correct_reports_zero_hold_but_still_flags_fault():
    result = HandstandAnalyzer().analyze(build_handstand_series(seconds=3.0, tilt=25))
    assert result.hold_seconds == 0.0
    assert result.total_hold_seconds == 0.0
    assert "balance" in _fault_areas(result)


def test_good_hold_longest_equals_total():
    result = HandstandAnalyzer().analyze(build_handstand_series(seconds=4.0, tilt=4))
    assert abs(result.hold_seconds - result.total_hold_seconds) < 0.2
    assert abs(result.hold_seconds - 4.0) < 0.3
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run: `python -m pytest tests/cv/analyzers/test_handstand.py -v`
Expected: FAIL — `total_hold_seconds` is `None` (so the arithmetic/`abs()` errors), and the off-balance clip currently reports a non-zero hold.

- [ ] **Step 5: Implement the in-position gate in the handstand analyzer**

In `app/cv/analyzers/handstand.py`:

(a) Add the import (next to the other `app.cv` imports):

```python
from app.cv.holds import hold_metrics
```

(b) Add the gap threshold to `HandstandThresholds`:

```python
@dataclass(frozen=True)
class HandstandThresholds:
    max_tilt_deg: float = 12.0  # body tilt from vertical above this == off balance
    min_straight_deg: float = 165.0  # shoulder-hip-ankle below this == arched back
    sway_ratio: float = 0.5  # shoulder horizontal sway / shoulder width
    min_hold_seconds: float = 1.0
    min_visibility: float = 0.3
    max_gap_frames: int = 1  # bridge this many dropped/jittered frames within a hold
```

(c) Add an in-position classifier method to `HandstandAnalyzer` (place it just above `analyze`):

```python
    def _in_position(self, series: PoseSeries) -> list[bool]:
        """Per-frame (full timeline) flag: balanced AND straight this frame."""
        t = self.t
        flags: list[bool] = []
        for frame in series.frames:
            if not frame.detected:
                flags.append(False)
                continue
            tilt = body_vertical_tilt(frame, t.min_visibility)
            straight = body_line_angle(frame, t.min_visibility)
            ok = (
                tilt is not None
                and not np.isnan(tilt)
                and tilt <= t.max_tilt_deg
                and straight is not None
                and not np.isnan(straight)
                and straight >= t.min_straight_deg
            )
            flags.append(bool(ok))
        return flags
```

(d) Replace the old hold-seconds line. Find:

```python
        hold_seconds = round(len(tilts) / series.sample_fps, 2) if series.sample_fps else 0.0
```

Replace with:

```python
        flags = self._in_position(series)
        if series.sample_fps:
            metrics = hold_metrics(flags, series.sample_fps, t.max_gap_frames)
            hold_seconds = metrics.longest_seconds
            total_hold_seconds = metrics.total_seconds
        else:
            hold_seconds = total_hold_seconds = 0.0
```

(e) In the `len(tilts) < 3` early-return, add the total. Find that `return ExerciseAnalysisResult(...)` block and change its tail from:

```python
                rep_count=None,
                hold_seconds=hold_seconds,
            )
```

to:

```python
                rep_count=None,
                hold_seconds=hold_seconds,
                total_hold_seconds=total_hold_seconds,
            )
```

(f) In the final `return ExerciseAnalysisResult(...)` at the end of `analyze`, change its tail from:

```python
            rep_count=None,
            hold_seconds=hold_seconds,
        )
```

to:

```python
            rep_count=None,
            hold_seconds=hold_seconds,
            total_hold_seconds=total_hold_seconds,
        )
```

- [ ] **Step 6: Run the full handstand suite to verify it passes**

Run: `python -m pytest tests/cv/analyzers/test_handstand.py -v`
Expected: PASS (all tests, including the pre-existing ones).

- [ ] **Step 7: Commit**

```bash
git add app/cv/analyzers/base.py app/cv/analyzers/handstand.py tests/conftest.py tests/cv/analyzers/test_handstand.py
git commit -m "feat(cv): handstand hold counts only correct-position time"
```

---

## Task 3: Response contract — `type` and `total_hold_seconds`

**Files:**
- Modify: `app/models/analysis.py`
- Modify: `app/services/analysis_service.py`
- Test: `tests/api/test_analyze.py`, `tests/api/test_analyze_by_reference.py`

- [ ] **Step 1: Write/adjust the failing API test**

In `tests/api/test_analyze.py`, update `_fake_response()` to set the (now required) `type` and the new field:

```python
def _fake_response() -> AnalysisResponse:
    return AnalysisResponse(
        session_id="test-session",
        exercise="Push-up",
        exercise_slug="push_up",
        type="reps",
        video_duration_seconds=12.0,
        rep_count=8,
        hold_seconds=None,
        total_hold_seconds=None,
        analysis=Analysis(
            score=82,
            remarks=[
                Remark(
                    timestamp_seconds=2.1, severity="warning", area="hips", message="Hips sagging."
                )
            ],
            tips=["Brace your core."],
        ),
        meta=Meta(analyzed_frames=120, sample_fps=10.0, pose_detected_ratio=0.95),
    )
```

Then extend `test_analyze_happy_path` with two assertions:

```python
    assert body["type"] == "reps"
    assert body["total_hold_seconds"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/api/test_analyze.py::test_analyze_happy_path -v`
Expected: FAIL — `AnalysisResponse` has no field `type` (validation error on construction).

- [ ] **Step 3: Add the fields to the response model**

In `app/models/analysis.py`, add the kind alias and update `AnalysisResponse`:

```python
Severity = Literal["info", "warning", "critical"]
ExerciseKind = Literal["reps", "timed"]
```

```python
class AnalysisResponse(BaseModel):
    session_id: str
    exercise: str
    exercise_slug: str
    type: ExerciseKind = Field(
        ..., description="'reps' for rep-counted exercises, 'timed' for holds."
    )
    video_duration_seconds: float
    rep_count: int | None = None
    hold_seconds: float | None = Field(
        default=None, description="Longest continuous correct-position hold (s), timed only."
    )
    total_hold_seconds: float | None = Field(
        default=None, description="Total correct-position time (s), timed only."
    )
    analysis: Analysis
    meta: Meta
```

(`Field` is already imported in this module.)

- [ ] **Step 4: Wire the service to populate them**

In `app/services/analysis_service.py`, update the `return AnalysisResponse(...)`:

```python
    return AnalysisResponse(
        session_id=str(uuid.uuid4()),
        exercise=analyzer.display_name,
        exercise_slug=analyzer.slug,
        type=analyzer.kind,
        video_duration_seconds=round(sampled.source_duration, 2),
        rep_count=result.rep_count,
        hold_seconds=(round(result.hold_seconds, 2) if result.hold_seconds is not None else None),
        total_hold_seconds=(
            round(result.total_hold_seconds, 2)
            if result.total_hold_seconds is not None
            else None
        ),
        analysis=Analysis(score=result.score, remarks=remarks, tips=result.tips),
        meta=Meta(
            analyzed_frames=len(series),
            sample_fps=round(series.sample_fps, 2),
            pose_detected_ratio=round(detected_ratio, 3),
        ),
    )
```

- [ ] **Step 5: Fix the other test that builds an `AnalysisResponse`**

In `tests/api/test_analyze_by_reference.py`, update `_fake_response()` to include `type`:

```python
def _fake_response() -> AnalysisResponse:
    return AnalysisResponse(
        session_id="s",
        exercise="Push-up",
        exercise_slug="push_up",
        type="reps",
        video_duration_seconds=10.0,
        rep_count=5,
        analysis=Analysis(score=90, remarks=[], tips=[]),
        meta=Meta(analyzed_frames=100, sample_fps=10.0, pose_detected_ratio=0.97),
    )
```

- [ ] **Step 6: Run both API test files to verify they pass**

Run: `python -m pytest tests/api/test_analyze.py tests/api/test_analyze_by_reference.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/models/analysis.py app/services/analysis_service.py tests/api/test_analyze.py tests/api/test_analyze_by_reference.py
git commit -m "feat(api): add type and total_hold_seconds to analysis response"
```

---

## Task 4: Enrich `/exercises` with each exercise's type

**Files:**
- Modify: `app/cv/analyzers/registry.py`
- Modify: `app/api/routes/analyze.py`
- Test: `tests/cv/analyzers/test_registry.py`

- [ ] **Step 1: Write the failing registry test**

In `tests/cv/analyzers/test_registry.py`, append:

```python
def test_supported_exercises_returns_name_slug_type(isolated_registry):
    rows = isolated_registry.supported_exercises()
    assert rows == [{"name": "Dummy Move", "slug": "dummy_move", "type": "reps"}]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/cv/analyzers/test_registry.py::test_supported_exercises_returns_name_slug_type -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'supported_exercises'`.

- [ ] **Step 3: Add the registry helper**

In `app/cv/analyzers/registry.py`, add after `supported_names`:

```python
def supported_exercises() -> list[dict[str, str]]:
    """List analyzable exercises with their type, sorted by display name."""
    load_builtin_analyzers()
    return sorted(
        ({"name": a.display_name, "slug": a.slug, "type": a.kind} for a in _REGISTRY.values()),
        key=lambda e: e["name"],
    )
```

- [ ] **Step 4: Run the registry test to verify it passes**

Run: `python -m pytest tests/cv/analyzers/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Update the `/exercises` route**

In `app/api/routes/analyze.py`, change the import:

```python
from app.cv.analyzers.registry import supported_exercises
```

and the endpoint:

```python
@router.get("/exercises")
async def exercises() -> dict[str, list[dict[str, str]]]:
    """List the exercises this service can analyze, each with its type (reps/timed)."""
    return {"exercises": supported_exercises()}
```

- [ ] **Step 6: Verify the endpoint shape with a quick run**

Run:
```bash
python -c "from fastapi.testclient import TestClient; from app.main import app; import json; print(json.dumps(TestClient(app).get('/api/v1/exercises').json(), indent=2))"
```
Expected: an `exercises` list of objects, e.g. `{"name": "Handstand", "slug": "handstand", "type": "timed"}` among them.

- [ ] **Step 7: Commit**

```bash
git add app/cv/analyzers/registry.py app/api/routes/analyze.py tests/cv/analyzers/test_registry.py
git commit -m "feat(api): /exercises returns name, slug, and type per exercise"
```

---

## Task 5: Update the in-repo demo page

**Files:**
- Modify: `app/web/index.html`

No automated test (static demo page); verify by reading the rendered output.

- [ ] **Step 1: Update the dropdown loader to read objects**

In `app/web/index.html`, in `loadExercises`, replace the `.map(...)` line:

```javascript
        exerciseSel.innerHTML = exercises
          .map((e) => `<option value="${e.name}">${e.name}</option>`)
          .join("");
```

- [ ] **Step 2: Branch the summary on `type`**

In `renderResult`, replace the `reps` / `hold` summary lines:

```javascript
      const reps = data.type === "reps" && data.rep_count != null
        ? `${data.rep_count} reps`
        : null;
      const hold = data.type === "timed" && data.hold_seconds != null
        ? `${data.hold_seconds}s hold` +
          (data.total_hold_seconds != null ? ` (${data.total_hold_seconds}s total)` : "")
        : null;
```

- [ ] **Step 3: Verify by serving and eyeballing (optional manual check)**

Run: `uvicorn app.main:app` then open the page; the dropdown should populate and a handstand result should read e.g. "6.2s hold (8.1s total)". (If no static mount, just confirm the file parses — no syntax errors — by reading it.)

- [ ] **Step 4: Commit**

```bash
git add app/web/index.html
git commit -m "feat(web): demo page branches reps vs timed and shows total hold"
```

---

## Task 6: Update the sample contract files

**Files:**
- Modify: `sample_analysis.json`
- Create: `sample_analysis_handstand.json`

- [ ] **Step 1: Add the new fields to the push-up sample**

In `sample_analysis.json`, add `"type": "reps"` right after `"exercise_slug"`, and `"total_hold_seconds": null` right after `"hold_seconds"`:

```json
  "exercise": "Push-up",
  "exercise_slug": "push_up",
  "type": "reps",
  "video_duration_seconds": 12.4,
  "rep_count": 8,
  "hold_seconds": null,
  "total_hold_seconds": null,
```

- [ ] **Step 2: Create the handstand sample**

Create `sample_analysis_handstand.json`:

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
  "analysis": {
    "score": 82,
    "remarks": [
      {
        "timestamp_seconds": 1.4,
        "severity": "warning",
        "area": "balance",
        "message": "Body is tilting off vertical — stack your hips and feet directly over your hands."
      },
      {
        "timestamp_seconds": 0.0,
        "severity": "info",
        "area": "hold",
        "message": "Solid, stable handstand held for ~6.2s."
      }
    ],
    "tips": [
      "Push tall through the shoulders and keep your gaze between your hands.",
      "Build the hold against a wall first, then practice freestanding balance.",
      "Find a hollow shape: ribs in, hips stacked over shoulders and wrists."
    ]
  },
  "meta": {
    "analyzed_frames": 110,
    "sample_fps": 10.0,
    "pose_detected_ratio": 0.98,
    "warnings": []
  }
}
```

- [ ] **Step 3: Validate both files parse as JSON**

Run:
```bash
python -c "import json; json.load(open('sample_analysis.json')); json.load(open('sample_analysis_handstand.json')); print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add sample_analysis.json sample_analysis_handstand.json
git commit -m "docs: update sample contract for type + total_hold_seconds"
```

---

## Task 7: Migration doc for the downstream app

**Files:**
- Create: `docs/integration/2026-06-11-reps-vs-timed-migration.md`

- [ ] **Step 1: Write the migration prompt**

Create `docs/integration/2026-06-11-reps-vs-timed-migration.md` with the full content below:

````markdown
# Migration: DigitalCoach reps-vs-timed response changes

Paste this to Claude Code in the consumer app. It describes a backwards-incompatible
change to the DigitalCoach analysis API.

## What changed

The analysis API now distinguishes **reps-based** exercises (push-up, pull-up, pike
push-up) from **timed holds** (handstand).

### 1. `/api/v1/analyze` (and `/analyze/by-reference`) response

Two new fields, and one redefined field:

- **NEW** `type`: `"reps" | "timed"`. Branch on this.
- **NEW** `total_hold_seconds`: `number | null`. Total correct-position time
  (timed exercises only; `null` for reps).
- **CHANGED MEANING** `hold_seconds`: still `number | null`, but now means the
  **longest single continuous correct-position hold**, not total tracked time. For
  reps exercises it remains `null`.
- `rep_count`: unchanged (`number | null`; populated for reps, `null` for timed).

Reps response (e.g. push-up):

```json
{ "type": "reps", "rep_count": 8, "hold_seconds": null, "total_hold_seconds": null }
```

Timed response (e.g. handstand):

```json
{ "type": "timed", "rep_count": null, "hold_seconds": 6.2, "total_hold_seconds": 8.1 }
```

### 2. `GET /api/v1/exercises` response

Was a list of names:

```json
{ "exercises": ["Handstand", "Pike Push-up", "Pull-up", "Push-up"] }
```

Now a list of objects:

```json
{
  "exercises": [
    { "name": "Handstand",    "slug": "handstand",    "type": "timed" },
    { "name": "Pike Push-up", "slug": "pike_push_up", "type": "reps"  },
    { "name": "Pull-up",      "slug": "pull_up",      "type": "reps"  },
    { "name": "Push-up",      "slug": "push_up",      "type": "reps"  }
  ]
}
```

## Consumer changes required

1. **Models / DTOs:** add `type` and `total_hold_seconds` to the analysis response
   type. Make `hold_seconds` and `total_hold_seconds` nullable numbers.
2. **`/exercises` parsing:** stop treating entries as strings. Map each object's
   `name` (display) / `slug` (stable key) / `type`. Update any dropdown/list that
   rendered the old string array.
3. **Display logic:** branch on `type`.
   - `reps` → show `rep_count` (e.g. "8 reps").
   - `timed` → show `hold_seconds` as the headline hold ("held 6.2s") and optionally
     `total_hold_seconds` ("8.1s total in position").
4. **Audit existing reads of `hold_seconds`:** anything that assumed it meant "total
   time in frame / total tracked time" must switch to `total_hold_seconds` (or be
   re-checked), because `hold_seconds` is now the longest continuous hold.
5. **Persistence/analytics:** if hold duration is stored, decide which number to
   store (longest vs. total) and migrate historical rows if the semantics matter.

## Notes

- A wobbly handstand with no correct frames returns `hold_seconds: 0` and
  `total_hold_seconds: 0` (with form remarks still present) — handle the zero case.
- `hold_seconds` can be slightly larger than the clean-frame time it contains, by
  design (a single bridged blip frame counts toward the continuous span but not the
  total). Treat `hold_seconds >= 0` and `total_hold_seconds >= 0` independently.
````

- [ ] **Step 2: Validate it renders / parses**

Run: `python -c "open('docs/integration/2026-06-11-reps-vs-timed-migration.md').read(); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add docs/integration/2026-06-11-reps-vs-timed-migration.md
git commit -m "docs: migration guide for reps-vs-timed API changes"
```

---

## Task 8: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `python -m pytest -q`
Expected: all tests pass (no failures, no errors).

- [ ] **Step 2: Lint and format check**

Run: `ruff check . && ruff format --check .`
Expected: no errors. If `ruff format --check` reports diffs, run `ruff format .`, review, and amend the relevant commit.

- [ ] **Step 3: Final confirmation**

Confirm the working tree is clean (`git status`) and all eight tasks are committed.

---

## Self-Review Notes (author)

- **Spec coverage:** correct-position gate (Task 2), two hold numbers (Tasks 1–2),
  `type` field (Task 3), `/exercises` enrichment (Task 4), demo page (Task 5),
  sample files (Task 6), migration doc (Task 7) — all spec sections mapped.
- **Type consistency:** `HoldMetrics(longest_seconds, total_seconds)` used uniformly;
  `hold_metrics(in_position, sample_fps, max_gap_frames)` signature matches all call
  sites; `ExerciseKind = Literal["reps","timed"]` mirrors the analyzer `kind` field
  passed via `analyzer.kind`.
- **No placeholders:** every code step contains complete code.
```
