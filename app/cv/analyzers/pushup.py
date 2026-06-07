"""Push-up form analyzer.

Criteria (rule-based geometry):
- **Depth** — elbows should bend to roughly 90° at the bottom of each rep.
- **Lockout** — arms should fully extend at the top of each rep.
- **Body line** — shoulders→hips→ankles stay straight; flag sagging hips
  (lower-back injury risk) or piking hips.

Thresholds are named constants; coaching messages are templated per criterion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.cv.analyzers._common import elbow_angle, hip_sag_ratio
from app.cv.analyzers.base import ExerciseAnalysisResult, ExerciseAnalyzer, Remark
from app.cv.analyzers.registry import register
from app.cv.segmentation import count_reps
from app.cv.types import PoseSeries


@dataclass(frozen=True)
class PushupThresholds:
    good_depth_deg: float = 95.0  # bottom elbow angle at/below this == full depth
    shallow_depth_deg: float = 110.0  # at/above this == too shallow
    lockout_deg: float = 150.0  # top elbow angle below this == incomplete lockout
    sag_ratio: float = 0.12  # hip offset above this == sagging
    pike_ratio: float = -0.12  # below this == piking
    min_signal_range_deg: float = 25.0  # need this much elbow motion to call it reps
    rep_band: float = 0.25  # hysteresis band as a fraction of the signal range
    min_visibility: float = 0.3


class PushupAnalyzer(ExerciseAnalyzer):
    slug = "push_up"
    display_name = "Push-up"
    kind = "reps"

    def __init__(self, thresholds: PushupThresholds | None = None):
        self.t = thresholds or PushupThresholds()

    def analyze(self, series: PoseSeries) -> ExerciseAnalysisResult:
        t = self.t
        elbow_vals: list[float] = []
        sag_vals: list[float] = []
        timestamps: list[float] = []

        for frame in series.detected_frames():
            angle = elbow_angle(frame, t.min_visibility)
            if angle is None or np.isnan(angle):
                continue
            elbow_vals.append(angle)
            timestamps.append(frame.timestamp)
            sag = hip_sag_ratio(frame, t.min_visibility)
            sag_vals.append(sag if sag is not None else np.nan)

        if len(elbow_vals) < 3:
            return ExerciseAnalysisResult(
                score=0,
                remarks=[
                    Remark(
                        0.0,
                        "critical",
                        "body",
                        "Couldn't track the push-up clearly enough to analyze. "
                        "Film from the side with your whole body in frame.",
                    )
                ],
                tips=_BASE_TIPS,
                rep_count=0,
            )

        elbow = np.asarray(elbow_vals)
        sag = np.asarray(sag_vals)
        ts = np.asarray(timestamps)

        remarks: list[Remark] = []
        rep_count = 0
        shallow = 0
        poor_lockout = 0

        signal_range = float(elbow.max() - elbow.min())
        if signal_range < t.min_signal_range_deg:
            remarks.append(
                Remark(
                    float(ts[0]),
                    "warning",
                    "reps",
                    "Didn't detect full push-up repetitions — perform full "
                    "range-of-motion reps with your whole body in view.",
                )
            )
        else:
            low = elbow.min() + t.rep_band * signal_range
            high = elbow.max() - t.rep_band * signal_range
            reps = count_reps(elbow, low, high)
            rep_count = len(reps)
            for rep in reps:
                bottom_angle = float(elbow[rep.bottom_idx])
                top_angle = float(max(elbow[rep.start_idx], elbow[rep.end_idx]))
                if bottom_angle > t.shallow_depth_deg:
                    shallow += 1
                    if shallow <= 3:
                        remarks.append(
                            Remark(
                                float(ts[rep.bottom_idx]),
                                "warning",
                                "depth",
                                f"Shallow rep — only reached ~{bottom_angle:.0f}° at the "
                                "elbow. Lower until your elbows bend to about 90°.",
                            )
                        )
                if top_angle < t.lockout_deg:
                    poor_lockout += 1
                    if poor_lockout <= 2:
                        remarks.append(
                            Remark(
                                float(ts[rep.end_idx]),
                                "warning",
                                "lockout",
                                "Fully extend your arms at the top of each rep for a "
                                "complete lockout.",
                            )
                        )
            if rep_count > 0 and shallow == 0:
                remarks.append(
                    Remark(
                        float(ts[reps[0].bottom_idx]),
                        "info",
                        "depth",
                        "Good depth — elbows reaching a strong bottom position.",
                    )
                )

        worst_sag, worst_pike = self._body_line_remark(sag, ts, remarks)

        score = self._score(signal_range, rep_count, shallow, poor_lockout, worst_sag, worst_pike)
        return ExerciseAnalysisResult(
            score=score,
            remarks=remarks,
            tips=self._tips(shallow, poor_lockout, worst_sag, worst_pike),
            rep_count=rep_count,
            hold_seconds=None,
        )

    def _body_line_remark(self, sag, ts, remarks) -> tuple[float | None, float | None]:
        if not np.any(~np.isnan(sag)):
            return None, None
        t = self.t
        worst_sag = float(np.nanmax(sag))
        worst_pike = float(np.nanmin(sag))
        if worst_sag > t.sag_ratio:
            idx = int(np.nanargmax(sag))
            severity = "critical" if worst_sag > 2 * t.sag_ratio else "warning"
            remarks.append(
                Remark(
                    float(ts[idx]),
                    severity,
                    "hips",
                    "Hips are sagging — brace your core and squeeze your glutes to "
                    "keep a straight line from shoulders to ankles.",
                )
            )
        elif worst_pike < t.pike_ratio:
            idx = int(np.nanargmin(sag))
            remarks.append(
                Remark(
                    float(ts[idx]),
                    "warning",
                    "hips",
                    "Hips are piking up — lower your hips so your body forms a straight line.",
                )
            )
        else:
            remarks.append(
                Remark(float(ts[0]), "info", "hips", "Nice straight body line throughout.")
            )
        return worst_sag, worst_pike

    def _score(self, signal_range, rep_count, shallow, poor_lockout, worst_sag, worst_pike) -> int:
        t = self.t
        score = 100.0
        if signal_range >= t.min_signal_range_deg and rep_count > 0:
            score -= 30.0 * (shallow / rep_count)
            score -= 15.0 * (poor_lockout / rep_count)
        else:
            score -= 40.0
        if worst_sag is not None and worst_sag > t.sag_ratio:
            score -= min(30.0, 30.0 * (worst_sag / (2 * t.sag_ratio)))
        elif worst_pike is not None and worst_pike < t.pike_ratio:
            score -= min(15.0, 15.0 * (abs(worst_pike) / (2 * abs(t.pike_ratio))))
        return int(max(0.0, min(100.0, round(score))))

    def _tips(self, shallow, poor_lockout, worst_sag, worst_pike) -> list[str]:
        tips = list(_BASE_TIPS)
        if shallow:
            tips.append("Slow the descent and aim to lightly touch your chest toward the floor.")
        if poor_lockout:
            tips.append("Press all the way up until your elbows are straight before the next rep.")
        if worst_sag is not None and worst_sag > self.t.sag_ratio:
            tips.append("Strengthen your core (planks, hollow holds) to stop the hips dropping.")
        return tips


_BASE_TIPS = [
    "Keep your body in one straight line from head to heels.",
    "Tuck your elbows to roughly 45° from your torso, not flared straight out.",
]

register(PushupAnalyzer())
