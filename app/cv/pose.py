"""MediaPipe Pose estimation: turns sampled frames into a :class:`PoseSeries`.

``mediapipe`` and ``cv2`` are imported lazily so the rest of the pipeline stays
importable without them.
"""

from __future__ import annotations

import numpy as np

from app.cv.frames import SampledFrames
from app.cv.types import NUM_LANDMARKS, PoseFrame, PoseSeries


def estimate_pose(
    sampled: SampledFrames,
    *,
    model_complexity: int = 1,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> PoseSeries:
    """Run MediaPipe Pose over the sampled frames.

    Frames where no pose is found yield a :class:`PoseFrame` with ``landmarks=None``.
    """
    import cv2
    import mediapipe as mp

    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=model_complexity,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )

    frames: list[PoseFrame] = []
    try:
        for timestamp, bgr in sampled.frames:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)
            landmarks = result.pose_landmarks
            if landmarks is None:
                frames.append(PoseFrame(timestamp=timestamp, landmarks=None))
                continue
            arr = np.array(
                [[lm.x, lm.y, lm.z, lm.visibility] for lm in landmarks.landmark],
                dtype=float,
            )
            if arr.shape[0] != NUM_LANDMARKS:
                frames.append(PoseFrame(timestamp=timestamp, landmarks=None))
            else:
                frames.append(PoseFrame(timestamp=timestamp, landmarks=arr))
    finally:
        pose.close()

    return PoseSeries(frames=frames, sample_fps=sampled.sample_fps)
