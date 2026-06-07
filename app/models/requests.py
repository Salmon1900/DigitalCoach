"""Request models for the JSON (storage-reference) analysis endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StorageRef(BaseModel):
    """Points at a video already in Supabase Storage."""

    path: str = Field(..., description="Object path within the bucket.")
    bucket: str | None = Field(
        default=None,
        description="Storage bucket; defaults to the configured video bucket.",
    )


class AnalyzeByReferenceRequest(BaseModel):
    exercise: str = Field(..., description="Exercise name, e.g. 'Push-up'.")
    video: StorageRef
