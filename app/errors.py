"""Typed domain exceptions, raised in the cv/service layers and translated to
HTTP responses at the route edge (see ``app/main.py``)."""

from __future__ import annotations


class DigitalCoachError(Exception):
    """Base class for all application errors."""


class UnsupportedExerciseError(DigitalCoachError):
    def __init__(self, requested: str, supported: list[str]):
        self.requested = requested
        self.supported = supported
        super().__init__(
            f"Exercise '{requested}' is not supported yet. Supported: {', '.join(supported)}."
        )


class InvalidVideoError(DigitalCoachError):
    """The video could not be opened/decoded."""


class VideoTooLongError(DigitalCoachError):
    def __init__(self, duration: float, max_seconds: int):
        self.duration = duration
        self.max_seconds = max_seconds
        super().__init__(f"Video is {duration:.1f}s long; the limit is {max_seconds}s.")


class PoseNotDetectedError(DigitalCoachError):
    def __init__(self, detected_ratio: float, min_ratio: float):
        self.detected_ratio = detected_ratio
        self.min_ratio = min_ratio
        super().__init__(
            "Could not reliably track a body in the video "
            f"(usable in {detected_ratio:.0%} of frames, need {min_ratio:.0%}). "
            "Ensure the full body is visible with good lighting and a clear background."
        )


class StorageDownloadError(DigitalCoachError):
    """Failed to download a video from the provided storage reference."""
