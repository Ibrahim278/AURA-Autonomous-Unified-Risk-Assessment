"""Alert engine: turns readings into Normal / Warning / Critical assessments.

Rules, in order of precedence (all are PROTOTYPE rules, not clinically validated):

1. Critical: the latest reading crosses an indicator's absolute critical limit.
2. Warning (absolute): the latest reading crosses an absolute warning limit.
3. Warning (sustained deviation): the last ``SUSTAINED_WINDOW`` readings all sit on the
   adverse side of the astronaut's personal baseline by at least ``SUSTAINED_Z_EACH`` standard
   deviations, the mean of that window is at least ``SUSTAINED_Z_MEAN`` SD away, and the shift
   is at least the indicator's ``min_meaningful_change``.
4. Warning (unusual reading): a single reading at least ``SPIKE_Z`` SD from baseline in the
   adverse direction, with a shift of at least 2x ``min_meaningful_change``.
5. Otherwise: Normal.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable, Sequence

from .indicators import BodySystem, Direction, Indicator

SUSTAINED_WINDOW = 3
SUSTAINED_Z_EACH = 1.5
SUSTAINED_Z_MEAN = 2.0
SPIKE_Z = 3.5
TREND_WINDOW = 7
MIN_BASELINE_READINGS = 3


class Level(IntEnum):
    NORMAL = 0
    WARNING = 1
    CRITICAL = 2

    @property
    def label(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Reading:
    day: int
    value: float
    source: str = "synthetic"  # synthetic | research | manual
    timestamp: str | None = None


@dataclass(frozen=True)
class Baseline:
    mean: float
    sd: float
    n: int

    @classmethod
    def from_values(cls, values: Sequence[float], indicator: Indicator) -> "Baseline":
        if len(values) < MIN_BASELINE_READINGS:
            raise ValueError(
                f"Need at least {MIN_BASELINE_READINGS} baseline readings for {indicator.key}"
            )
        mean = statistics.fmean(values)
        sd = statistics.stdev(values)
        # Floor the SD so a very stable baseline doesn't make every tiny wobble "significant".
        sd = max(sd, indicator.min_meaningful_change / 2)
        return cls(mean=mean, sd=sd, n=len(values))


@dataclass
class Assessment:
    indicator: Indicator
    level: Level
    value: float | None
    day: int | None
    source: str | None
    baseline: Baseline | None
    z_score: float | None
    deviation: float | None
    trend: str
    reasons: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    escalate: bool = False

    def to_dict(self) -> dict:
        ind = self.indicator
        r = ind.decimals
        return {
            "indicator": ind.key,
            "name": ind.name,
            "unit": ind.unit,
            "body_system": ind.body_system.value,
            "custom": ind.custom,
            "level": self.level.label,
            "value": None if self.value is None else round(self.value, r),
            "day": self.day,
            "source": self.source,
            "baseline": None
            if self.baseline is None
            else {
                "mean": round(self.baseline.mean, r + 1),
                "sd": round(self.baseline.sd, r + 1),
                "n": self.baseline.n,
            },
            "z_score": None if self.z_score is None else round(self.z_score, 2),
            "deviation": None if self.deviation is None else round(self.deviation, r + 1),
            "trend": self.trend,
            "reasons": self.reasons,
            "actions": self.actions,
            "escalate": self.escalate,
        }


def _fmt(value: float, ind: Indicator) -> str:
    return f"{value:.{ind.decimals}f} {ind.unit}".replace(" %", "%").replace(" /10", "/10")


def _is_adverse(delta: float, direction: Direction) -> bool:
    if direction is Direction.HIGH:
        return delta > 0
    if direction is Direction.LOW:
        return delta < 0
    return delta != 0


def _trend(readings: Sequence[Reading], baseline: Baseline | None, ind: Indicator) -> str:
    """Least-squares slope over the last TREND_WINDOW readings -> rising/falling/stable."""
    recent = readings[-TREND_WINDOW:]
    if len(recent) < 3:
        return "insufficient_data"
    xs = [r.day for r in recent]
    ys = [r.value for r in recent]
    x_mean, y_mean = statistics.fmean(xs), statistics.fmean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return "stable"
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    total_change = slope * (xs[-1] - xs[0])
    if abs(total_change) < ind.min_meaningful_change:
        return "stable"
    return "rising" if slope > 0 else "falling"


def _check_limits(value: float, ind: Indicator) -> tuple[Level, str | None]:
    lim = ind.limits
    if lim.critical_high is not None and value >= lim.critical_high:
        return Level.CRITICAL, f"{_fmt(value, ind)} is at or above the critical limit of {_fmt(lim.critical_high, ind)}."
    if lim.critical_low is not None and value <= lim.critical_low:
        return Level.CRITICAL, f"{_fmt(value, ind)} is at or below the critical limit of {_fmt(lim.critical_low, ind)}."
    if lim.warning_high is not None and value >= lim.warning_high:
        return Level.WARNING, f"{_fmt(value, ind)} is at or above the warning limit of {_fmt(lim.warning_high, ind)}."
    if lim.warning_low is not None and value <= lim.warning_low:
        return Level.WARNING, f"{_fmt(value, ind)} is at or below the warning limit of {_fmt(lim.warning_low, ind)}."
    return Level.NORMAL, None


def assess(
    ind: Indicator,
    readings: Sequence[Reading],
    baseline: Baseline | None,
) -> Assessment:
    """Assess the latest reading of one indicator. ``readings`` must be in time order and
    should contain only in-flight readings (the baseline is passed separately)."""
    if not readings:
        return Assessment(
            indicator=ind, level=Level.NORMAL, value=None, day=None, source=None,
            baseline=baseline, z_score=None, deviation=None, trend="insufficient_data",
            reasons=["No readings yet. Take a measurement to start tracking."],
        )

    if not ind.use_baseline:
        baseline = None

    latest = readings[-1]
    level, limit_reason = _check_limits(latest.value, ind)
    reasons: list[str] = [limit_reason] if limit_reason else []

    z = deviation = None
    if baseline is not None:
        deviation = latest.value - baseline.mean
        z = deviation / baseline.sd

        window = readings[-SUSTAINED_WINDOW:]
        if level < Level.WARNING and len(window) == SUSTAINED_WINDOW:
            deltas = [r.value - baseline.mean for r in window]
            each_ok = all(
                _is_adverse(d, ind.adverse_direction) and abs(d) / baseline.sd >= SUSTAINED_Z_EACH
                for d in deltas
            )
            same_side = all(d > 0 for d in deltas) or all(d < 0 for d in deltas)
            mean_delta = statistics.fmean(deltas)
            if (
                each_ok
                and same_side
                and abs(mean_delta) / baseline.sd >= SUSTAINED_Z_MEAN
                and abs(mean_delta) >= ind.min_meaningful_change
            ):
                level = Level.WARNING
                direction = "above" if mean_delta > 0 else "below"
                reasons.append(
                    f"The last {SUSTAINED_WINDOW} readings are consistently {direction} your "
                    f"personal baseline of {_fmt(baseline.mean, ind)} (on average "
                    f"{_fmt(abs(mean_delta), ind)} {direction}). This is still a warning even "
                    "if it is within Earth-normal ranges."
                )

        if (
            level < Level.WARNING
            and _is_adverse(deviation, ind.adverse_direction)
            and abs(z) >= SPIKE_Z
            and abs(deviation) >= 2 * ind.min_meaningful_change
        ):
            level = Level.WARNING
            reasons.append(
                f"This reading is unusually far from your baseline of "
                f"{_fmt(baseline.mean, ind)}. Re-measure to confirm it."
            )

    if level is Level.NORMAL:
        reasons.append(
            "No significant deviation from your personal baseline."
            if baseline is not None
            else "Within the prototype safe range."
        )

    return Assessment(
        indicator=ind,
        level=level,
        value=latest.value,
        day=latest.day,
        source=latest.source,
        baseline=baseline,
        z_score=z,
        deviation=deviation,
        trend=_trend(readings, baseline, ind),
        reasons=reasons,
        actions=list(ind.actions.get(level.label, [])),
        escalate=level is Level.CRITICAL,
    )


def overall_level(assessments: Iterable[Assessment]) -> Level:
    return max((a.level for a in assessments), default=Level.NORMAL)


def body_system_rollup(assessments: Iterable[Assessment]) -> dict[str, dict]:
    """Worst level per body region, for the clickable body figure."""
    rollup: dict[str, dict] = {
        s.value: {"level": Level.NORMAL.label, "indicators": []} for s in BodySystem
    }
    for a in assessments:
        entry = rollup[a.indicator.body_system.value]
        entry["indicators"].append(a.indicator.key)
        if a.level > Level[entry["level"].upper()]:
            entry["level"] = a.level.label
    return rollup
