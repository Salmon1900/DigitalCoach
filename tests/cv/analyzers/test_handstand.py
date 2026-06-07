"""Behavioral tests for the handstand analyzer (timed hold)."""

from app.cv.analyzers.handstand import HandstandAnalyzer
from tests.conftest import build_handstand_series


def _areas(result):
    return {r.area for r in result.remarks}


def _fault_areas(result):
    return {r.area for r in result.remarks if r.severity != "info"}


def test_reports_hold_seconds_and_no_reps():
    result = HandstandAnalyzer().analyze(build_handstand_series(seconds=3.0))
    assert result.rep_count is None
    assert abs(result.hold_seconds - 3.0) < 0.3


def test_good_handstand_scores_high():
    result = HandstandAnalyzer().analyze(
        build_handstand_series(seconds=4.0, tilt=4, arch=0.0, sway=0.0)
    )
    assert result.score >= 85
    assert _fault_areas(result) == set()


def test_off_balance_tilt_flagged():
    result = HandstandAnalyzer().analyze(build_handstand_series(seconds=3.0, tilt=22))
    assert "balance" in _fault_areas(result)


def test_banana_back_flagged_as_critical():
    result = HandstandAnalyzer().analyze(build_handstand_series(seconds=3.0, arch=0.08))
    back = [r for r in result.remarks if r.area == "back"]
    assert back and back[0].severity == "critical"


def test_short_hold_flagged():
    result = HandstandAnalyzer().analyze(build_handstand_series(seconds=0.5))
    assert result.hold_seconds < 1.0
    assert "hold" in _areas(result)
