"""Tests for slugify + the analyzer registry mechanics."""

import pytest

from app.cv.analyzers import registry
from app.cv.analyzers.base import ExerciseAnalysisResult, ExerciseAnalyzer
from app.errors import UnsupportedExerciseError


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Push-up", "push_up"),
        ("Pike Push-up", "pike_push_up"),
        ("Pull-up", "pull_up"),
        ("  Handstand  ", "handstand"),
        ("L-Sit to Tuck", "l_sit_to_tuck"),
        ("Diamond   Push-up", "diamond_push_up"),
    ],
)
def test_slugify(name, expected):
    assert registry.slugify(name) == expected


class _DummyAnalyzer(ExerciseAnalyzer):
    slug = "dummy_move"
    display_name = "Dummy Move"
    kind = "reps"

    def analyze(self, series):
        return ExerciseAnalysisResult(score=100)


@pytest.fixture
def isolated_registry(monkeypatch):
    """A registry pre-populated with only the dummy analyzer."""
    monkeypatch.setattr(registry, "_REGISTRY", {})
    monkeypatch.setattr(registry, "_loaded", True)  # skip importing built-ins
    registry.register(_DummyAnalyzer())
    return registry


def test_get_analyzer_by_display_name(isolated_registry):
    assert isolated_registry.get_analyzer("Dummy Move").slug == "dummy_move"


def test_get_analyzer_is_name_format_insensitive(isolated_registry):
    # Different surface forms slugify to the same key.
    assert isolated_registry.get_analyzer("dummy move").slug == "dummy_move"
    assert isolated_registry.get_analyzer("DUMMY-MOVE").slug == "dummy_move"


def test_unknown_exercise_raises_with_supported_list(isolated_registry):
    with pytest.raises(UnsupportedExerciseError) as exc:
        isolated_registry.get_analyzer("Backflip")
    assert exc.value.requested == "Backflip"
    assert "Dummy Move" in exc.value.supported


def test_supported_exercises_returns_name_slug_type(isolated_registry):
    rows = isolated_registry.supported_exercises()
    assert rows == [{"name": "Dummy Move", "slug": "dummy_move", "type": "reps"}]
