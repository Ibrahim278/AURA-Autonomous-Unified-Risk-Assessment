"""Import a person's own health data from CSV as a new crew member.

Two layouts are accepted (header names are case-insensitive):

Wide, one row per day:
    day,heart_rate,systolic_bp,diastolic_bp,sleep_hours,mood
    -7,61,118,76,7.1,8
    1,64,121,78,6.4,7

Long, one row per reading:
    day,indicator,value
    -7,heart_rate,61

``day`` <= -1 is preflight (it builds the personal baseline; aim for 3 to 7 days) and
``day`` >= 1 is a mission day. There is no day 0. Blank cells are skipped. Every value must be
within AURA's plausible range for that indicator. Imported readings are labelled ``imported``.
"""

from __future__ import annotations

import csv
import io
import random

from .alerts import MIN_BASELINE_READINGS
from .indicators import INDICATORS
from .simulator import DEFAULTS, PREFLIGHT_DAYS

MAX_ROWS = 5000
ALIASES = {
    "hr": "heart_rate", "resting_hr": "heart_rate", "resting_heart_rate": "heart_rate", "pulse": "heart_rate",
    "sbp": "systolic_bp", "systolic": "systolic_bp", "dbp": "diastolic_bp", "diastolic": "diastolic_bp",
    "oxygen": "spo2", "o2": "spo2", "blood_oxygen": "spo2",
    "temp": "body_temp", "temperature": "body_temp", "body_temperature": "body_temp",
    "sleep": "sleep_hours", "exercise": "exercise_minutes", "radiation": "radiation_dose",
    "dose": "radiation_dose", "blood_glucose": "glucose",
}


class ImportError_(ValueError):
    """A problem with the uploaded file, worded for the user."""


def _key(name: str) -> str | None:
    k = name.strip().lower().replace(" ", "_").replace("-", "_")
    k = ALIASES.get(k, k)
    return k if k in INDICATORS else None


def parse_csv(text: str, mission_days: int) -> tuple[list[tuple[str, int, float]], list[str]]:
    """Return ``[(indicator, day, value)]`` and a list of warnings, or raise ImportError_."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ImportError_("The file needs a header row and at least one data row.")
    if len(rows) > MAX_ROWS:
        raise ImportError_(f"The file has more than {MAX_ROWS} rows.")
    header = [h.strip().lower() for h in rows[0]]
    if "day" not in header:
        raise ImportError_("Add a 'day' column: -7 to -1 for preflight days, 1, 2, 3... for mission days.")
    di = header.index("day")

    long = {"indicator", "value"} <= set(header)
    if long:
        ii, vi = header.index("indicator"), header.index("value")
        cells = [(r[ii] if ii < len(r) else "", r[vi] if vi < len(r) else "", r, n)
                 for n, r in enumerate(rows[1:], start=2)]
    else:
        cols = {i: _key(h) for i, h in enumerate(header) if i != di}
        unknown = [rows[0][i] for i, k in cols.items() if k is None]
        cols = {i: k for i, k in cols.items() if k}
        if not cols:
            raise ImportError_("No indicator columns recognised. Use names like heart_rate, systolic_bp, "
                               f"sleep_hours or mood. Known: {', '.join(INDICATORS)}.")
        cells = [(cols[i], r[i] if i < len(r) else "", r, n)
                 for n, r in enumerate(rows[1:], start=2) for i in cols]
    warnings = [f"Ignored unrecognised column(s): {', '.join(unknown)}."] if not long and unknown else []

    out: dict[tuple[str, int], float] = {}
    for name, raw, row, line in cells:
        raw = raw.strip()
        if not raw or raw.upper() in {"NA", "N/A", "NAN"}:
            continue
        key = _key(name) if long else name
        if key is None:
            raise ImportError_(f"Line {line}: unknown indicator '{name}'.")
        try:
            day = int(float(row[di]))
        except (ValueError, IndexError):
            raise ImportError_(f"Line {line}: day '{row[di] if di < len(row) else ''}' is not a whole number.") from None
        if day == 0:
            raise ImportError_(f"Line {line}: there is no day 0. Use -1 for the last preflight day and 1 for launch day.")
        if day > mission_days:
            raise ImportError_(f"Line {line}: day {day} is after the end of the {mission_days}-day mission.")
        if day < -60:
            raise ImportError_(f"Line {line}: preflight days go back at most 60 days.")
        try:
            value = float(raw)
        except ValueError:
            raise ImportError_(f"Line {line}: {key} value '{raw}' is not a number.") from None
        _, _, lo, hi = DEFAULTS[key]
        if not lo <= value <= hi:
            raise ImportError_(f"Line {line}: {key}={value:g} is outside the plausible range {lo:g} to {hi:g}.")
        out[(key, day)] = round(value, INDICATORS[key].decimals)

    if not out:
        raise ImportError_("No values found in the file.")
    readings = sorted(((k, d, v) for (k, d), v in out.items()), key=lambda x: (x[0], x[1]))
    if not any(d >= 1 for _, d, _ in readings):
        raise ImportError_("Add at least one mission day (day 1 or later) so there is something to assess.")
    for key in sorted({k for k, _, _ in readings}):
        if not INDICATORS[key].use_baseline:
            continue
        n = sum(1 for k, d, _ in readings if k == key and d < 0)
        if n < MIN_BASELINE_READINGS:
            warnings.append(f"{INDICATORS[key].name}: {n} preflight day(s), so no personal baseline "
                            f"(needs {MIN_BASELINE_READINGS}+). Only fixed limits apply.")
    return readings, warnings


def template() -> str:
    """A small example file in the wide layout."""
    lines = ["day,heart_rate,systolic_bp,diastolic_bp,spo2,glucose,body_temp,sleep_hours,mood,exercise_minutes"]
    rnd = random.Random(7)
    for day in [*range(-PREFLIGHT_DAYS, 0), *range(1, 11)]:
        drift = max(0, day - 5)
        lines.append(",".join(str(x) for x in (
            day, round(61 + rnd.gauss(0, 2) + drift * 1.5), round(117 + rnd.gauss(0, 3)), round(75 + rnd.gauss(0, 2)),
            round(98 + rnd.gauss(0, 0.5)), round(88 + rnd.gauss(0, 4)), round(36.6 + rnd.gauss(0, 0.1), 1),
            round(7.2 - (0.4 if day > 0 else 0) - drift * 0.2 + rnd.gauss(0, 0.2), 1),
            max(1, min(10, round(8 - drift * 0.4 + rnd.gauss(0, 0.5)))), round(120 + rnd.gauss(0, 8)))))
    return "\n".join(lines) + "\n"
