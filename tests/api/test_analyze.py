"""API tests for /api/v1/analyze with the CV pipeline mocked at the service boundary."""

from fastapi.testclient import TestClient

from app.api.routes import analyze as analyze_route
from app.errors import UnsupportedExerciseError, VideoTooLongError
from app.main import app
from app.models.analysis import Analysis, AnalysisResponse, Meta, Remark

client = TestClient(app)


def _fake_response() -> AnalysisResponse:
    return AnalysisResponse(
        session_id="test-session",
        exercise="Push-up",
        exercise_slug="push_up",
        type="reps",
        video_duration_seconds=12.0,
        rep_count=8,
        hold_seconds=None,
        total_hold_seconds=None,
        analysis=Analysis(
            score=82,
            remarks=[
                Remark(
                    timestamp_seconds=2.1, severity="warning", area="hips", message="Hips sagging."
                )
            ],
            tips=["Brace your core."],
        ),
        meta=Meta(analyzed_frames=120, sample_fps=10.0, pose_detected_ratio=0.95),
    )


def _post(monkeypatch, run_impl):
    monkeypatch.setattr(analyze_route, "run_analysis", run_impl)
    return client.post(
        "/api/v1/analyze",
        data={"exercise": "Push-up"},
        files={"video": ("clip.mp4", b"fake-bytes", "video/mp4")},
    )


def test_analyze_happy_path(monkeypatch):
    resp = _post(monkeypatch, lambda path, exercise, settings: _fake_response())
    assert resp.status_code == 200
    body = resp.json()
    assert body["exercise"] == "Push-up"
    assert body["rep_count"] == 8
    assert body["analysis"]["score"] == 82
    assert body["analysis"]["remarks"][0]["area"] == "hips"
    assert body["type"] == "reps"
    assert body["total_hold_seconds"] is None


def test_unsupported_exercise_returns_422_with_supported_list(monkeypatch):
    def boom(path, exercise, settings):
        raise UnsupportedExerciseError("Backflip", ["Push-up"])

    resp = _post(monkeypatch, boom)
    assert resp.status_code == 422
    assert resp.json()["supported"] == ["Push-up"]


def test_video_too_long_returns_413(monkeypatch):
    def boom(path, exercise, settings):
        raise VideoTooLongError(150.0, 120)

    resp = _post(monkeypatch, boom)
    assert resp.status_code == 413


def test_missing_exercise_field_is_422():
    resp = client.post(
        "/api/v1/analyze",
        files={"video": ("clip.mp4", b"fake-bytes", "video/mp4")},
    )
    assert resp.status_code == 422


def test_missing_video_is_422():
    resp = client.post("/api/v1/analyze", data={"exercise": "Push-up"})
    assert resp.status_code == 422
