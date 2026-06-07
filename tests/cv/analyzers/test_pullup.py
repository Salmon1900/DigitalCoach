"""Behavioral tests for the pull-up analyzer."""

from app.cv.analyzers.pullup import PullupAnalyzer
from tests.conftest import build_pullup_series


def _areas(result):
    return {r.area for r in result.remarks}


def _faults(result):
    return [r for r in result.remarks if r.severity != "info"]


def test_counts_reps():
    result = PullupAnalyzer().analyze(build_pullup_series(reps=3))
    assert result.rep_count == 3
    assert result.hold_seconds is None


def test_good_form_scores_high_with_no_faults():
    result = PullupAnalyzer().analyze(build_pullup_series(reps=4, hang=174, top=55, swing=0.0))
    assert result.score >= 85
    assert _faults(result) == []


def test_shallow_pull_flagged():
    result = PullupAnalyzer().analyze(build_pullup_series(reps=3, hang=174, top=110))
    assert "height" in _areas(result)


def test_incomplete_dead_hang_flagged():
    result = PullupAnalyzer().analyze(build_pullup_series(reps=3, hang=150, top=55))
    assert "range" in {r.area for r in _faults(result)}


def test_excessive_swing_flagged():
    result = PullupAnalyzer().analyze(build_pullup_series(reps=3, swing=0.12))
    assert "swing" in _areas(result)
