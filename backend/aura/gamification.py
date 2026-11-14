"""Mission routine, streaks, points and badges.

Turns the daily health routine into small tasks the astronaut can tick off. Tasks are completed
by the data itself (a check-in logs the reading), so the game rewards exactly the behaviour that
keeps the monitoring useful: measuring regularly, following up on warnings, and keeping up
exercise countermeasures.

Rules:
* Wearable-synced indicators (heart rate, SpO2, sleep, exercise, dosimeter) count as done when a
  reading exists for the day.
* Manual indicators (blood pressure, temperature, glucose, mood) must be entered by the astronaut
  on the current day. Past mission days count any reading (the history is pre-recorded).
* Follow-up tasks appear for every warning or critical spot measurement (vitals, glucose,
  temperature). They are done when the astronaut re-measures that indicator manually today.
* Wellness tasks are ticked off by hand.
"""

from __future__ import annotations

from dataclasses import dataclass

from .alerts import Level
from .store import MissionStore

AUTO = {"heart_rate", "spo2", "sleep_hours", "exercise_minutes", "radiation_dose"}
EXERCISE_TARGET = 90  # minutes; the in-flight program targets about 2 h a day


@dataclass(frozen=True)
class RoutineTask:
    id: str
    title: str
    description: str
    indicators: tuple[str, ...]
    points: int


ROUTINE: tuple[RoutineTask, ...] = (
    RoutineTask("vitals", "Morning vitals",
                "Seated blood pressure (2 readings) and temperature, before breakfast.",
                ("systolic_bp", "diastolic_bp", "body_temp"), 20),
    RoutineTask("glucose", "Fasting glucose", "Finger-stick glucometer before eating.", ("glucose",), 10),
    RoutineTask("mood", "Mood check-in", "Rate your mood from 1 to 10. It takes 5 seconds.", ("mood",), 10),
    RoutineTask("wearable", "Wearable sync", "Heart rate, SpO2 and sleep sync from your wearable.",
                ("heart_rate", "spo2", "sleep_hours"), 5),
    RoutineTask("dosimeter", "Dosimeter reading", "Log today's personal radiation dose.",
                ("radiation_dose",), 5),
    RoutineTask("exercise", f"Exercise countermeasures ≥ {EXERCISE_TARGET} min",
                "Treadmill, cycle and resistance work protect bone and muscle.",
                ("exercise_minutes",), 25),
)

LEVELS = [(0, "Cadet"), (1500, "Mission Specialist"), (3000, "Flight Engineer"),
          (4500, "Commander"), (6000, "Mission Legend")]
SLEEP_TARGET = 6.5  # hours; ISS crews average about 6 h, so this is a realistic stretch goal
# Follow-up re-measurement only makes sense for spot measurements.
REMEASURABLE = {"heart_rate", "systolic_bp", "diastolic_bp", "spo2", "glucose", "body_temp"}

WELLNESS = {
    "behavioural": [
        ("wind_down", "Wind-down routine tonight", "Lights dim and screens off an hour before your sleep window."),
        ("call_home", "Private call home", "Book a family or friends call for your next comms window."),
    ],
    "general": [
        ("hydrate", "Hydrate: 2 L of water", "Fluid shifts in microgravity make it easy to fall behind."),
        ("window", "10-minute window break", "Earth- or Moon-gazing is a proven mood booster."),
    ],
    "critical": [
        ("call_surgeon", "Contact the flight surgeon", "Critical reading today. Report it to the ground team."),
    ],
}


def _reading(store: MissionStore, crew_id: str, key: str, day: int):
    return next((r for r in store.readings(crew_id, key, day) if r.day == day), None)


def _routine_done(store: MissionStore, crew_id: str, task: RoutineTask, day: int, today: int) -> bool:
    for key in task.indicators:
        r = _reading(store, crew_id, key, day)
        if r is None:
            return False
        if day == today and key not in AUTO and r.source != "manual":
            return False
        if key == "exercise_minutes" and r.value < EXERCISE_TARGET:
            return False
    return True


def _streak(flags: list[bool], today_done: bool) -> int:
    """Consecutive completed days ending today (or yesterday, if today isn't done yet)."""
    n = 1 if today_done else 0
    for ok in reversed(flags):
        if not ok:
            break
        n += 1
    return n


def _level(points: int) -> dict:
    current = max((lv for lv in LEVELS if points >= lv[0]), key=lambda lv: lv[0])
    nxt = next((lv for lv in LEVELS if lv[0] > points), None)
    return {"title": current[1], "points": points,
            "next_title": nxt[1] if nxt else None, "next_at": nxt[0] if nxt else None,
            "floor": current[0]}


def mission_tasks(store: MissionStore, crew_id: str) -> dict:
    today = store.current_day
    status = store.status(crew_id, today)
    flagged = [a for a in status["indicators"] if a["level"] != Level.NORMAL.label]
    # Follow-ups cover anything flagged today or yesterday, so a task stays on the list (ticked)
    # after a re-measurement brings the indicator back to normal.
    flagged_keys = {a["indicator"] for a in flagged}
    if today > 1:
        flagged_keys |= {a["indicator"] for a in store.status(crew_id, today - 1)["indicators"]
                         if a["level"] != Level.NORMAL.label}
    by_key = {a["indicator"]: a for a in status["indicators"]}
    prev = {a["indicator"]: a for a in store.status(crew_id, today - 1)["indicators"]} if today > 1 else {}
    done_extra = store.task_completions.get(crew_id, {}).get(today, set())

    tasks = []
    for t in ROUTINE:
        tasks.append({"id": t.id, "kind": "routine", "title": t.title, "description": t.description,
                      "indicators": list(t.indicators), "points": t.points,
                      "done": _routine_done(store, crew_id, t, today, today),
                      "auto": all(k in AUTO for k in t.indicators)})

    for key in [k for k in by_key if k in flagged_keys and k in REMEASURABLE]:
        a = by_key[key]
        level = a["level"] if a["level"] != Level.NORMAL.label else prev[key]["level"]
        r = _reading(store, crew_id, key, today)
        tasks.append({"id": f"followup_{key}", "kind": "follow_up",
                      "title": f"Re-measure {a['name'].lower()}",
                      "description": f"Flagged {level}. A fresh manual reading confirms whether it's real.",
                      "indicators": [key], "points": 15, "level": level,
                      "done": bool(r and r.source == "manual"), "auto": False})

    behavioural = any(a["indicator"] in ("sleep_hours", "mood") for a in flagged)
    pool = (WELLNESS["critical"] if status["escalate"] else []) + \
        WELLNESS["behavioural" if behavioural else "general"]
    for wid, title, desc in pool:
        tasks.append({"id": wid, "kind": "wellness", "title": title, "description": desc,
                      "indicators": [], "points": 10, "done": wid in done_extra, "auto": False})

    # History: routine compliance per past in-flight day.
    history = {t.id: [_routine_done(store, crew_id, t, d, today) for d in range(1, today)] for t in ROUTINE}
    checkin_flags = [all(history[t.id][i] for t in ROUTINE if t.id != "exercise") for i in range(today - 1)]
    today_checkin = all(x["done"] for x in tasks if x["kind"] == "routine" and x["id"] != "exercise")
    today_ex = next(x["done"] for x in tasks if x["id"] == "exercise")

    sleep_flags = []
    for d in range(1, today + 1):
        r = _reading(store, crew_id, "sleep_hours", d)
        sleep_flags.append(bool(r and r.value >= SLEEP_TARGET))

    points = sum(t.points for t in ROUTINE for ok in history[t.id] if ok)
    points += sum(x["points"] for x in tasks if x["done"])
    points += 10 * sum(len(v) for d, v in store.task_completions.get(crew_id, {}).items() if d != today)

    streaks = {
        "checkin": _streak(checkin_flags, today_checkin),
        "exercise": _streak(history["exercise"], today_ex),
        "sleep": _streak(sleep_flags[:-1], sleep_flags[-1]),
    }
    best_ex = max_run(history["exercise"] + [today_ex])
    manual_today = any(r.source == "manual" for k in AUTO | {"systolic_bp", "diastolic_bp", "body_temp", "glucose", "mood"}
                       for r in [_reading(store, crew_id, k, today)] if r)
    followups = [x for x in tasks if x["kind"] == "follow_up"]

    badges = [
        _badge("baseline", "Baseline Builder", "🧬", "Completed 7 days of preflight baseline data.", True),
        _badge("storm", "Storm Survivor", "☀️", "Logged your dose through a solar particle event.",
               any((_reading(store, crew_id, "radiation_dose", d) or _Zero).value >= 10 for d in range(1, today + 1))),
        _badge("iron", "Iron Crew", "🏋️", f"7 days in a row at {EXERCISE_TARGET}+ min of exercise.", best_ex >= 7),
        _badge("month", "30-Day Streak", "🔥", "Completed the routine 30 days in a row.",
               max_run(checkin_flags + [today_checkin]) >= 30),
        _badge("self_aware", "Self-Aware", "🩺", "Logged a manual check-in today.", manual_today),
        _badge("early_catch", "Early Catch", "🎯", "Re-measured every flagged indicator the same day.",
               bool(followups) and all(x["done"] for x in followups)),
        _badge("rested", "Well Rested", "🌙", f"7 nights in a row with {SLEEP_TARGET}+ hours of sleep.", max_run(sleep_flags) >= 7),
    ]

    done = [x for x in tasks if x["done"]]
    return {
        "crew_id": crew_id,
        "day": today,
        "tasks": tasks,
        "progress": {"done": len(done), "total": len(tasks),
                     "points_today": sum(x["points"] for x in done)},
        "streaks": streaks,
        "level": _level(points),
        "badges": badges,
    }


class _Zero:
    value = 0.0


def max_run(flags: list[bool]) -> int:
    best = cur = 0
    for ok in flags:
        cur = cur + 1 if ok else 0
        best = max(best, cur)
    return best


def _badge(bid: str, name: str, icon: str, description: str, earned: bool) -> dict:
    return {"id": bid, "name": name, "icon": icon, "description": description, "earned": bool(earned)}


def complete_wellness(store: MissionStore, crew_id: str, task_id: str) -> None:
    valid = {wid for pool in WELLNESS.values() for wid, _, _ in pool}
    if task_id not in valid:
        raise ValueError(f"'{task_id}' is not a task you can tick off by hand")
    store.task_completions.setdefault(crew_id, {}).setdefault(store.current_day, set()).add(task_id)
