"""Video analysis endpoints (thin: validate → delegate to the service)."""

from __future__ import annotations

import os
import tempfile

import anyio
from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.config import Settings, get_settings
from app.cv.analyzers.registry import supported_exercises
from app.db.storage import download_to_temp
from app.models.analysis import AnalysisResponse
from app.models.exercises import ExercisesResponse
from app.models.requests import AnalyzeByReferenceRequest
from app.services.analysis_service import run_analysis

router = APIRouter(prefix="/api/v1", tags=["analysis"])

_CHUNK = 1024 * 1024  # 1 MiB


@router.get("/exercises", response_model=ExercisesResponse)
async def exercises() -> ExercisesResponse:
    """List the exercises this service can analyze, each with its type (reps/timed)."""
    return ExercisesResponse(exercises=supported_exercises())


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    exercise: str = Form(..., description="Exercise name, e.g. 'Push-up'."),
    video: UploadFile = File(..., description="The workout video file."),
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    """Analyze an uploaded workout video and return technique feedback."""
    suffix = os.path.splitext(video.filename or "")[1] or ".mp4"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await video.read(_CHUNK):
                out.write(chunk)
        # CV is CPU-bound and blocking — run it off the event loop.
        return await anyio.to_thread.run_sync(run_analysis, path, exercise, settings)
    finally:
        os.unlink(path)


@router.post("/analyze/by-reference", response_model=AnalysisResponse)
async def analyze_by_reference(
    payload: AnalyzeByReferenceRequest,
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    """Analyze a video already stored in Supabase Storage."""
    bucket = payload.video.bucket or settings.supabase_video_bucket
    path = await anyio.to_thread.run_sync(download_to_temp, bucket, payload.video.path, settings)
    try:
        return await anyio.to_thread.run_sync(run_analysis, path, payload.exercise, settings)
    finally:
        os.unlink(path)
