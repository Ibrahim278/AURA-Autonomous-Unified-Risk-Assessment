"""Radiation dose budget: how much of each astronaut's limits the mission has used.

The daily dosimeter card says whether *today* was unusual. This module answers the long-term
question: how much exposure is left?

Limits (NASA-STD-3001 Volume 1, Rev B):
* Career: 600 mSv effective dose, the same for every age and sex.
* Short term, blood-forming organs: 250 mGy-Eq in any 30 days, 500 mGy-Eq in a year.
  AURA compares the dosimeter's mSv with these as an approximation (for the mostly
  low-LET background, 1 mSv is close to 1 mGy-Eq). It is a prototype budget, not dosimetry.

Status levels (prototype rules):
* critical: a limit is reached, or today's reading is a solar particle event (>= 10 mSv)
* warning: 80% of the career limit used, a 30-day window above 80% of its limit, or the
  current rate would pass the career limit before the planned end of the mission
"""

from __future__ import annotations

CAREER_LIMIT = 600.0
LIMIT_30D = 250.0
LIMIT_1Y = 500.0
WARN_FRACTION = 0.8
SPE_DAILY = 10.0  # a day this high means a solar particle event
RATE_WINDOW = 7

REFERENCES = [
    "NASA-STD-3001 Vol. 1 Rev. B (2022): 600 mSv career effective dose limit",
    "NASA-STD-3001 Vol. 1: 30-day (250 mGy-Eq) and 1-year (500 mGy-Eq) blood-forming organ limits",
    "Zeitlin et al., Science 340:1080 (2013): 1.84 mSv/day in deep space",
    "Zhang et al., Science Advances 6 (2020): 1.37 mSv/day on the lunar surface",
]


def _window(readings, day: int, length: int) -> float:
    return sum(r.value for r in readings if day - length < r.day <= day)


def budget(store, crew_id: str, day: int | None = None) -> dict:
    day = store.current_day if day is None else day
    member = store.crew[crew_id]
    rs = store.readings(crew_id, "radiation_dose", day)
    mission = sum(r.value for r in rs)
    prior = member.prior_dose_mSv
    career = prior + mission
    recent = [r.value for r in rs[-RATE_WINDOW:] if r.value < SPE_DAILY]  # background rate, no storms
    rate = sum(recent) / len(recent) if recent else 0.0
    planned_end = max(store.dataset.days, day)
    projected_end = career + rate * (planned_end - day)
    remaining = max(CAREER_LIMIT - career, 0.0)
    days_left = None if rate <= 0 else round(remaining / rate)
    d30 = _window(rs, day, 30)
    d365 = _window(rs, day, 365)
    today = rs[-1].value if rs and rs[-1].day == day else None
    spe_days = [r.day for r in rs if r.value >= SPE_DAILY]

    reasons, level = [], "normal"

    def flag(lvl: str, text: str) -> None:
        nonlocal level
        reasons.append(text)
        if lvl == "critical" or level == "normal":
            level = lvl

    if career >= CAREER_LIMIT:
        flag("critical", f"Career dose {career:.0f} mSv has reached the {CAREER_LIMIT:.0f} mSv limit.")
    elif career >= WARN_FRACTION * CAREER_LIMIT:
        flag("warning", f"{100 * career / CAREER_LIMIT:.0f}% of the career limit is used.")
    elif projected_end >= CAREER_LIMIT:
        flag("warning", f"At {rate:.2f} mSv/day the career limit is reached around day "
                        f"{day + (days_left or 0)}, before the mission ends on day {planned_end}.")
    if d30 >= LIMIT_30D:
        flag("critical", f"{d30:.0f} mSv in the last 30 days reaches the 30-day limit.")
    elif d30 >= WARN_FRACTION * LIMIT_30D:
        flag("warning", f"{d30:.0f} mSv in the last 30 days is over 80% of the 30-day limit.")
    if today is not None and today >= SPE_DAILY:
        flag("critical", f"Today's {today:.1f} mSv looks like a solar particle event.")

    warn_at = WARN_FRACTION * CAREER_LIMIT
    if level == "normal" and career < warn_at <= projected_end and rate > 0:
        reasons.append(f"On this course you pass 80% of the career limit around day "
                       f"{day + round((warn_at - career) / rate)}.")

    actions = {
        "normal": ["Keep wearing your dosimeter and log it each evening."],
        "warning": ["Ask ground to review your remaining EVA and high-dose tasks.",
                    "Spend sleep and rest time in the best-shielded module.",
                    "Watch the space-weather feed so you can shelter early."],
        "critical": ["Go to the storm shelter or most-shielded area if a solar event is under way.",
                     "Message ground: the flight surgeon must review your dose before further EVAs."],
    }[level]

    return {
        "crew_id": crew_id,
        "day": day,
        "level": level,
        "reasons": reasons or ["Dose is well inside every limit."],
        "actions": actions,
        "prior_mSv": round(prior, 1),
        "mission_mSv": round(mission, 1),
        "career_mSv": round(career, 1),
        "career_limit_mSv": CAREER_LIMIT,
        "career_used_pct": round(100 * career / CAREER_LIMIT, 1),
        "remaining_mSv": round(remaining, 1),
        "rate_mSv_day": round(rate, 2),
        "days_to_limit": days_left,
        "planned_end_day": planned_end,
        "projected_end_mSv": round(projected_end, 1),
        "window_30d_mSv": round(d30, 1),
        "limit_30d_mSv": LIMIT_30D,
        "window_1y_mSv": round(d365, 1),
        "limit_1y_mSv": LIMIT_1Y,
        "spe_days": spe_days,
        "cumulative": [{"day": r.day, "mSv": round(prior + sum(x.value for x in rs[: i + 1]), 1)}
                       for i, r in enumerate(rs)],
        "references": REFERENCES,
        "note": "Prototype budget. Dosimeter mSv is compared with the mGy-Eq short-term limits as an approximation.",
    }
