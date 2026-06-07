"""Video decoding and frame sampling (OpenCV).

``cv2`` is imported lazily inside the function so the pure-logic layers (and their
tests) don't require OpenCV, and so the heavy import doesn't slow cold starts until
analysis actually runs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.errors import InvalidVideoError, VideoTooLongError


@dataclass
class SampledFrames:
    """Frames sampled from a video, with the effective sampling rate."""

    # Each item: (timestamp_seconds, BGR image as an HxWx3 uint8 array).
    frames: list[tuple[float, np.ndarray]]
    sample_fps: float
    source_duration: float


def extract_frames(
    path: str,
    *,
    target_fps: float,
    max_seconds: int,
    max_frames: int,
) -> SampledFrames:
    """Decode ``path`` and return frames sampled down to ~``target_fps``.

    Raises :class:`InvalidVideoError` if the file can't be opened and
    :class:`VideoTooLongError` if it exceeds ``max_seconds``.
    """
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise InvalidVideoError(f"Could not open video: {path}")

    try:
        source_fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        frame_total = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        duration = frame_total / source_fps if source_fps > 0 else 0.0

        if duration and duration > max_seconds:
            raise VideoTooLongError(duration, max_seconds)

        # How many source frames to skip between samples.
        step = max(1, round(source_fps / target_fps)) if source_fps > 0 else 1

        sampled: list[tuple[float, np.ndarray]] = []
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                timestamp = index / source_fps if source_fps > 0 else index / target_fps
                sampled.append((timestamp, frame))
                if len(sampled) >= max_frames:
                    break
            index += 1

        if not sampled:
            raise InvalidVideoError(f"No frames could be read from: {path}")

        effective_fps = source_fps / step if source_fps > 0 else target_fps
        # Fall back to a measured duration if metadata was missing.
        measured_duration = duration or (sampled[-1][0] if sampled else 0.0)
        return SampledFrames(
            frames=sampled, sample_fps=effective_fps, source_duration=measured_duration
        )
    finally:
        capture.release()
