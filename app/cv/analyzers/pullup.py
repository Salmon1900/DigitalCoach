"""Pull-up form analyzer.

Criteria (rule-based geometry, filmed from the front):
- **Full dead hang** — arms should fully straighten at the bottom of each rep.
- **Pull height** — elbows should bend enough at the top (chin over the bar).
- **Swing / kipping** — minimal horizontal hip movement; a strict pull-up is controlled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.cv.analyzers._common import elbow_angle, mean_hip_x, shoulder_width
from app.cv.analyzers.base import ExerciseAnalysisResult, ExerciseAnalyzer, Remark
from app.cv.analyzers.registry import register
from app.cv.segmentation import count_reps
from app.cv.types import PoseSeries


@dataclass(frozen=True)
class PullupThresholds:
    full_hang_deg: float = 160.0  # max elbow angle should reach this at the bottom
    pulled_deg: float = 95.0  # min elbow angle at the top should be at/below this
    swing_ratio: float = 0.6  # hip horizontal range / shoulder width
    min_signal_range_deg: float = 30.0
    rep_band: float = 0.25
    min_visibility: float = 0.3


class PullupAnalyzer(ExerciseAnalyzer):
    slug = "pull_up"
    display_name = "Pull-up"
    kind = "reps"

    def __init__(self, thresholds: PullupThresholds | None = None):
        self.t = thresholds or PullupThresholds()

    def analyze(self, series: PoseSeries) -> ExerciseAnalysisResult:
        t = self.t
        elbow_vals: list[float] = []
        hip_xs: list[float] = []
        widths: list[float] = []
        timestamps: list[float] = []

        for frame in series.detected_frames():
            angle = elbow_angle(frame, t.min_visibility)
            if angle is None or np.isnan(angle):
                continue
            elbow_vals.append(angle)
            timestamps.append(frame.timestamp)
            hx = mean_hip_x(frame, t.min_visibility)
            hip_xs.append(hx if hx is not None else np.nan)
            sw = shoulder_width(frame, t.min_visibility)
            widths.append(sw if sw is not None else np.nan)

        if len(elbow_vals) < 3:
            return ExerciseAnalysisResult(
                score=0,
                remarks=[
                    Remark(
                        0.0,
                        "critical",
                        "body",
                        "Couldn't track the pull-up clearly enough to analyze. "
                        "Film from the front with your whole body in frame.",
                    )
                ],
                tips=_BASE_TIPS,
                rep_count=0,
            )

        elbow = np.asarray(elbow_vals)
        ts = np.asarray(timestamps)
        hip_x = np.asarray(hip_xs)
        widths_arr = np.asarray(widths)

        remarks: list[Remark] = []
        rep_count = 0
        shallow_pulls = 0
        signal_range = float(elbow.max() - elbow.min())

        if signal_range < t.min_signal_range_deg:
            remarks.append(
                Remark(
                    float(ts[0]),
                    "warning",
                    "reps",
                    "Didn't detect full pull-up repetitions — perform complete reps "
                    "from a dead hang to chin over the bar.",
                )
            )
        else:
            low = elbow.min() + t.rep_band * signal_range
            high = elbow.max() - t.rep_band * signal_range
            reps = count_reps(elbow, low, high)
            rep_count = len(reps)
            for rep in reps:
                top_elbow = float(elbow[rep.bottom_idx])  # most bent == top of pull-up
                if top_elbow > t.pulled_deg:
                    shallow_pulls += 1
                    if shallow_pulls <= 3:
                        remarks.append(
                            Remark(
                                float(ts[rep.bottom_idx]),
                                "warning",
                                "height",
                                "Pull higher — aim to get your chin over the bar at the "
                                "top of each rep.",
                            )
                        )

        max_elbow = float(elbow.max())
        incomplete_hang = max_elbow < t.full_hang_deg
        if incomplete_hang:
            idx = int(np.argmax(elbow))
            remarks.append(
                Remark(
                    float(ts[idx]),
                    "warning",
                    "range",
                    "Lower all the way to a full dead hang (arms straight) between reps.",
                )
            )

        swing = self._swing(hip_x, widths_arr)
        if swing is not None and swing > t.swing_ratio:
            idx = int(np.nanargmax(hip_x))
            remarks.append(
                Remark(
                    float(ts[idx]),
                    "warning",
                    "swing",
                    "Too much swinging/kipping — keep your core tight and pull in a straight line.",
                )
            )

        if rep_count > 0 and shallow_pulls == 0 and not incomplete_hang:
            remarks.append(
                Remark(float(ts[0]), "info", "range", "Clean full-range reps — nice work.")
            )

        score = self._score(signal_range, rep_count, shallow_pulls, incomplete_hang, swing)
        return ExerciseAnalysisResult(
            score=score,
            remarks=remarks,
            tips=self._tips(shallow_pulls, incomplete_hang, swing),
            rep_count=rep_count,
            hold_seconds=None,
        )

    def _swing(self, hip_x, widths) -> float | None:
        if not np.any(~np.isnan(hip_x)) or not np.any(~np.isnan(widths)):
            return None
        width = float(np.nanmedian(widths))
        if width <= 1e-6:
            return None
        return float(np.nanmax(hip_x) - np.nanmin(hip_x)) / width

    def _score(self, signal_range, rep_count, shallow_pulls, incomplete_hang, swing) -> int:
        t = self.t
        score = 100.0
        if signal_range >= t.min_signal_range_deg and rep_count > 0:
            score -= 30.0 * (shallow_pulls / rep_count)
        else:
            score -= 40.0
        if incomplete_hang:
            score -= 15.0
        if swing is not None and swing > t.swing_ratio:
            score -= min(20.0, 20.0 * (swing / (2 * t.swing_ratio)))
        return int(max(0.0, min(100.0, round(score))))

    def _tips(self, shallow_pulls, incomplete_hang, swing) -> list[str]:
        tips = list(_BASE_TIPS)
        if shallow_pulls:
            tips.append("Drive your elbows down and back to clear the bar with your chin.")
        if incomplete_hang:
            tips.append(
                "Full range builds strength — straighten the arms completely at the bottom."
            )
        if swing is not None and swing > self.t.swing_ratio:
            tips.append("Squeeze your glutes and brace your abs to stop the legs swinging.")
        return tips


_BASE_TIPS = [
    "Start each rep from a controlled dead hang with shoulders engaged.",
    "Pull your shoulder blades down and together as you rise.",
]

register(PullupAnalyzer())
