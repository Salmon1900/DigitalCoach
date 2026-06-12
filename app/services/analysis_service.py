"""Orchestrates a single analysis: video → frames → pose → analyzer → response.

``run_analysis`` is a standalone, synchronous (CPU-bound) function. Routes call it
via a threadpool so the event loop isn't blocked; keeping it framework-agnostic also
means it can later be moved behind a job queue with no rewrite.
"""

from __future__ import annotations

import uuid

from app.config import Settings
from app.cv.analyzers.registry import get_analyzer
from app.cv.frames import extract_frames
from app.cv.pose import estimate_pose
from app.errors import PoseNotDetectedError
from app.models.analysis import Analysis, AnalysisResponse, Meta, Remark


def run_analysis(video_path: str, exercise_name: str, settings: Settings) -> AnalysisResponse:
    """Analyze ``video_path`` for ``exercise_name`` and build the API response.

    Raises the typed errors in :mod:`app.errors` (unsupported exercise, video too
    long, undecodable video, pose not detected), which routes map to HTTP.
    """
    # Fail fast on an unsupported exercise before doing any heavy CV work.
    analyzer = get_analyzer(exercise_name)

    sampled = extract_frames(
        video_path,
        target_fps=settings.analysis_sample_fps,
        max_seconds=settings.max_video_seconds,
        max_frames=settings.max_analyzed_frames,
        max_frame_dim=settings.max_frame_dim,
    )
    series = estimate_pose(sampled, model_complexity=settings.model_complexity)

    detected_ratio = series.detected_ratio
    if detected_ratio < settings.min_pose_detected_ratio:
        raise PoseNotDetectedError(detected_ratio, settings.min_pose_detected_ratio)

    result = analyzer.analyze(series)

    remarks = [
        Remark(
            timestamp_seconds=round(r.timestamp, 2),
            severity=r.severity,
            area=r.area,
            message=r.message,
        )
        for r in result.remarks
    ]

    return AnalysisResponse(
        session_id=str(uuid.uuid4()),
        exercise=analyzer.display_name,
        exercise_slug=analyzer.slug,
        type=analyzer.kind,
        video_duration_seconds=round(sampled.source_duration, 2),
        rep_count=result.rep_count,
        hold_seconds=(round(result.hold_seconds, 2) if result.hold_seconds is not None else None),
        total_hold_seconds=(
            round(result.total_hold_seconds, 2) if result.total_hold_seconds is not None else None
        ),
        analysis=Analysis(score=result.score, remarks=remarks, tips=result.tips),
        meta=Meta(
            analyzed_frames=len(series),
            sample_fps=round(series.sample_fps, 2),
            pose_detected_ratio=round(detected_ratio, 3),
        ),
    )
