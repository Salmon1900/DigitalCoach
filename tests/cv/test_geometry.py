"""Tests for pure geometry helpers."""

import math

import numpy as np

from app.cv import geometry as g


def test_angle_right_angle():
    a = (0.0, 1.0)
    b = (0.0, 0.0)
    c = (1.0, 0.0)
    assert g.angle(a, b, c) == 90.0


def test_angle_straight_line():
    a = (0.0, 0.0)
    b = (1.0, 0.0)
    c = (2.0, 0.0)
    assert g.angle(a, b, c) == 180.0


def test_angle_forty_five():
    a = (0.0, 1.0)
    b = (0.0, 0.0)
    c = (1.0, 1.0)
    assert math.isclose(g.angle(a, b, c), 45.0, abs_tol=1e-6)


def test_angle_is_orientation_independent():
    # Same shape, mirrored — interior angle is unchanged.
    assert math.isclose(
        g.angle((0, 1), (0, 0), (1, 0)),
        g.angle((0, -1), (0, 0), (-1, 0)),
        abs_tol=1e-6,
    )


def test_angle_degenerate_returns_nan():
    assert math.isnan(g.angle((0, 0), (0, 0), (1, 0)))


def test_angle_from_vertical_vertical_segment_is_zero():
    # y grows downward; a straight vertical segment -> 0 deg from vertical.
    assert math.isclose(g.angle_from_vertical((0.5, 0.1), (0.5, 0.9)), 0.0, abs_tol=1e-6)


def test_angle_from_vertical_horizontal_segment_is_ninety():
    assert math.isclose(g.angle_from_vertical((0.1, 0.5), (0.9, 0.5)), 90.0, abs_tol=1e-6)


def test_angle_from_vertical_is_direction_agnostic():
    up = g.angle_from_vertical((0.5, 0.9), (0.5, 0.1))
    down = g.angle_from_vertical((0.5, 0.1), (0.5, 0.9))
    assert math.isclose(up, down, abs_tol=1e-6)


def test_midpoint():
    m = g.midpoint((0.0, 0.0), (2.0, 4.0))
    assert np.allclose(m, [1.0, 2.0])
