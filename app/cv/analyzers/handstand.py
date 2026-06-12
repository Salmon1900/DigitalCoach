"""Handstand form analyzer (a timed hold, not reps).

Criteria (rule-based geometry):
- **Alignment** — wrists, shoulders, hips and ankles stack vertically over the hands.
- **Straight body** — avoid the arched "banana back" (lower-back injury risk).
- **Balance** — minimal side-to-side sway.
- **Hold time** — how long a stable inverted position was maintained.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.cv.analyzers._common import body_line_angle, body_vertical_tilt, shoulder_width
from app.cv.analyzers.base import ExerciseAnalysisResult, ExerciseAnalyzer, Remark
from app.cv.analyzers.registry import register
from app.cv.holds import hold_metrics
from app.cv.types import PoseFrame, PoseSeries
from app.cv.types import PoseLandmark as L


@dataclass(frozen=True)
class HandstandThresholds:
    max_tilt_deg: float = 12.0  # body tilt from vertical above this == off balance
    min_straight_deg: float = 165.0  # shoulder-hip-ankle below this == arched back
    sway_ratio: float = 0.5  # shoulder horizontal sway / shoulder width
    min_hold_seconds: float = 1.0
    min_visibility: float = 0.3
    max_gap_frames: int = 1  # bridge this many dropped/jittered frames within a hold


def _mean_shoulder_x(frame: PoseFrame, min_visibility: float) -> float | None:
    xs = [
        frame.point(j)[0]
        for j in (L.LEFT_SHOULDER, L.RIGHT_SHOULDER)
        if frame.visibility(j) >= min_visibility
    ]
    return float(np.mean(xs)) if xs else None


class HandstandAnalyzer(ExerciseAnalyzer):
    slug = "handstand"
    display_name = "Handstand"
    kind = "timed"

    def __init__(self, thresholds: HandstandThresholds | None = None):
        self.t = thresholds or HandstandThresholds()

    def _in_position(self, series: PoseSeries) -> list[bool]:
        """Per-frame (full timeline) flag: balanced AND straight this frame."""
        t = self.t
        flags: list[bool] = []
        for frame in series.frames:
            if not frame.detected:
                flags.append(False)
                continue
            tilt = body_vertical_tilt(frame, t.min_visibility)
            straight = body_line_angle(frame, t.min_visibility)
            ok = (
                tilt is not None
                and not np.isnan(tilt)
                and tilt <= t.max_tilt_deg
                and straight is not None
                and not np.isnan(straight)
                and straight >= t.min_straight_deg
            )
            flags.append(bool(ok))
        return flags

    def analyze(self, series: PoseSeries) -> ExerciseAnalysisResult:
        t = self.t
        tilts: list[float] = []
        straights: list[float] = []
        shoulder_xs: list[float] = []
        widths: list[float] = []
        timestamps: list[float] = []

        for frame in series.detected_frames():
            tilt = body_vertical_tilt(frame, t.min_visibility)
            if tilt is None or np.isnan(tilt):
                continue
            tilts.append(tilt)
            timestamps.append(frame.timestamp)
            straight = body_line_angle(frame, t.min_visibility)
            straights.append(straight if straight is not None else np.nan)
            sx = _mean_shoulder_x(frame, t.min_visibility)
            shoulder_xs.append(sx if sx is not None else np.nan)
            sw = shoulder_width(frame, t.min_visibility)
            widths.append(sw if sw is not None else np.nan)

        flags = self._in_position(series)
        if series.sample_fps:
            metrics = hold_metrics(flags, series.sample_fps, t.max_gap_frames)
            hold_seconds = metrics.longest_seconds
            total_hold_seconds = metrics.total_seconds
        else:
            hold_seconds = total_hold_seconds = 0.0

        if len(tilts) < 3:
            return ExerciseAnalysisResult(
                score=0,
                remarks=[
                    Remark(
                        0.0,
                        "critical",
                        "body",
                        "Couldn't track a handstand clearly enough to analyze. "
                        "Film the whole body with hands and feet in frame.",
                    )
                ],
                tips=_BASE_TIPS,
                rep_count=None,
                hold_seconds=hold_seconds,
                total_hold_seconds=total_hold_seconds,
            )

        tilt = np.asarray(tilts)
        straight = np.asarray(straights)
        ts = np.asarray(timestamps)

        remarks: list[Remark] = []

        median_tilt = float(np.median(tilt))
        off_balance = median_tilt > t.max_tilt_deg
        if off_balance:
            idx = int(np.argmax(tilt))
            remarks.append(
                Remark(
                    float(ts[idx]),
                    "warning",
                    "balance",
                    "Body is tilting off vertical — stack your hips and feet directly "
                    "over your hands.",
                )
            )

        min_straight = float(np.nanmin(straight)) if np.any(~np.isnan(straight)) else 180.0
        arched = min_straight < t.min_straight_deg
        if arched:
            idx = int(np.nanargmin(straight))
            remarks.append(
                Remark(
                    float(ts[idx]),
                    "critical",
                    "back",
                    "Arched 'banana' back — posterior pelvic tilt: squeeze glutes and ribs "
                    "down to straighten, protecting your lower back.",
                )
            )

        sway = self._sway(shoulder_xs, widths)
        if sway is not None and sway > t.sway_ratio:
            remarks.append(
                Remark(
                    float(ts[0]),
                    "warning",
                    "balance",
                    "Lots of side-to-side sway — press through your fingertips to balance.",
                )
            )

        short_hold = hold_seconds < t.min_hold_seconds
        if short_hold:
            remarks.append(
                Remark(
                    0.0,
                    "info",
                    "hold",
                    f"Held for ~{hold_seconds:.1f}s — work toward longer, stable holds.",
                )
            )
        elif not (off_balance or arched):
            remarks.append(
                Remark(
                    0.0, "info", "hold", f"Solid, stable handstand held for ~{hold_seconds:.1f}s."
                )
            )

        score = self._score(off_balance, median_tilt, arched, sway, short_hold)
        return ExerciseAnalysisResult(
            score=score,
            remarks=remarks,
            tips=self._tips(off_balance, arched, sway),
            rep_count=None,
            hold_seconds=hold_seconds,
            total_hold_seconds=total_hold_seconds,
        )

    def _sway(self, shoulder_xs, widths) -> float | None:
        sx = np.asarray(shoulder_xs)
        w = np.asarray(widths)
        if not np.any(~np.isnan(sx)) or not np.any(~np.isnan(w)):
            return None
        width = float(np.nanmedian(w))
        if width <= 1e-6:
            return None
        return float(np.nanmax(sx) - np.nanmin(sx)) / width

    def _score(self, off_balance, median_tilt, arched, sway, short_hold) -> int:
        t = self.t
        score = 100.0
        if off_balance:
            score -= min(30.0, 30.0 * (median_tilt / (2 * t.max_tilt_deg)))
        if arched:
            score -= 30.0
        if sway is not None and sway > t.sway_ratio:
            score -= min(20.0, 20.0 * (sway / (2 * t.sway_ratio)))
        if short_hold:
            score -= 20.0
        return int(max(0.0, min(100.0, round(score))))

    def _tips(self, off_balance, arched, sway) -> list[str]:
        tips = list(_BASE_TIPS)
        if off_balance:
            tips.append("Find a hollow shape: ribs in, hips stacked over shoulders and wrists.")
        if arched:
            tips.append("Practice hollow-body holds to fix the banana-back arch.")
        if sway is not None and sway > self.t.sway_ratio:
            tips.append("Balance with fingertip pressure rather than swinging at the hips.")
        return tips


_BASE_TIPS = [
    "Push tall through the shoulders and keep your gaze between your hands.",
    "Build the hold against a wall first, then practice freestanding balance.",
]

register(HandstandAnalyzer())
