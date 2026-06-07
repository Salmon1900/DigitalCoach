"""Synthetic pose-series builders shared across analyzer tests.

These construct geometrically consistent side-view skeletons so analyzers compute
the joint angles we intend — no real video or MediaPipe needed.
"""

from __future__ import annotations

import numpy as np

from app.cv.types import NUM_LANDMARKS, PoseFrame, PoseSeries
from app.cv.types import PoseLandmark as L

# Side-view layout (normalized coords, y grows downward).
_BODY_Y = 0.5
_SHOULDER_X = 0.35
_HIP_X = 0.62
_ANKLE_X = 0.85
_KNEE_X = 0.74
_TORSO = _HIP_X - _SHOULDER_X  # horizontal shoulder→hip distance


def _arm_points(shoulder: np.ndarray, elbow_deg: float, upper=0.10, fore=0.10, alpha_deg=80.0):
    """Place elbow/wrist so angle(shoulder, elbow, wrist) == elbow_deg."""
    alpha = np.radians(alpha_deg)
    elbow = shoulder + upper * np.array([np.cos(alpha), np.sin(alpha)])
    es = shoulder - elbow
    es_u = es / np.linalg.norm(es)
    theta = np.radians(elbow_deg)
    best = None
    for sign in (1.0, -1.0):
        c, s = np.cos(sign * theta), np.sin(sign * theta)
        rot = np.array([[c, -s], [s, c]])
        wrist = elbow + fore * (rot @ es_u)
        if best is None or wrist[1] > best[1][1]:  # prefer wrist nearer the ground
            best = (elbow, wrist)
    return best


def pushup_frame_landmarks(elbow_deg: float, sag_ratio: float, visibility: float) -> np.ndarray:
    """Build a (33,4) landmark array for a side-view push-up pose."""
    arr = np.zeros((NUM_LANDMARKS, 4), dtype=float)
    arr[:, :2] = 0.5  # neutral default for unused landmarks
    arr[:, 3] = 0.0

    shoulder = np.array([_SHOULDER_X, _BODY_Y])
    ankle = np.array([_ANKLE_X, _BODY_Y])
    hip = np.array([_HIP_X, _BODY_Y + sag_ratio * _TORSO])
    knee = np.array([_KNEE_X, _BODY_Y + 0.5 * sag_ratio * _TORSO])
    elbow, wrist = _arm_points(shoulder, elbow_deg)

    def setp(idx: L, p: np.ndarray) -> None:
        arr[int(idx), 0] = p[0]
        arr[int(idx), 1] = p[1]
        arr[int(idx), 3] = visibility

    for left, right, point in (
        (L.LEFT_SHOULDER, L.RIGHT_SHOULDER, shoulder),
        (L.LEFT_ELBOW, L.RIGHT_ELBOW, elbow),
        (L.LEFT_WRIST, L.RIGHT_WRIST, wrist),
        (L.LEFT_HIP, L.RIGHT_HIP, hip),
        (L.LEFT_KNEE, L.RIGHT_KNEE, knee),
        (L.LEFT_ANKLE, L.RIGHT_ANKLE, ankle),
    ):
        setp(left, point)
        setp(right, point)

    return arr


def build_pushup_series(
    *,
    reps: int = 3,
    top: float = 170.0,
    bottom: float = 80.0,
    sag_ratio: float = 0.0,
    fps: float = 10.0,
    frames_per_phase: int = 6,
    visibility: float = 0.9,
) -> PoseSeries:
    """A push-up clip: ``reps`` descent/ascent cycles of the elbow angle."""
    thetas: list[float] = [top, top]  # brief hold at the top to start
    for _ in range(reps):
        thetas.extend(np.linspace(top, bottom, frames_per_phase).tolist())
        thetas.extend(np.linspace(bottom, top, frames_per_phase).tolist())

    frames = [
        PoseFrame(
            timestamp=i / fps,
            landmarks=pushup_frame_landmarks(theta, sag_ratio, visibility),
        )
        for i, theta in enumerate(thetas)
    ]
    return PoseSeries(frames=frames, sample_fps=fps)


# --------------------------------------------------------------------------- #
# Pull-up (front view, vertical pull)                                          #
# --------------------------------------------------------------------------- #


def _vertical_arm(shoulder, elbow_deg, upper=0.12, fore=0.12, up=True):
    """Place elbow/wrist so angle(shoulder, elbow, wrist) == elbow_deg, arm up/down."""
    direction = -1.0 if up else 1.0
    elbow = shoulder + np.array([0.02, direction * upper])
    es_u = (shoulder - elbow) / np.linalg.norm(shoulder - elbow)
    theta = np.radians(elbow_deg)
    best = None
    for sign in (1.0, -1.0):
        c, s = np.cos(sign * theta), np.sin(sign * theta)
        wrist = elbow + fore * (np.array([[c, -s], [s, c]]) @ es_u)
        key = -wrist[1] if up else wrist[1]  # prefer wrist toward the bar (up) / floor
        if best is None or key > best[0]:
            best = (key, (elbow, wrist))
    return best[1]


def pullup_frame_landmarks(elbow_deg: float, hip_x: float, visibility: float) -> np.ndarray:
    arr = np.zeros((NUM_LANDMARKS, 4), dtype=float)
    arr[:, :2] = 0.5
    arr[:, 3] = 0.0

    shoulder_l = np.array([0.43, 0.40])
    shoulder_r = np.array([0.57, 0.40])
    elbow_l, wrist_l = _vertical_arm(shoulder_l, elbow_deg, up=True)
    elbow_r, wrist_r = _vertical_arm(shoulder_r, elbow_deg, up=True)
    hip_l = np.array([hip_x - 0.05, 0.72])
    hip_r = np.array([hip_x + 0.05, 0.72])
    nose = np.array([0.5, 0.32])

    def setp(idx: L, p) -> None:
        arr[int(idx), 0] = p[0]
        arr[int(idx), 1] = p[1]
        arr[int(idx), 3] = visibility

    setp(L.NOSE, nose)
    for left, right, pl, pr in (
        (L.LEFT_SHOULDER, L.RIGHT_SHOULDER, shoulder_l, shoulder_r),
        (L.LEFT_ELBOW, L.RIGHT_ELBOW, elbow_l, elbow_r),
        (L.LEFT_WRIST, L.RIGHT_WRIST, wrist_l, wrist_r),
        (L.LEFT_HIP, L.RIGHT_HIP, hip_l, hip_r),
    ):
        setp(left, pl)
        setp(right, pr)
    return arr


def build_pullup_series(
    *,
    reps: int = 3,
    hang: float = 172.0,
    top: float = 60.0,
    swing: float = 0.0,
    fps: float = 10.0,
    frames_per_phase: int = 6,
    visibility: float = 0.9,
) -> PoseSeries:
    """A pull-up clip: elbow angle drops (pull up) then rises (lower) per rep."""
    thetas: list[float] = [hang, hang]
    for _ in range(reps):
        thetas.extend(np.linspace(hang, top, frames_per_phase).tolist())
        thetas.extend(np.linspace(top, hang, frames_per_phase).tolist())

    period = 2 * frames_per_phase
    frames = [
        PoseFrame(
            timestamp=i / fps,
            landmarks=pullup_frame_landmarks(
                theta, 0.5 + swing * np.sin(2 * np.pi * i / period), visibility
            ),
        )
        for i, theta in enumerate(thetas)
    ]
    return PoseSeries(frames=frames, sample_fps=fps)


# --------------------------------------------------------------------------- #
# Pike push-up (side view, piked hips)                                         #
# --------------------------------------------------------------------------- #


def pike_frame_landmarks(elbow_deg: float, hip_angle_deg: float, visibility: float) -> np.ndarray:
    arr = np.zeros((NUM_LANDMARKS, 4), dtype=float)
    arr[:, :2] = 0.5
    arr[:, 3] = 0.0

    hip = np.array([0.5, 0.25])
    beta = np.radians(hip_angle_deg / 2)
    limb = 0.22
    shoulder = hip + limb * np.array([-np.sin(beta), np.cos(beta)])
    ankle = hip + limb * np.array([np.sin(beta), np.cos(beta)])
    knee = (hip + ankle) / 2
    elbow, wrist = _arm_points(shoulder, elbow_deg)

    def setp(idx: L, p) -> None:
        arr[int(idx), 0] = p[0]
        arr[int(idx), 1] = p[1]
        arr[int(idx), 3] = visibility

    for left, right, point in (
        (L.LEFT_SHOULDER, L.RIGHT_SHOULDER, shoulder),
        (L.LEFT_ELBOW, L.RIGHT_ELBOW, elbow),
        (L.LEFT_WRIST, L.RIGHT_WRIST, wrist),
        (L.LEFT_HIP, L.RIGHT_HIP, hip),
        (L.LEFT_KNEE, L.RIGHT_KNEE, knee),
        (L.LEFT_ANKLE, L.RIGHT_ANKLE, ankle),
    ):
        setp(left, point)
        setp(right, point)
    return arr


def build_pike_series(
    *,
    reps: int = 3,
    top: float = 160.0,
    bottom: float = 80.0,
    hip_angle: float = 70.0,
    fps: float = 10.0,
    frames_per_phase: int = 6,
    visibility: float = 0.9,
) -> PoseSeries:
    """A pike push-up clip: elbow sweep with hips held in a pike."""
    thetas: list[float] = [top, top]
    for _ in range(reps):
        thetas.extend(np.linspace(top, bottom, frames_per_phase).tolist())
        thetas.extend(np.linspace(bottom, top, frames_per_phase).tolist())

    frames = [
        PoseFrame(timestamp=i / fps, landmarks=pike_frame_landmarks(theta, hip_angle, visibility))
        for i, theta in enumerate(thetas)
    ]
    return PoseSeries(frames=frames, sample_fps=fps)


# --------------------------------------------------------------------------- #
# Handstand (inverted hold)                                                    #
# --------------------------------------------------------------------------- #


def handstand_frame_landmarks(
    tilt_deg: float, arch: float, sway_x: float, visibility: float
) -> np.ndarray:
    arr = np.zeros((NUM_LANDMARKS, 4), dtype=float)
    arr[:, :2] = 0.5
    arr[:, 3] = 0.0

    base_x = 0.5 + sway_x
    wrist_mid = np.array([base_x, 0.90])
    height = 0.70
    top_dx = height * np.tan(np.radians(tilt_deg))
    ankle_mid = np.array([base_x + top_dx, 0.90 - height])

    line = ankle_mid - wrist_mid
    unit = line / np.linalg.norm(line)
    perp = np.array([-unit[1], unit[0]])
    shoulder = wrist_mid + 0.30 * line
    hip = wrist_mid + 0.60 * line + arch * perp

    def setp(idx: L, p) -> None:
        arr[int(idx), 0] = p[0]
        arr[int(idx), 1] = p[1]
        arr[int(idx), 3] = visibility

    for left, right, point in (
        (L.LEFT_WRIST, L.RIGHT_WRIST, wrist_mid + np.array([-0.04, 0])),
        (L.LEFT_SHOULDER, L.RIGHT_SHOULDER, shoulder),
        (L.LEFT_HIP, L.RIGHT_HIP, hip),
        (L.LEFT_ANKLE, L.RIGHT_ANKLE, ankle_mid),
    ):
        setp(left, point)
        setp(right, point)
    # Give paired landmarks a slight L/R spread so midpoints/widths are well defined.
    arr[int(L.RIGHT_WRIST), 0] = wrist_mid[0] + 0.04
    arr[int(L.RIGHT_ANKLE), 0] = ankle_mid[0] + 0.04
    arr[int(L.LEFT_ANKLE), 0] = ankle_mid[0] - 0.04
    arr[int(L.LEFT_SHOULDER), 0] = shoulder[0] - 0.04
    arr[int(L.RIGHT_SHOULDER), 0] = shoulder[0] + 0.04
    arr[int(L.LEFT_HIP), 0] = hip[0] - 0.04
    arr[int(L.RIGHT_HIP), 0] = hip[0] + 0.04
    return arr


def build_handstand_series(
    *,
    seconds: float = 3.0,
    tilt: float = 5.0,
    arch: float = 0.0,
    sway: float = 0.0,
    fps: float = 10.0,
    visibility: float = 0.9,
) -> PoseSeries:
    """An inverted hold of ``seconds`` with given tilt/arch/sway."""
    n = max(1, int(seconds * fps))
    frames = [
        PoseFrame(
            timestamp=i / fps,
            landmarks=handstand_frame_landmarks(
                tilt, arch, sway * np.sin(2 * np.pi * i / max(1, n - 1)), visibility
            ),
        )
        for i in range(n)
    ]
    return PoseSeries(frames=frames, sample_fps=fps)
