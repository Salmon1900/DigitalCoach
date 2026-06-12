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
    run_len = 0
    gap = 0
    for i, ok in enumerate(in_position):
        if ok:
            if run_start is None:
                run_start = i
            run_len = i - run_start + 1
            gap = 0
        elif run_start is not None:
            gap += 1
            if gap > max_gap_frames:
                longest_span = max(longest_span, run_len)
                run_start = None
                run_len = 0
                gap = 0
    longest_span = max(longest_span, run_len)

    return HoldMetrics(
        longest_seconds=longest_span / sample_fps,
        total_seconds=total_frames / sample_fps,
    )
