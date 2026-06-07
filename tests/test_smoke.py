"""Scaffold smoke tests: the app boots and config loads."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_health_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_settings_defaults():
    settings = get_settings()
    assert settings.analysis_sample_fps > 0
    assert settings.max_video_seconds > 0
