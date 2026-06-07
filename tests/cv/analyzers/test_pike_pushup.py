"""Behavioral tests for the pike push-up analyzer."""

from app.cv.analyzers.pike_pushup import PikePushupAnalyzer
from tests.conftest import build_pike_series


def _areas(result):
    return {r.area for r in result.remarks}


def test_counts_reps():
    result = PikePushupAnalyzer().analyze(build_pike_series(reps=3))
    assert result.rep_count == 3
    assert result.hold_seconds is None


def test_good_form_scores_high():
    result = PikePushupAnalyzer().analyze(
        build_pike_series(reps=3, top=160, bottom=80, hip_angle=70)
    )
    assert result.score >= 85
    hip_remarks = [r for r in result.remarks if r.area == "hips"]
    assert all(r.severity == "info" for r in hip_remarks)


def test_shallow_depth_flagged():
    result = PikePushupAnalyzer().analyze(build_pike_series(reps=3, top=160, bottom=128))
    assert "depth" in _areas(result)


def test_insufficient_pike_flagged():
    result = PikePushupAnalyzer().analyze(build_pike_series(reps=3, hip_angle=150))
    hip_faults = [r for r in result.remarks if r.area == "hips" and r.severity != "info"]
    assert hip_faults
