"""Shared per-frame pose metrics used by multiple analyzers.

Each helper averages the left/right sides that are sufficiently visible and
returns ``None`` when neither side can be measured, so analyzers can skip
unusable frames.
"""

from __future__ import annotations

import numpy as np

from app.cv import geometry as g
from app.cv.types import PoseFrame
from app.cv.types import PoseLandmark as L

_SIDES = (
    {
        "shoulder": L.LEFT_SHOULDER,
        "elbow": L.LEFT_ELBOW,
        "wrist": L.LEFT_WRIST,
        "hip": L.LEFT_HIP,
        "knee": L.LEFT_KNEE,
        "ankle": L.LEFT_ANKLE,
    },
    {
        "shoulder": L.RIGHT_SHOULDER,
        "elbow": L.RIGHT_ELBOW,
        "wrist": L.RIGHT_WRIST,
        "hip": L.RIGHT_HIP,
        "knee": L.RIGHT_KNEE,
        "ankle": L.RIGHT_ANKLE,
    },
)


def _visible(frame: PoseFrame, joints: tuple[L, ...], min_visibility: float) -> bool:
    return all(frame.visibility(j) >= min_visibility for j in joints)


def _mean_over_sides(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def elbow_angle(frame: PoseFrame, min_visibility: float = 0.3) -> float | None:
    """Mean elbow angle (shoulder-elbow-wrist) over visible sides, in degrees."""
    values = []
    for s in _SIDES:
        joints = (s["shoulder"], s["elbow"], s["wrist"])
        if _visible(frame, joints, min_visibility):
            values.append(
                g.angle(
                    frame.point(s["shoulder"]), frame.point(s["elbow"]), frame.point(s["wrist"])
                )
            )
    return _mean_over_sides(values)


def body_line_angle(frame: PoseFrame, min_visibility: float = 0.3) -> float | None:
    """Mean shoulder-hip-ankle angle (180 == perfectly straight)."""
    values = []
    for s in _SIDES:
        joints = (s["shoulder"], s["hip"], s["ankle"])
        if _visible(frame, joints, min_visibility):
            values.append(
                g.angle(frame.point(s["shoulder"]), frame.point(s["hip"]), frame.point(s["ankle"]))
            )
    return _mean_over_sides(values)


def hip_sag_ratio(frame: PoseFrame, min_visibility: float = 0.3) -> float | None:
    """Signed vertical offset of the hip from the shoulder→ankle line.

    Normalized by torso length. Positive = hips below the line (sagging),
    negative = hips above the line (piking). ~0 = straight.
    """
    values = []
    for s in _SIDES:
        joints = (s["shoulder"], s["hip"], s["ankle"])
        if not _visible(frame, joints, min_visibility):
            continue
        shoulder = frame.point(s["shoulder"])
        hip = frame.point(s["hip"])
        ankle = frame.point(s["ankle"])
        dx = ankle[0] - shoulder[0]
        t = (hip[0] - shoulder[0]) / dx if abs(dx) > 1e-9 else 0.5
        expected_y = shoulder[1] + t * (ankle[1] - shoulder[1])
        torso = float(np.linalg.norm(hip - shoulder)) + 1e-9
        values.append((hip[1] - expected_y) / torso)
    return _mean_over_sides(values)


def mean_hip_x(frame: PoseFrame, min_visibility: float = 0.3) -> float | None:
    """Mean horizontal hip position over visible sides (for swing/sway)."""
    xs = [frame.point(s["hip"])[0] for s in _SIDES if frame.visibility(s["hip"]) >= min_visibility]
    return float(np.mean(xs)) if xs else None


def shoulder_width(frame: PoseFrame, min_visibility: float = 0.3) -> float | None:
    """Horizontal distance between the shoulders (a scale reference)."""
    if not _visible(frame, (L.LEFT_SHOULDER, L.RIGHT_SHOULDER), min_visibility):
        return None
    return abs(frame.point(L.LEFT_SHOULDER)[0] - frame.point(L.RIGHT_SHOULDER)[0])


def body_vertical_tilt(frame: PoseFrame, min_visibility: float = 0.3) -> float | None:
    """Tilt of the wrists→ankles line from vertical, in degrees (0 = stacked)."""
    need = (L.LEFT_WRIST, L.RIGHT_WRIST, L.LEFT_ANKLE, L.RIGHT_ANKLE)
    if not _visible(frame, need, min_visibility):
        return None
    wrist_mid = (frame.point(L.LEFT_WRIST) + frame.point(L.RIGHT_WRIST)) / 2
    ankle_mid = (frame.point(L.LEFT_ANKLE) + frame.point(L.RIGHT_ANKLE)) / 2
    return g.angle_from_vertical(wrist_mid, ankle_mid)


def series_signal(frames, metric, **kwargs):
    """Apply ``metric`` to each frame, returning (values, frames) for non-None results."""
    values: list[float] = []
    kept = []
    for frame in frames:
        value = metric(frame, **kwargs)
        if value is not None and not np.isnan(value):
            values.append(value)
            kept.append(frame)
    return np.asarray(values, dtype=float), kept
