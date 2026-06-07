"""Pure geometric helpers for pose analysis.

All functions operate on 2-D image-plane points (``(x, y)`` tuples or arrays) and
have no dependency on MediaPipe/OpenCV, so they are trivially unit-testable.
"""

from __future__ import annotations

import numpy as np

Point = np.ndarray | tuple[float, float] | list[float]

_VERTICAL = np.array([0.0, 1.0])


def _vec2(p: Point) -> np.ndarray:
    return np.asarray(p, dtype=float)[:2]


def angle(a: Point, b: Point, c: Point) -> float:
    """Interior angle at vertex ``b`` formed by ``a-b-c``, in degrees [0, 180].

    Returns NaN if either segment has zero length.
    """
    a, b, c = _vec2(a), _vec2(b), _vec2(c)
    ba = a - b
    bc = c - b
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom == 0:
        return float("nan")
    cos_angle = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def angle_from_vertical(a: Point, b: Point) -> float:
    """Angle of the segment ``a->b`` from the vertical axis, in degrees [0, 90].

    Direction-agnostic: 0 means perfectly vertical, 90 means horizontal. Useful
    for body-line verticality (e.g. handstand alignment).
    """
    v = _vec2(b) - _vec2(a)
    n = np.linalg.norm(v)
    if n == 0:
        return float("nan")
    cos_angle = np.clip(abs(np.dot(v, _VERTICAL)) / n, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def midpoint(a: Point, b: Point) -> np.ndarray:
    return (_vec2(a) + _vec2(b)) / 2.0
