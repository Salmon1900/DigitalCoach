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


def fit_within(frame: np.ndarray, max_dim: int) -> np.ndarray:
    """Downscale ``frame`` so its longer side is at most ``max_dim`` pixels.

    Returns the frame unchanged if ``max_dim`` is non-positive or the frame already
    fits. Only ever shrinks (never upscales). Aspect ratio is preserved.
    """
    if max_dim <= 0:
        return frame
    height, width = frame.shape[:2]
    longest = max(height, width)
    if longest <= max_dim:
        return frame

    import cv2

    scale = max_dim / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    # INTER_AREA is the right interpolation for shrinking.
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)


def extract_frames(
    path: str,
    *,
    target_fps: float,
    max_seconds: int,
    max_frames: int,
    max_frame_dim: int = 0,
) -> SampledFrames:
    """Decode ``path`` and return frames sampled down to ~``target_fps``.

    Each kept frame is downscaled so its longer side is at most ``max_frame_dim``
    pixels (0 disables), which keeps memory bounded on high-resolution clips.

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
                sampled.append((timestamp, fit_within(frame, max_frame_dim)))
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
