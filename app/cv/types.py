"""Core data types flowing through the CV pipeline.

These are intentionally free of any MediaPipe/OpenCV imports so the geometry and
analyzer layers can be unit-tested on synthetic data without heavy dependencies.

Coordinate convention (matches MediaPipe): normalized image coordinates where
``x`` grows rightward and ``y`` grows *downward* (0 = top, 1 = bottom). Each
landmark row is ``[x, y, z, visibility]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np

# Number of landmarks emitted by MediaPipe Pose.
NUM_LANDMARKS = 33


class PoseLandmark(IntEnum):
    """Subset of MediaPipe Pose landmark indices we reason about."""

    NOSE = 0
    LEFT_EAR = 7
    RIGHT_EAR = 8
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28


@dataclass
class PoseFrame:
    """A single sampled frame's pose.

    ``landmarks`` is an ``(33, 4)`` array of ``[x, y, z, visibility]`` or ``None``
    when no pose was detected in the frame.
    """

    timestamp: float
    landmarks: np.ndarray | None

    @property
    def detected(self) -> bool:
        return self.landmarks is not None

    def point(self, landmark: PoseLandmark) -> np.ndarray:
        """Return the ``(x, y)`` image-plane coordinates of a landmark."""
        if self.landmarks is None:
            raise ValueError("No pose detected in this frame")
        return self.landmarks[int(landmark), :2]

    def visibility(self, landmark: PoseLandmark) -> float:
        if self.landmarks is None:
            return 0.0
        return float(self.landmarks[int(landmark), 3])


@dataclass
class PoseSeries:
    """An ordered, time-stamped sequence of pose frames."""

    frames: list[PoseFrame]
    sample_fps: float

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def duration(self) -> float:
        if not self.frames:
            return 0.0
        return self.frames[-1].timestamp

    @property
    def detected_ratio(self) -> float:
        if not self.frames:
            return 0.0
        return sum(f.detected for f in self.frames) / len(self.frames)

    def detected_frames(self) -> list[PoseFrame]:
        return [f for f in self.frames if f.detected]


@dataclass(frozen=True)
class RepSegment:
    """One repetition: indices into the (detected-frame) signal."""

    start_idx: int
    bottom_idx: int
    end_idx: int
