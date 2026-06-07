"""Behavioral tests for the push-up analyzer on synthetic pose series."""

from app.cv.analyzers.pushup import PushupAnalyzer
from tests.conftest import build_pushup_series


def _areas(result):
    return {r.area for r in result.remarks}


def test_counts_reps():
    result = PushupAnalyzer().analyze(build_pushup_series(reps=3))
    assert result.rep_count == 3
    assert result.hold_seconds is None


def test_good_form_scores_high_with_no_hip_fault():
    result = PushupAnalyzer().analyze(build_pushup_series(reps=4, top=172, bottom=80))
    assert result.score >= 85
    hip_remarks = [r for r in result.remarks if r.area == "hips"]
    # Any hip remark on good form must be positive (info), not a fault.
    assert all(r.severity == "info" for r in hip_remarks)


def test_shallow_depth_is_flagged_and_lowers_score():
    good = PushupAnalyzer().analyze(build_pushup_series(reps=3, top=170, bottom=80))
    shallow = PushupAnalyzer().analyze(build_pushup_series(reps=3, top=170, bottom=125))
    assert "depth" in _areas(shallow)
    assert shallow.score < good.score


def test_sagging_hips_flagged_as_fault():
    result = PushupAnalyzer().analyze(build_pushup_series(reps=3, sag_ratio=0.28))
    hip_faults = [r for r in result.remarks if r.area == "hips" and r.severity != "info"]
    assert hip_faults
    assert "sag" in hip_faults[0].message.lower()


def test_piking_hips_flagged():
    result = PushupAnalyzer().analyze(build_pushup_series(reps=3, sag_ratio=-0.28))
    hip_faults = [r for r in result.remarks if r.area == "hips" and r.severity != "info"]
    assert hip_faults
    assert "pik" in hip_faults[0].message.lower()


def test_poor_lockout_flagged():
    result = PushupAnalyzer().analyze(build_pushup_series(reps=3, top=138, bottom=80))
    assert "lockout" in _areas(result)


def test_no_full_reps_does_not_crash_and_counts_zero():
    result = PushupAnalyzer().analyze(build_pushup_series(reps=1, top=120, bottom=118))
    assert result.rep_count == 0
    assert result.remarks  # produced actionable feedback rather than crashing


def test_remark_timestamps_within_clip():
    series = build_pushup_series(reps=3)
    result = PushupAnalyzer().analyze(series)
    assert all(0.0 <= r.timestamp <= series.duration for r in result.remarks)
