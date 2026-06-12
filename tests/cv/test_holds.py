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


def test_empty_signal_returns_zeros():
    m = hold_metrics([], sample_fps=10.0)
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


def test_wider_gap_tolerance_bridges_two_frames():
    flags = [True] * 3 + [False] * 2 + [True] * 2  # span = 7 frames, clean = 5
    m = hold_metrics(flags, sample_fps=10.0, max_gap_frames=2)
    assert m.longest_seconds == pytest.approx(0.7)
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


@pytest.mark.parametrize("fps", [0.0, -1.0])
def test_invalid_fps_raises(fps):
    with pytest.raises(ValueError):
        hold_metrics([True], sample_fps=fps, max_gap_frames=1)
