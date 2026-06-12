"""API response models (the analysis contract — see ``sample_analysis.json``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "critical"]
ExerciseKind = Literal["reps", "timed"]


class Remark(BaseModel):
    timestamp_seconds: float = Field(..., description="When in the clip this was observed.")
    severity: Severity
    area: str = Field(..., description="Body area / criterion, e.g. 'hips', 'depth'.")
    message: str


class Analysis(BaseModel):
    score: int = Field(..., ge=0, le=100)
    remarks: list[Remark]
    tips: list[str]


class Meta(BaseModel):
    analyzed_frames: int
    sample_fps: float
    pose_detected_ratio: float
    warnings: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    session_id: str
    exercise: str
    exercise_slug: str
    type: ExerciseKind = Field(
        ..., description="'reps' for rep-counted exercises, 'timed' for holds."
    )
    video_duration_seconds: float
    rep_count: int | None = None
    hold_seconds: float | None = Field(
        default=None, description="Longest continuous correct-position hold (s), timed only."
    )
    total_hold_seconds: float | None = Field(
        default=None, description="Total correct-position time (s), timed only."
    )
    analysis: Analysis
    meta: Meta
