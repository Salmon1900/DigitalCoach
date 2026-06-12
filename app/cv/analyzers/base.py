"""Common interface and result types every exercise analyzer implements.

Analyzers are deliberately free of Pydantic/FastAPI: they take a
:class:`~app.cv.types.PoseSeries` and return plain dataclasses, so they are easy
to unit-test on synthetic data. The service layer maps these to API models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from app.cv.types import PoseSeries

Severity = Literal["info", "warning", "critical"]
ExerciseKind = Literal["reps", "timed"]


@dataclass
class Remark:
    """A single timestamped observation about technique."""

    timestamp: float
    severity: Severity
    area: str
    message: str


@dataclass
class ExerciseAnalysisResult:
    score: int
    remarks: list[Remark] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)
    rep_count: int | None = None
    # For timed exercises only. ``hold_seconds`` is the longest continuous
    # correct-position hold; ``total_hold_seconds`` is the sum of all correct
    # time. Both are ``None`` for reps-based exercises.
    hold_seconds: float | None = None
    total_hold_seconds: float | None = None


class ExerciseAnalyzer(ABC):
    """Base class for per-exercise form checkers.

    Subclasses set ``slug`` (internal key), ``display_name`` (human label that
    slugifies to ``slug``), and ``kind`` (``"reps"`` or ``"timed"``).
    """

    slug: str
    display_name: str
    kind: ExerciseKind

    @abstractmethod
    def analyze(self, series: PoseSeries) -> ExerciseAnalysisResult:
        """Evaluate technique over the pose series and produce feedback."""
        raise NotImplementedError
