"""Pike push-up form analyzer.

A pike push-up is a push-up performed with the hips piked high (an inverted-V),
shifting load to the shoulders — a handstand-push-up progression.

Criteria (rule-based geometry, filmed from the side):
- **Pike position** — hips stay high; the shoulder-hip-ankle angle is acute.
- **Depth** — elbows bend so the head travels toward the floor between the hands.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.cv.analyzers._common import body_line_angle, elbow_angle
from app.cv.analyzers.base import ExerciseAnalysisResult, ExerciseAnalyzer, Remark
from app.cv.analyzers.registry import register
from app.cv.segmentation import count_reps
from app.cv.types import PoseSeries


@dataclass(frozen=True)
class PikeThresholds:
    pike_max_deg: float = 120.0  # hip angle above this == not enough pike
    shallow_depth_deg: float = 110.0  # bottom elbow angle above this == too shallow
    min_signal_range_deg: float = 25.0
    rep_band: float = 0.25
    min_visibility: float = 0.3


class PikePushupAnalyzer(ExerciseAnalyzer):
    slug = "pike_push_up"
    display_name = "Pike Push-up"
    kind = "reps"

    def __init__(self, thresholds: PikeThresholds | None = None):
        self.t = thresholds or PikeThresholds()

    def analyze(self, series: PoseSeries) -> ExerciseAnalysisResult:
        t = self.t
        elbow_vals: list[float] = []
        hip_angles: list[float] = []
        timestamps: list[float] = []

        for frame in series.detected_frames():
            angle = elbow_angle(frame, t.min_visibility)
            if angle is None or np.isnan(angle):
                continue
            elbow_vals.append(angle)
            timestamps.append(frame.timestamp)
            hip = body_line_angle(frame, t.min_visibility)
            hip_angles.append(hip if hip is not None else np.nan)

        if len(elbow_vals) < 3:
            return ExerciseAnalysisResult(
                score=0,
                remarks=[
                    Remark(
                        0.0,
                        "critical",
                        "body",
                        "Couldn't track the pike push-up clearly enough to analyze. "
                        "Film from the side with your whole body in frame.",
                    )
                ],
                tips=_BASE_TIPS,
                rep_count=0,
            )

        elbow = np.asarray(elbow_vals)
        ts = np.asarray(timestamps)
        hip = np.asarray(hip_angles)

        remarks: list[Remark] = []
        rep_count = 0
        shallow = 0
        signal_range = float(elbow.max() - elbow.min())

        if signal_range < t.min_signal_range_deg:
            remarks.append(
                Remark(
                    float(ts[0]),
                    "warning",
                    "reps",
                    "Didn't detect full pike push-up repetitions — perform complete reps.",
                )
            )
        else:
            low = elbow.min() + t.rep_band * signal_range
            high = elbow.max() - t.rep_band * signal_range
            reps = count_reps(elbow, low, high)
            rep_count = len(reps)
            for rep in reps:
                bottom_angle = float(elbow[rep.bottom_idx])
                if bottom_angle > t.shallow_depth_deg:
                    shallow += 1
                    if shallow <= 3:
                        remarks.append(
                            Remark(
                                float(ts[rep.bottom_idx]),
                                "warning",
                                "depth",
                                "Shallow rep — lower your head toward the floor between "
                                "your hands for full range.",
                            )
                        )

        not_piked = self._pike_remark(hip, ts, remarks)

        score = self._score(signal_range, rep_count, shallow, not_piked)
        return ExerciseAnalysisResult(
            score=score,
            remarks=remarks,
            tips=self._tips(shallow, not_piked),
            rep_count=rep_count,
            hold_seconds=None,
        )

    def _pike_remark(self, hip, ts, remarks) -> bool:
        if not np.any(~np.isnan(hip)):
            return False
        median_hip = float(np.nanmedian(hip))
        if median_hip > self.t.pike_max_deg:
            idx = int(np.nanargmax(hip))
            remarks.append(
                Remark(
                    float(ts[idx]),
                    "warning",
                    "hips",
                    "Pike your hips higher — walk your feet in and lift your hips so your "
                    "torso is more vertical.",
                )
            )
            return True
        remarks.append(
            Remark(float(ts[0]), "info", "hips", "Good pike position — hips nice and high.")
        )
        return False

    def _score(self, signal_range, rep_count, shallow, not_piked) -> int:
        t = self.t
        score = 100.0
        if signal_range >= t.min_signal_range_deg and rep_count > 0:
            score -= 30.0 * (shallow / rep_count)
        else:
            score -= 40.0
        if not_piked:
            score -= 25.0
        return int(max(0.0, min(100.0, round(score))))

    def _tips(self, shallow, not_piked) -> list[str]:
        tips = list(_BASE_TIPS)
        if shallow:
            tips.append("Control the descent until the crown of your head nears the floor.")
        if not_piked:
            tips.append("The higher the hips, the more this trains the handstand push-up.")
        return tips


_BASE_TIPS = [
    "Keep your hips high so the load stays on your shoulders, not your chest.",
    "Look slightly back between your hands to protect your neck.",
]

register(PikePushupAnalyzer())
