"""Response models for the exercise-listing endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.analysis import ExerciseKind


class ExerciseInfo(BaseModel):
    name: str = Field(..., description="Human display name, e.g. 'Push-up'.")
    slug: str = Field(..., description="Stable analyzer key, e.g. 'push_up'.")
    type: ExerciseKind = Field(
        ..., description="'reps' for rep-counted exercises, 'timed' for holds."
    )


class ExercisesResponse(BaseModel):
    exercises: list[ExerciseInfo]
