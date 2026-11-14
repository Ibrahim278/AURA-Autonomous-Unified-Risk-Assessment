"""Early-warning forecast: where is each indicator heading?

For every indicator, fit a straight line to the last ``FIT_WINDOW`` in-flight readings and
project it forward. If the trend is adverse, clear (R² >= ``MIN_R2``) and meaningful, report
when it would cross the next line: the edge of the personal baseline band (mean ± 2 SD), the
warning limit or the critical limit, if that happens within ``HORIZON`` days.

This is a simple, transparent extrapolation, not a clinical prediction. It never changes an
alert level; it only says "if nothing changes, this is where the trend goes".
"""

from __future__ import annotations

import numpy as np

from .alerts import SUSTAINED_Z_MEAN, Level, _is_adverse
from .indicators import INDICATORS, Direction
from .store import MissionStore

FIT_WINDOW = 10
MIN_POINTS = 5
MIN_R2 = 0.3
HORIZON = 14  # days ahead we report crossings for
PROJECT_DAYS = 7  # days of projection returned for charts


def _thresholds(key: str, store: MissionStore, crew_id: str, side: str) -> list[tuple[float, str, str]]:
    """(value, level, label) lines on one side, nearest-first order not guaranteed."""
    ind = INDICATORS[key]
    lim = ind.limits
    out = []
    base = store.baseline(crew_id, key) if ind.use_baseline else None
    if side == "high":
        if base:
            out.append((base.mean + SUSTAINED_Z_MEAN * base.sd, Level.WARNING.label, "edge of your baseline"))
        if lim.warning_high is not None:
            out.append((lim.warning_high, Level.WARNING.label, "warning limit"))
        if lim.critical_high is not None:
            out.append((lim.critical_high, Level.CRITICAL.label, "critical limit"))
    else:
        if base:
            out.append((base.mean - SUSTAINED_Z_MEAN * base.sd, Level.WARNING.label, "edge of your baseline"))
        if lim.warning_low is not None:
            out.append((lim.warning_low, Level.WARNING.label, "warning limit"))
        if lim.critical_low is not None:
            out.append((lim.critical_low, Level.CRITICAL.label, "critical limit"))
    return out


def indicator_forecast(store: MissionStore, crew_id: str, key: str, day: int) -> dict | None:
    ind = INDICATORS[key]
    rs = store.readings(crew_id, key, day)[-FIT_WINDOW:]
    if len(rs) < MIN_POINTS or rs[-1].day < day - 3:  # need recent data
        return None
    x = np.array([r.day for r in rs], dtype=float)
    y = np.array([r.value for r in rs], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(((y - fitted) ** 2).sum()) / ss_tot if ss_tot > 0 else 0.0
    now = slope * day + intercept
    projection = [{"day": day + k, "value": round(float(slope * (day + k) + intercept), ind.decimals + 1)}
                  for k in range(PROJECT_DAYS + 1)]
    result = {"indicator": key, "name": ind.name, "unit": ind.unit, "slope_per_day": round(float(slope), 3),
              "r2": round(r2, 2), "current_trend_value": round(float(now), ind.decimals + 1),
              "projected_7d": projection[-1]["value"], "projection": projection, "crossing": None,
              "direction": "rising" if slope > 0 else "falling"}

    meaningful = abs(slope) * 7 >= ind.min_meaningful_change * 0.5
    if not (meaningful and r2 >= MIN_R2 and _is_adverse(slope, ind.adverse_direction)):
        return result
    side = "high" if slope > 0 else "low"
    if ind.adverse_direction is not Direction.BOTH and side != ind.adverse_direction.value:
        return result
    crossings = []
    for value, level, label in _thresholds(key, store, crew_id, side):
        already = now >= value if side == "high" else now <= value
        if already:
            continue
        days = (value - now) / slope
        if 0 < days <= HORIZON:
            crossings.append({"in_days": max(1, round(days)), "threshold": round(value, ind.decimals + 1),
                              "level": level, "label": label})
    if crossings:
        crossings.sort(key=lambda c: (c["in_days"], c["level"] != Level.CRITICAL.label))
        # Report the soonest crossing, plus the critical one if that's also coming.
        result["crossing"] = crossings[0]
        crit = next((c for c in crossings if c["level"] == Level.CRITICAL.label), None)
        result["critical_crossing"] = crit if crit and crit is not crossings[0] else None
    return result


def forecast(store: MissionStore, crew_id: str, day: int | None = None) -> dict:
    day = store.current_day if day is None else day
    status = {a["indicator"]: a for a in store.status(crew_id, day)["indicators"]}
    items = []
    for key in INDICATORS:
        f = indicator_forecast(store, crew_id, key, day)
        if f is None:
            continue
        f["level_now"] = status[key]["level"]
        items.append(f)
    risks = [f for f in items if f["crossing"]]
    risks.sort(key=lambda f: (f["crossing"]["in_days"], f["crossing"]["level"] != Level.CRITICAL.label))
    return {
        "crew_id": crew_id, "day": day, "horizon_days": HORIZON,
        "risks": risks,
        "series": {f["indicator"]: f["projection"] for f in items},
        "method": (f"Straight-line trend of the last {FIT_WINDOW} readings, projected forward. Shown only when the "
                   f"trend is clear (R² ≥ {MIN_R2}), adverse and large enough to matter. Not a clinical prediction."),
    }
