"""Import a person's own health data from CSV as a new crew member.

Two layouts are accepted (header names are case-insensitive):

Wide, one row per day (or per reading):
    day,heart_rate,systolic_bp,diastolic_bp,sleep_hours,mood
    -7,61,118,76,7.1,8
    1,64,121,78,6.4,7

Long, one row per reading (an optional ``unit`` column is used for conversions):
    day,indicator,value
    -7,heart_rate,61

``day`` <= -1 is preflight (it builds the personal baseline; aim for 3 to 7 days) and
``day`` >= 1 is a mission day. There is no day 0. Instead of ``day`` the file may have a ``date``
column (2026-11-14, 2026-11-14T07:00:00Z, 14/11/2026, 14.11.2026...): the launch date is day 1
and the day before it is day -1. Dates outside the mission window are skipped with a warning.

Real exports are messy, so the parser also copes with:
- ``;`` or tab separators (Excel in many locales) and decimal commas (``36,6``) in those files;
- units in headers (``Heart rate (bpm)``, ``Sleep [min]``, ``temp_f``) and in cells (``98%``, ``7h``);
- other units, converted with a warning: °F, glucose in mmol/L, sleep in minutes, SpO2 as a
  fraction, exercise in hours, radiation in µSv (detected from the unit, or from the values when
  no unit is given);
- blood pressure in one column (``120/80``);
- several readings on one day: averaged (summed for sleep, exercise and radiation dose);
- extra columns AURA doesn't track, which are listed in a warning.

Every value must be within AURA's plausible range for that indicator after conversion.
Imported readings are labelled ``imported``.
"""

from __future__ import annotations

import csv
import io
import random
import re
import statistics
from collections import defaultdict
from datetime import date, timedelta

from .alerts import MIN_BASELINE_READINGS
from .indicators import INDICATORS
from .simulator import DEFAULTS, PREFLIGHT_DAYS

MAX_ROWS = 50_000  # hourly wearable exports are long; the API caps the upload at 2 MB anyway
MAX_PREFLIGHT = 60
ALIASES = {
    "hr": "heart_rate", "resting_hr": "heart_rate", "resting_heart_rate": "heart_rate", "pulse": "heart_rate",
    "rhr": "heart_rate", "heart_rate_resting": "heart_rate", "heartrate": "heart_rate",
    "sbp": "systolic_bp", "systolic": "systolic_bp", "dbp": "diastolic_bp", "diastolic": "diastolic_bp",
    "systolic_blood_pressure": "systolic_bp", "diastolic_blood_pressure": "diastolic_bp",
    "oxygen": "spo2", "o2": "spo2", "blood_oxygen": "spo2", "sp02": "spo2", "spo_2": "spo2",
    "oxygen_saturation": "spo2", "blood_oxygen_saturation": "spo2", "o2_saturation": "spo2",
    "temp": "body_temp", "temperature": "body_temp", "body_temperature": "body_temp", "core_temp": "body_temp",
    "sleep": "sleep_hours", "sleep_duration": "sleep_hours", "total_sleep": "sleep_hours",
    "time_asleep": "sleep_hours", "asleep": "sleep_hours", "sleep_time": "sleep_hours",
    "exercise": "exercise_minutes", "exercise_time": "exercise_minutes", "workout": "exercise_minutes",
    "workout_minutes": "exercise_minutes", "active_minutes": "exercise_minutes", "training": "exercise_minutes",
    "radiation": "radiation_dose", "dose": "radiation_dose", "daily_dose": "radiation_dose",
    "blood_glucose": "glucose", "fasting_glucose": "glucose", "blood_sugar": "glucose",
    "mood_score": "mood", "mood_rating": "mood",
}
BP_COLUMNS = {"blood_pressure", "bp", "bloodpressure"}
DAY_COLUMNS = {"day", "mission_day", "day_number", "flight_day"}
# In order of preference: a file with both 'date' and 'time' columns uses 'date'.
DATE_COLUMNS = ("date", "calendar_date", "datetime", "date_time", "timestamp", "start_date", "start", "start_time",
                "recorded", "recorded_at", "measured_at", "time")
LONG_NAME_COLUMNS = {"indicator", "measure", "measurement", "metric", "test", "type", "parameter", "variable"}
IGNORED_COLUMNS = {"notes", "note", "comment", "comments", "source", "device", "timezone", "tz", "id", "name",
                   "person", "subject", "participant", "unit", "units", "time", "end", "end_date", "end_time"}
# Several readings in one day are averaged, except these, which add up over the day.
SUMMED = {"sleep_hours", "exercise_minutes", "radiation_dose"}

# Unit spellings -> canonical token.
UNIT_TOKENS = {
    "bpm": "bpm", "beats_min": "bpm", "beats_per_minute": "bpm", "/min": "bpm",
    "mmhg": "mmhg", "mm_hg": "mmhg",
    "%": "pct", "pct": "pct", "percent": "pct",
    "c": "c", "°c": "c", "degc": "c", "deg_c": "c", "celsius": "c", "ºc": "c",
    "f": "f", "°f": "f", "degf": "f", "deg_f": "f", "fahrenheit": "f", "ºf": "f",
    "mg/dl": "mgdl", "mgdl": "mgdl", "mg_dl": "mgdl",
    "mmol/l": "mmol", "mmol": "mmol", "mmol_l": "mmol", "mmoll": "mmol",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    "msv": "msv", "usv": "usv", "µsv": "usv", "μsv": "usv", "microsievert": "usv",
}
# Header suffixes that name a unit, e.g. sleep_minutes, temp_f, glucose_mmol.
SUFFIX_UNITS = ("bpm", "mmhg", "pct", "percent", "celsius", "fahrenheit", "degc", "degf", "c", "f", "mgdl",
                "mg_dl", "mmol_l", "mmol", "hours", "hrs", "hr", "h", "minutes", "mins", "min", "msv", "usv")
# Per indicator: the unit AURA stores, and conversions from other units.
CANONICAL = {"heart_rate": "bpm", "systolic_bp": "mmhg", "diastolic_bp": "mmhg", "spo2": "pct", "glucose": "mgdl",
             "body_temp": "c", "sleep_hours": "h", "exercise_minutes": "min", "radiation_dose": "msv"}
CONVERSIONS = {
    ("body_temp", "f"): ("°F", "°C", lambda v: (v - 32) * 5 / 9),
    ("glucose", "mmol"): ("mmol/L", "mg/dL", lambda v: v * 18.016),
    ("sleep_hours", "min"): ("minutes", "hours", lambda v: v / 60),
    ("exercise_minutes", "h"): ("hours", "minutes", lambda v: v * 60),
    ("radiation_dose", "usv"): ("µSv", "mSv", lambda v: v / 1000),
    ("spo2", "fraction"): ("a fraction", "%", lambda v: v * 100),
}
# No unit given: guess from the column's median value (only when it is impossible in AURA's unit).
GUESSES = {
    "body_temp": lambda m: "f" if m > 50 else None,
    "glucose": lambda m: "mmol" if m < 30 else None,
    "sleep_hours": lambda m: "min" if m > 24 else None,
    "spo2": lambda m: "fraction" if m <= 1 else None,
}
NUMBER_RE = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+))\s*([^\d\s].*)?$")


class ImportError_(ValueError):
    """A problem with the uploaded file, worded for the user."""


def _norm(name: str) -> tuple[str, str | None]:
    """'Heart Rate (bpm)' -> ('heart_rate', 'bpm'); 'Temp [°F]' -> ('temp', 'f')."""
    raw = name.strip().lower()
    unit = None
    m = re.search(r"[(\[]([^)\]]*)[)\]]\s*$", raw)
    if m:
        unit = UNIT_TOKENS.get(m[1].strip().replace(" ", ""), None) if m[1].strip() else None
        raw = raw[:m.start()]
    raw = raw.strip()
    if raw.endswith("%"):  # 'SpO2 %'
        raw, unit = raw[:-1], unit or "pct"
    key = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return key, unit


def _key(name: str) -> tuple[str | None, str | None]:
    """Header or indicator name -> (indicator key or None, unit hint or None)."""
    k, unit = _norm(name)
    if k in BP_COLUMNS:
        return "blood_pressure", unit
    for cand in (k, ALIASES.get(k)):
        if cand in INDICATORS:
            return cand, unit
    for suf in SUFFIX_UNITS:  # sleep_minutes, temp_f, glucose_mmol_l, heart_rate_bpm
        if k.endswith("_" + suf):
            base = k[: -len(suf) - 1]
            base = ALIASES.get(base, base)
            if base in INDICATORS:
                return base, unit or UNIT_TOKENS.get(suf.replace("_", "/") if suf in ("mg_dl", "mmol_l") else suf)
    return None, unit


def _sniff(text: str) -> str:
    first = next((line for line in text.splitlines() if line.strip()), "")
    counts = {d: first.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def _number(raw: str, decimal_comma: bool) -> tuple[float, str | None] | None:
    """'36,6' -> (36.6, None); '98%' -> (98.0, 'pct'); '7 h' -> (7.0, 'h'); 'abc' -> None."""
    s = raw.strip().replace("−", "-")
    if decimal_comma and re.fullmatch(r"[-+]?\d+,\d+.*", s):
        s = s.replace(",", ".", 1)
    m = NUMBER_RE.match(s)
    if not m:
        return None
    unit = None
    if m[2]:
        unit = UNIT_TOKENS.get(m[2].strip().lower().replace(" ", ""))
        if unit is None:
            return None  # '7h30', '12 apples'
    return float(m[1]), unit


def _parse_dates(values: list[str]) -> list[date | None]:
    """Parse a date column. Slash dates are read day-first or month-first, whichever the file
    proves (a part > 12); if it never does, they are ambiguous and the user is asked for ISO."""
    out: list[date | None] = []
    slash = []
    for v in values:
        v = v.strip()
        m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", v)
        if m:
            try:
                out.append(date(int(m[1]), int(m[2]), int(m[3])))
            except ValueError:  # 2026-13-45
                out.append(None)
            continue
        m = re.match(r"^(\d{1,2})([/.-])(\d{1,2})\2(\d{4})", v)
        if m:
            slash.append((len(out), int(m[1]), int(m[3]), int(m[4]), m[2]))
            out.append(None)
            continue
        out.append(None)
    if slash:
        day_first = any(sep == "." for *_, sep in slash) or any(a > 12 for _, a, _, _, _ in slash)
        month_first = any(b > 12 for _, _, b, _, _ in slash)
        if day_first and month_first:
            raise ImportError_("The date column mixes day-first and month-first dates. Use YYYY-MM-DD.")
        if not day_first and not month_first:
            raise ImportError_(f"Dates like {values[slash[0][0]].strip()} could be day/month or month/day. "
                               "Use YYYY-MM-DD (for example 2026-11-14).")
        for i, a, b, y, _ in slash:
            d, mth = (a, b) if day_first else (b, a)
            try:
                out[i] = date(y, mth, d)
            except ValueError:
                out[i] = None
    return out


def _to_day(d: date, launch: date) -> int:
    """Launch date is day 1; the day before launch is day -1 (there is no day 0)."""
    delta = (d - launch).days
    return delta + 1 if delta >= 0 else delta


def parse_csv(text: str, mission_days: int, launch: date | None = None
              ) -> tuple[list[tuple[str, int, float]], list[str]]:
    """Return ``[(indicator, day, value)]`` and a list of warnings, or raise ImportError_.

    ``launch`` is the date of mission day 1, used only when the file has dates instead of days.
    """
    text = text.lstrip("﻿")
    delim = _sniff(text)
    decimal_comma = delim != ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ImportError_("The file needs a header row and at least one data row.")
    if len(rows) > MAX_ROWS:
        raise ImportError_(f"The file has more than {MAX_ROWS:,} rows.")
    header = [_norm(h)[0] for h in rows[0]]
    warnings: list[str] = []

    # ---- which column says when?
    di = next((i for i, h in enumerate(header) if h in DAY_COLUMNS), None)
    ti = next((header.index(c) for c in DATE_COLUMNS if c in header), None) if di is None else None
    if di is None and ti is None:
        raise ImportError_("Add a 'day' column (-7 to -1 for preflight days, 1, 2, 3... for mission days) "
                           "or a 'date' column (YYYY-MM-DD; the launch date is day 1).")
    days_of_row: list[int | None]
    skipped_dates = 0
    if di is not None:
        days_of_row = []
        for n, r in enumerate(rows[1:], start=2):
            raw = r[di].strip() if di < len(r) else ""
            try:
                days_of_row.append(int(float(raw.replace(",", "."))))
            except ValueError:
                raise ImportError_(f"Line {n}: day '{raw}' is not a whole number.") from None
    else:
        launch = launch or date.today()
        dates = _parse_dates([r[ti] if ti < len(r) else "" for r in rows[1:]])
        for n, (d, r) in enumerate(zip(dates, rows[1:]), start=2):
            if d is None:
                raise ImportError_(f"Line {n}: '{r[ti] if ti < len(r) else ''}' is not a date. Use YYYY-MM-DD.")
        days_of_row = [_to_day(d, launch) for d in dates]  # type: ignore[arg-type]
        lo_d, hi_d = min(dates), max(dates)  # type: ignore[type-var]
        keep = [-MAX_PREFLIGHT <= d <= mission_days for d in days_of_row]
        skipped_dates = keep.count(False)
        if not any(d >= 1 for d, k in zip(days_of_row, keep) if k):
            end = launch + timedelta(days=mission_days - 1)
            raise ImportError_(
                f"Your dates run from {lo_d} to {hi_d}, but the mission runs from {launch} (day 1) to {end}, so "
                "none of them is a mission day. Set the launch date to the first day of your own mission "
                "period, and AURA will count your earlier dates as preflight.")
        days_of_row = [d if k else None for d, k in zip(days_of_row, keep)]
        kept = sorted({d for d in days_of_row if d is not None})
        n_pre, n_in = sum(d < 0 for d in kept), sum(d >= 1 for d in kept)
        warnings.append(f"Dates mapped with {launch} as mission day 1: {n_pre} preflight day(s) and {n_in} "
                        "mission day(s). If that's not right, set the launch date and import again.")
        if skipped_dates:
            warnings.append(f"Skipped {skipped_dates} row(s) dated more than {MAX_PREFLIGHT} days before launch "
                            f"({launch}) or after mission day {mission_days}.")

    # ---- which columns hold values? (wide) or which column names them? (long)
    when_col = di if di is not None else ti
    name_i = next((i for i, h in enumerate(header) if h in LONG_NAME_COLUMNS), None)
    value_i = next((i for i, h in enumerate(header) if h in ("value", "reading", "result")), None)
    long = name_i is not None and value_i is not None
    unit_i = next((i for i, h in enumerate(header) if h in ("unit", "units")), None) if long else None

    # (key, raw cell, unit hint from header/unit column, line, day)
    cells: list[tuple[str, str, str | None, int, int]] = []
    if long:
        unknown_names: set[str] = set()
        for n, (r, day) in enumerate(zip(rows[1:], days_of_row), start=2):
            name = r[name_i].strip() if name_i < len(r) else ""
            raw = r[value_i] if value_i < len(r) else ""
            if day is None or not name:
                continue
            key, hint = _key(name)
            if key is None:
                unknown_names.add(name)
                continue
            if unit_i is not None and unit_i < len(r) and r[unit_i].strip():
                hint = UNIT_TOKENS.get(r[unit_i].strip().lower().replace(" ", ""), hint)
            cells.append((key, raw, hint, n, day))
        if unknown_names and not cells:
            raise ImportError_(f"Line 2: unknown indicator '{sorted(unknown_names)[0]}'. "
                               f"Known: {', '.join(INDICATORS)}.")
        if unknown_names:
            warnings.append(f"Skipped readings AURA doesn't track: {', '.join(sorted(unknown_names))}. "
                            "To keep one, add it with + Add indicator, using the same name, and import again.")
    else:
        cols: dict[int, tuple[str, str | None]] = {}
        unknown = []
        for i, h in enumerate(rows[0]):
            if i == when_col:
                continue
            key, hint = _key(h)
            if key is None:
                if _norm(h)[0] not in IGNORED_COLUMNS | DAY_COLUMNS | set(DATE_COLUMNS) and h.strip():
                    unknown.append(h.strip())
                continue
            cols[i] = (key, hint)
        if not cols:
            raise ImportError_("No indicator columns recognised. Use names like heart_rate, systolic_bp, "
                               f"sleep_hours or mood. Known: {', '.join(INDICATORS)}.")
        targets: dict[str, list[str]] = defaultdict(list)
        for i, (key, _) in cols.items():
            for k in (("systolic_bp", "diastolic_bp") if key == "blood_pressure" else (key,)):
                targets[k].append(rows[0][i].strip())
        clash = {k: v for k, v in targets.items() if len(v) > 1}
        if clash:
            k, v = next(iter(clash.items()))
            raise ImportError_(f"Columns {', '.join(repr(x) for x in v)} all hold {INDICATORS[k].name}. Keep one.")
        if unknown:
            warnings.append(f"Ignored unrecognised column(s): {', '.join(unknown)}. To keep one, add it with "
                            "+ Add indicator, using the column name as its name, and import again.")
        for n, (r, day) in enumerate(zip(rows[1:], days_of_row), start=2):
            if day is None:
                continue
            for i, (key, hint) in cols.items():
                cells.append((key, r[i] if i < len(r) else "", hint, n, day))

    # ---- cells -> numbers (split blood pressure, strip units in cells)
    parsed: list[tuple[str, int, float, str | None, int]] = []  # key, day, value, unit, line
    for key, raw, hint, line, day in cells:
        raw = raw.strip()
        if not raw or raw.upper() in {"NA", "N/A", "NAN", "-", "--"}:
            continue
        if day == 0:
            raise ImportError_(f"Line {line}: there is no day 0. Use -1 for the last preflight day and 1 for launch day.")
        if day > mission_days:
            raise ImportError_(f"Line {line}: day {day} is after the end of the {mission_days}-day mission.")
        if day < -MAX_PREFLIGHT:
            raise ImportError_(f"Line {line}: preflight days go back at most {MAX_PREFLIGHT} days.")
        if key == "blood_pressure":
            m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*(mmhg)?\s*", raw, re.I)
            if not m:
                raise ImportError_(f"Line {line}: blood pressure '{raw}' should look like 120/80.")
            parsed.append(("systolic_bp", day, float(m[1].replace(",", ".")), hint, line))
            parsed.append(("diastolic_bp", day, float(m[2].replace(",", ".")), hint, line))
            continue
        num = _number(raw, decimal_comma)
        if num is None:
            raise ImportError_(f"Line {line}: {key} value '{raw}' is not a number.")
        value, cell_unit = num
        parsed.append((key, day, value, cell_unit or hint, line))

    # ---- unit conversion (explicit unit first, else a guess from impossible values)
    converted: dict[tuple[str, str], int] = defaultdict(int)
    by_key: dict[str, list[float]] = defaultdict(list)
    for key, _, value, unit, _ in parsed:
        if unit is None:
            by_key[key].append(value)
    guessed = {k: GUESSES[k](statistics.median(v)) for k, v in by_key.items() if k in GUESSES and v}
    final: list[tuple[str, int, float, int]] = []
    for key, day, value, unit, line in parsed:
        if key in CANONICAL:
            unit = unit if unit is not None else guessed.get(key)
            if unit == "pct" and key == "spo2" and value <= 1:
                unit = "fraction"
            if unit is not None and unit != CANONICAL[key]:
                conv = CONVERSIONS.get((key, unit))
                if conv is None:
                    raise ImportError_(f"Line {line}: {key} is in an unexpected unit ({unit}). "
                                       f"AURA uses {INDICATORS[key].unit}.")
                value = conv[2](value)
                converted[(key, unit)] += 1
        final.append((key, day, value, line))
    for (key, unit), n in sorted(converted.items()):
        src, dst, _ = CONVERSIONS[(key, unit)]
        warnings.append(f"{INDICATORS[key].name}: converted {n} value(s) from {src} to {dst}.")

    # ---- plausibility, then one value per indicator per day
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    first_line: dict[tuple[str, int], int] = {}
    for key, day, value, line in final:
        _, _, lo, hi = DEFAULTS[key]
        if not lo <= value <= hi:
            raise ImportError_(f"Line {line}: {key}={value:g} is outside the plausible range {lo:g} to {hi:g}.")
        grouped[(key, day)].append(value)
        first_line.setdefault((key, day), line)
    out: dict[tuple[str, int], float] = {}
    multi: dict[str, int] = defaultdict(int)
    for (key, day), vals in grouped.items():
        if len(vals) > 1:
            multi[key] += 1
        v = sum(vals) if key in SUMMED else sum(vals) / len(vals)
        _, _, lo, hi = DEFAULTS[key]
        if not lo <= v <= hi:
            raise ImportError_(f"Day {day}: the {key} readings add up to {v:g}, outside the plausible range "
                               f"{lo:g} to {hi:g} (line {first_line[(key, day)]}). Is a day listed twice?")
        out[(key, day)] = round(v, INDICATORS[key].decimals)
    for key, n in sorted(multi.items()):
        how = "the daily total" if key in SUMMED else "the daily average"
        warnings.append(f"{INDICATORS[key].name}: {n} day(s) had several readings, so AURA used {how}.")

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
