"""Crew wellbeing: behavioural health for the whole team, not just one person.

Isolation and confinement are one of NASA's five hazards, and they affect the crew as a group:
one person's poor sleep or low mood changes the whole team's day. This view combines what
AURA already has (mood, sleep, exercise and behavioural symptoms) into a simple wellbeing score
for each person and the crew, with trends and team-level suggestions.

Score (0-100, prototype composite, not a psychological assessment), over the last 7 days:
  100 - 10 x (mood SD below baseline) - 8 x (sleep SD below baseline)
      - 5 x (days with trouble sleeping, low mood or unusual tiredness logged)
      - 10 x (share of days under the exercise target)
  (each part capped: mood 30, sleep 25, symptoms 20, exercise 10)
  >= 75 thriving, 55-74 watch, < 55 needs support.
"""

from __future__ import annotations

import numpy as np

from .gamification import EXERCISE_TARGET

WINDOW = 7
TREND_DAYS = 30
BEHAVIOURAL = {"insomnia", "low_mood", "fatigue"}


def _below_sd(store, cid: str, key: str, day: int) -> float:
    """How many baseline SDs the last-7-day mean sits below the baseline (0 if above)."""
    base = store.baseline(cid, key, day)
    rs = [r.value for r in store.readings(cid, key, day) if r.day > day - WINDOW]
    if base is None or not rs or base.sd <= 0:
        return 0.0
    return max(0.0, (base.mean - float(np.mean(rs))) / base.sd)


def member(store, cid: str, day: int) -> dict:
    m = store.crew[cid]
    mood_sd = _below_sd(store, cid, "mood", day)
    sleep_sd = _below_sd(store, cid, "sleep_hours", day)
    sym_days = {e["day"] for e in store.symptoms[cid] if day - WINDOW < e["day"] <= day
                and any(x["key"] in BEHAVIOURAL for x in e["symptoms"])}
    ex = [r.value for r in store.readings(cid, "exercise_minutes", day) if r.day > day - WINDOW]
    ex_short = sum(v < EXERCISE_TARGET for v in ex) / len(ex) if ex else 0.0
    parts = {"mood": min(30, 10 * mood_sd), "sleep": min(25, 8 * sleep_sd),
             "symptoms": min(20, 5 * len(sym_days)), "exercise": 10 * ex_short}
    score = round(max(0.0, min(100.0, 100 - sum(parts.values()))))
    band = "thriving" if score >= 75 else "watch" if score >= 55 else "support"
    drivers = []
    if parts["mood"] >= 5:
        drivers.append(f"mood {mood_sd:.1f} SD below baseline")
    if parts["sleep"] >= 4:
        drivers.append(f"sleep {sleep_sd:.1f} SD below baseline")
    if sym_days:
        drivers.append(f"behavioural symptoms on {len(sym_days)} day(s)")
    if ex_short >= 0.5:
        drivers.append(f"exercise under {EXERCISE_TARGET} min on {round(ex_short * len(ex))} of {len(ex)} days")
    return {"crew_id": cid, "name": m.name, "role": m.role, "score": score, "band": band,
            "drivers": drivers, "penalties": {k: round(v, 1) for k, v in parts.items()}}


def overview(store, day: int | None = None) -> dict:
    day = store.current_day if day is None else day
    rows = sorted((member(store, cid, day) for cid in store.crew), key=lambda r: r["score"])
    crew_score = round(float(np.mean([r["score"] for r in rows]))) if rows else None
    first = max(1, day - TREND_DAYS + 1)
    days = list(range(first, day + 1))

    def series(key):
        out = []
        for d in days:
            row = {"day": d}
            vals = []
            for cid in store.crew:
                v = next((r.value for r in store.readings(cid, key, d) if r.day == d), None)
                row[cid] = v
                if v is not None:
                    vals.append(v)
            row["crew"] = round(float(np.mean(vals)), 2) if vals else None
            out.append(row)
        return out

    mood = series("mood")
    sleep = series("sleep_hours")
    crew_mood = [r["crew"] for r in mood[-14:] if r["crew"] is not None]
    slope = float(np.polyfit(range(len(crew_mood)), crew_mood, 1)[0]) if len(crew_mood) >= 5 else 0.0

    tips = []
    support = [r for r in rows if r["band"] == "support"]
    low_sleep = [r for r in rows if r["penalties"]["sleep"] >= 8]  # 1 SD or more below
    if support:
        names = [r["name"] for r in support]
        who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        tips.append(f"Check in privately with {who}, and offer a call with the behavioural health team.")
    if len(low_sleep) >= 2:
        tips.append("More than one person is sleeping less than usual: review the crew schedule and protect sleep time.")
    if slope <= -0.05:
        tips.append("Crew mood is trending down: plan a shared meal or film night with no work talk.")
    if not tips:
        tips.append("The crew is doing well. Keep the shared meals and days off in the schedule.")

    return {
        "day": day,
        "crew_score": crew_score,
        "crew_band": None if crew_score is None else
        ("thriving" if crew_score >= 75 else "watch" if crew_score >= 55 else "support"),
        "mood_trend_per_day": round(slope, 3),
        "members": rows,
        "series": {"mood": mood, "sleep_hours": sleep},
        "names": {cid: store.crew[cid].name for cid in store.crew},
        "suggestions": tips,
        "method": __doc__.split("Score")[1].strip().split("\n\n")[0] if __doc__ else "",
        "note": "Prototype composite from mood, sleep, exercise and symptoms; not a psychological assessment.",
    }
