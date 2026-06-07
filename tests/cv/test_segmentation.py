"""Tests for hysteresis-based rep counting."""

import numpy as np

from app.cv.segmentation import count_reps


def _down_up(depth_low=60.0, top=170.0, n=10):
    """One smooth descent+ascent of an angle signal."""
    down = np.linspace(top, depth_low, n)
    up = np.linspace(depth_low, top, n)
    return np.concatenate([down, up])


def test_single_rep_counted():
    signal = _down_up()
    reps = count_reps(signal, low_threshold=90.0, high_threshold=150.0)
    assert len(reps) == 1


def test_bottom_index_is_the_minimum():
    signal = _down_up()
    reps = count_reps(signal, low_threshold=90.0, high_threshold=150.0)
    assert reps[0].bottom_idx == int(np.argmin(signal))


def test_two_reps_counted():
    signal = np.concatenate([_down_up(), _down_up()])
    reps = count_reps(signal, low_threshold=90.0, high_threshold=150.0)
    assert len(reps) == 2


def test_small_dips_below_hysteresis_are_ignored():
    # Jitter that never crosses the low threshold should not count as reps.
    signal = np.array([170, 165, 168, 160, 166, 169, 170], dtype=float)
    reps = count_reps(signal, low_threshold=90.0, high_threshold=150.0)
    assert reps == []


def test_monotonic_signal_has_no_reps():
    signal = np.linspace(170, 60, 20)
    reps = count_reps(signal, low_threshold=90.0, high_threshold=150.0)
    assert reps == []


def test_incomplete_final_descent_not_counted():
    # Goes down but never returns above high threshold -> not a completed rep.
    signal = np.concatenate([_down_up(), np.linspace(170, 60, 10)])
    reps = count_reps(signal, low_threshold=90.0, high_threshold=150.0)
    assert len(reps) == 1
