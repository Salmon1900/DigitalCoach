"""Rep detection from a 1-D movement signal (e.g. elbow-angle over time).

A repetition is one descent + ascent of the primary joint angle. We use a
hysteresis state machine so small jitter doesn't produce phantom reps: the signal
must drop below ``low_threshold`` to enter the "down" phase and rise back above
``high_threshold`` to complete the rep.

Thresholds are passed in explicitly (analyzers derive them from each clip's own
signal range), keeping this function pure and easy to test.
"""

from __future__ import annotations

import numpy as np

from app.cv.types import RepSegment


def count_reps(
    signal: np.ndarray,
    low_threshold: float,
    high_threshold: float,
) -> list[RepSegment]:
    """Return completed reps detected in ``signal``.

    ``low_threshold`` < ``high_threshold``. Each returned :class:`RepSegment`
    carries the index where the descent began, the bottom (extreme) index, and
    the index where the signal returned to the top.
    """
    if high_threshold <= low_threshold:
        raise ValueError("high_threshold must be greater than low_threshold")

    signal = np.asarray(signal, dtype=float)
    reps: list[RepSegment] = []

    state = "up"
    top_idx = 0
    descent_start = 0
    bottom_idx = 0
    bottom_val = float("inf")

    for i, value in enumerate(signal):
        if state == "up":
            if value <= low_threshold:
                state = "down"
                descent_start = top_idx
                bottom_idx = i
                bottom_val = value
            elif value >= high_threshold:
                top_idx = i
        else:  # state == "down"
            if value < bottom_val:
                bottom_val = value
                bottom_idx = i
            if value >= high_threshold:
                reps.append(RepSegment(start_idx=descent_start, bottom_idx=bottom_idx, end_idx=i))
                state = "up"
                top_idx = i

    return reps
