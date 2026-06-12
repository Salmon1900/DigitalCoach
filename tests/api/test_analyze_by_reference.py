"""API tests for /api/v1/analyze/by-reference (storage + service mocked)."""

import os
import tempfile

from fastapi.testclient import TestClient

from app.api.routes import analyze as analyze_route
from app.errors import StorageDownloadError
from app.main import app
from app.models.analysis import Analysis, AnalysisResponse, Meta

client = TestClient(app)


def _fake_response() -> AnalysisResponse:
    return AnalysisResponse(
        session_id="s",
        exercise="Push-up",
        exercise_slug="push_up",
        type="reps",
        video_duration_seconds=10.0,
        rep_count=5,
        analysis=Analysis(score=90, remarks=[], tips=[]),
        meta=Meta(analyzed_frames=100, sample_fps=10.0, pose_detected_ratio=0.97),
    )


def _make_temp_video() -> str:
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    return path


def test_by_reference_happy_path(monkeypatch):
    monkeypatch.setattr(analyze_route, "download_to_temp", lambda b, p, s: _make_temp_video())
    monkeypatch.setattr(analyze_route, "run_analysis", lambda path, ex, s: _fake_response())

    resp = client.post(
        "/api/v1/analyze/by-reference",
        json={"exercise": "Push-up", "video": {"bucket": "workout-videos", "path": "u/clip.mp4"}},
    )
    assert resp.status_code == 200
    assert resp.json()["exercise_slug"] == "push_up"


def test_by_reference_storage_error_returns_502(monkeypatch):
    def boom(bucket, path, settings):
        raise StorageDownloadError("nope")

    monkeypatch.setattr(analyze_route, "download_to_temp", boom)
    resp = client.post(
        "/api/v1/analyze/by-reference",
        json={"exercise": "Push-up", "video": {"path": "u/clip.mp4"}},
    )
    assert resp.status_code == 502


def test_by_reference_requires_path():
    resp = client.post(
        "/api/v1/analyze/by-reference",
        json={"exercise": "Push-up", "video": {}},
    )
    assert resp.status_code == 422
