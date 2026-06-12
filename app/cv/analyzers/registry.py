"""Exercise-name → analyzer lookup.

The mobile app sends an exercise *name* (matching its ``exercises`` table, e.g.
``"Pike Push-up"``). We slugify it (``pike_push_up``) and look up the analyzer.
Analyzers self-register at import time via :func:`register`; :func:`load_builtin_analyzers`
imports the built-in analyzer modules to trigger that registration.
"""

from __future__ import annotations

import re

from app.cv.analyzers.base import ExerciseAnalyzer
from app.errors import UnsupportedExerciseError

_REGISTRY: dict[str, ExerciseAnalyzer] = {}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Normalize an exercise name to an analyzer key.

    ``"Push-up"`` → ``"push_up"``, ``"Pike Push-up"`` → ``"pike_push_up"``.
    """
    return _NON_ALNUM.sub("_", name.strip().lower()).strip("_")


def register(analyzer: ExerciseAnalyzer) -> ExerciseAnalyzer:
    """Register an analyzer instance under its ``slug``."""
    _REGISTRY[analyzer.slug] = analyzer
    return analyzer


def get_analyzer(name: str) -> ExerciseAnalyzer:
    """Look up the analyzer for an exercise name (raises if unsupported)."""
    load_builtin_analyzers()
    slug = slugify(name)
    analyzer = _REGISTRY.get(slug)
    if analyzer is None:
        raise UnsupportedExerciseError(name, supported_names())
    return analyzer


def supported_slugs() -> list[str]:
    load_builtin_analyzers()
    return sorted(_REGISTRY)


def supported_names() -> list[str]:
    load_builtin_analyzers()
    return sorted(a.display_name for a in _REGISTRY.values())


def supported_exercises() -> list[dict[str, str]]:
    """List analyzable exercises with their type, sorted by display name."""
    load_builtin_analyzers()
    return sorted(
        ({"name": a.display_name, "slug": a.slug, "type": a.kind} for a in _REGISTRY.values()),
        key=lambda e: e["name"],
    )


_loaded = False


def load_builtin_analyzers() -> None:
    """Import built-in analyzer modules so they register themselves (idempotent)."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    # Imported for their registration side effects.
    from app.cv.analyzers import (  # noqa: F401
        handstand,
        pike_pushup,
        pullup,
        pushup,
    )
