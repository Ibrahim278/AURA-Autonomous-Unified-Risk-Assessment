"""Check-in plausibility checks: catch typos and unit mix-ups before they become alerts.

A mistyped reading (98.6 for temperature, 5.4 for glucose, 7 instead of 70) would trigger a
false critical alert or hide a real one. Before saving, AURA checks each value:

* errors (not saved): outside the plausible range. When the number fits a common unit mix-up,
  AURA says so and suggests the converted value (°F -> °C, mmol/L -> mg/dL, minutes -> hours).
* warnings (saved only if the astronaut confirms):
  - very far from the personal baseline (|z| >= 4),
  - a jump from the last reading much bigger than normal day-to-day change,
  - systolic blood pressure not above diastolic.
"""

from __future__ import annotations

from .indicators import INDICATORS
from .simulator import DEFAULTS

Z_LIMIT = 4.0
JUMP_SD = 5.0  # a change bigger than 5 day-to-day SDs is unusual


def _unit_hint(key: str, v: float) -> tuple[str, float | None] | None:
    """(explanation, suggested corrected value) for a common unit mix-up."""
    if key == "body_temp" and 90 <= v <= 110:
        c = round((v - 32) * 5 / 9, 1)
        return f"It looks like °F. {v} °F is {c} °C.", c
    if key == "glucose" and 2 <= v <= 30:
        mg = round(v * 18)
        return f"It looks like mmol/L. {v} mmol/L is {mg} mg/dL.", mg
    if key == "sleep_hours" and 60 <= v <= 900:
        h = round(v / 60, 1)
        return f"It looks like minutes. {v:.0f} min is {h} h.", h
    if key == "spo2" and 0.7 <= v <= 1:
        return f"It looks like a fraction. {v} is {v * 100:.0f}%.", round(v * 100)
    if key == "heart_rate" and 3 <= v < 30:
        return "Did you miss a digit? Resting heart rate is usually 40 to 100 bpm.", None
    return None


def check(store, crew_id: str, values: dict[str, float], day: int | None = None) -> dict:
    """Return {"ok", "errors", "warnings"} without saving anything."""
    day = store.current_day if day is None else day
    errors, warnings = [], []
    for key, v in values.items():
        ind = INDICATORS.get(key)
        if ind is None:
            errors.append({"indicator": key, "message": f"Unknown indicator '{key}'."})
            continue
        _, sd, lo, hi = DEFAULTS[key]
        name = ind.name
        vs = f"{v:.{ind.decimals}f}"
        if not lo <= v <= hi:
            hint, suggested = _unit_hint(key, v) or (None, None)
            errors.append({"indicator": key, "message": f"{name} {v:g} {ind.unit} is outside the plausible range "
                                                        f"{lo} to {hi}." + (f" {hint}" if hint else ""),
                           "hint": hint, "suggested": suggested})
            continue
        base = store.baseline(crew_id, key)
        if base is not None and base.sd > 0:
            z = (v - base.mean) / base.sd
            if abs(z) >= Z_LIMIT:
                warnings.append({"indicator": key, "message": (
                    f"{name} {vs} {ind.unit} is {abs(z):.1f} SD {'above' if z > 0 else 'below'} your baseline "
                    f"({base.mean:.{ind.decimals}f} {ind.unit}). Please re-measure to confirm.")})
                continue
        prev = [r for r in store.readings(crew_id, key, day) if r.day < day]
        if prev and sd > 0 and abs(v - prev[-1].value) >= JUMP_SD * sd:
            warnings.append({"indicator": key, "message": (
                f"{name} changed from {prev[-1].value} to {vs} {ind.unit} since day {prev[-1].day}, much more "
                "than usual from one day to the next. Is it typed correctly?")})
    sys_, dia = values.get("systolic_bp"), values.get("diastolic_bp")
    if sys_ is not None and dia is not None and sys_ <= dia:
        warnings.append({"indicator": "systolic_bp",
                         "message": f"Systolic ({sys_:g}) should be higher than diastolic ({dia:g}). Are they swapped?"})
    return {"ok": not errors and not warnings, "errors": errors, "warnings": warnings}
