"""Countermeasure planner: turn today's status into a concrete daily schedule.

Alerts say *what* is wrong; the planner says *when and how* to act today. It starts from a
standard long-duration day (about 2.5 h of exercise: aerobic plus resistive, as on the ISS)
and adapts each block to the astronaut's flagged indicators, symptom triage and radiation
budget. Every change carries the reason and the indicator that caused it.

Fixed prototype rules, not AI, and not a medical prescription: the flight surgeon and the
exercise specialists own the real plan.
"""

from __future__ import annotations

from . import radiation, symptoms

ISS_REFS = [
    "NASA: ISS crews exercise about 2.5 hours a day (treadmill T2, cycle CEVIS, resistive device ARED)",
    "NASA HRP: lighting countermeasures and sleep scheduling for circadian alignment",
    "NASA-STD-3001 Vol. 1: ALARA radiation exposure and storm shelter use",
]


def _block(id_, time, title, minutes, detail, kind, because=None, indicator=None, changed=False):
    return {"id": id_, "time": time, "title": title, "minutes": minutes, "detail": detail, "kind": kind,
            "because": because, "indicator": indicator, "changed": changed}


def plan(store, crew_id: str, day: int | None = None) -> dict:
    day = store.current_day if day is None else day
    st = store.status(crew_id, day)
    lvl = {i["indicator"]: i["level"] for i in st["indicators"]}
    val = {i["indicator"]: i for i in st["indicators"]}
    flagged = lambda k: lvl.get(k) in ("warning", "critical")  # noqa: E731
    sym = symptoms.report(store.symptoms[crew_id], day)
    sym_keys = {x["key"] for e in sym["log"] if e["day"] == day for x in e["symptoms"]}
    rad = radiation.budget(store, crew_id, day)
    fever = lvl.get("body_temp") == "critical" or "chills" in sym_keys
    red_flag = sym["triage"]["level"] == "critical"

    blocks = []
    # Morning light and measurements
    if flagged("sleep_hours") or flagged("mood"):
        blocks.append(_block("light", "06:30", "Bright-light session", 30,
                             "Sit by the blue-enriched light panel at full setting while you eat breakfast.",
                             "sleep", "Shifts your body clock earlier to help you fall asleep tonight.",
                             "sleep_hours", True))
    blocks.append(_block("vitals", "07:00", "Morning vitals", 10,
                         "Blood pressure (2 readings), temperature and fasting glucose before breakfast.", "measure"))

    # Exercise
    if fever or red_flag:
        why = "Fever or chills" if fever else "A red-flag symptom"
        blocks.append(_block("rest", "09:00", "Exercise suspended: rest", 0,
                             "No exercise today. Rest, hydrate (at least 2.5 L) and stay away from the crew if you can.",
                             "rest", f"{why}: exercise would add strain. Restart when ground clears you.",
                             "body_temp", True))
    else:
        aerobic = 45
        detail = "Treadmill (harness) or cycle at a moderate, conversational pace."
        because = indicator = None
        changed = False
        if flagged("heart_rate") or flagged("systolic_bp") or flagged("diastolic_bp"):
            aerobic, changed = 40, True
            detail = "Steady cycle at 60-70% of your max heart rate. No intervals or maximal efforts today."
            because = "Heart rate or blood pressure is above your baseline: keep the effort steady."
            indicator = next(k for k in ("heart_rate", "systolic_bp", "diastolic_bp") if flagged(k))
        blocks.append(_block("aerobic", "09:00", "Aerobic session", aerobic, detail, "exercise", because, indicator, changed))

        resist = 60
        r_detail = "Resistive device: squats, deadlifts, heel raises and upper body, 3 sets each."
        r_because = r_ind = None
        r_changed = False
        if flagged("exercise_minutes"):
            resist, r_changed = 75, True
            r_detail = "Resistive device, longer session: legs and spine first (squats, deadlifts, heel raises)."
            r_because = "Exercise time is below target, and resistive work protects bone and muscle the most."
            r_ind = "exercise_minutes"
        if "back_pain" in sym_keys or "muscle_pain" in sym_keys:
            r_changed = True
            r_detail = "Lighter loads with a slow tempo; skip any movement that hurts. Add 10 min of stretching."
            r_because = "You logged back or muscle pain today."
            r_ind = r_ind or "exercise_minutes"
        hour = "13:30" if not flagged("sleep_hours") else "13:00"
        blocks.append(_block("resistive", hour, "Resistive session", resist, r_detail, "exercise", r_because, r_ind, r_changed))

        if flagged("glucose"):
            blocks.append(_block("walk", "12:45", "Post-meal cycle", 15,
                                 "Easy cycle for 15 minutes straight after lunch.", "exercise",
                                 "Fasting glucose is above your baseline; light activity after meals lowers it.",
                                 "glucose", True))

    # Radiation
    if rad["level"] != "normal":
        blocks.append(_block("shield", "All day", "Limit high-dose time", 0,
                             "Postpone non-essential EVA and work in less-shielded modules. Sleep in the shielded crew quarters.",
                             "radiation", " ".join(rad["reasons"]), "radiation_dose", True))

    # Behavioural health
    if flagged("mood") or "low_mood" in sym_keys:
        blocks.append(_block("social", "18:30", "Private family call", 30,
                             "Book a private call home, or a crew meal with no work talk.", "wellbeing",
                             "Mood is below your baseline; social contact is one of the best countermeasures.",
                             "mood", True))
    blocks.append(_block("checkin", "19:30", "Evening check-in", 5,
                         "Mood rating, symptoms and dosimeter in AURA.", "measure"))

    # Sleep
    if flagged("sleep_hours") or "insomnia" in sym_keys:
        blocks.append(_block("winddown", "21:00", "Wind-down", 60,
                             "Dim, amber light; no screens or exercise; stow work. Same bedtime every night.",
                             "sleep", "Sleep is below your baseline: protect the hour before bed.", "sleep_hours", True))
        blocks.append(_block("sleep", "22:00", "Sleep window", 510,
                             "8.5 h in the sleep station with the light off and earplugs in.", "sleep",
                             "A longer, fixed sleep window to recover lost sleep.", "sleep_hours", True))
    else:
        blocks.append(_block("sleep", "22:30", "Sleep window", 480, "8 h in the sleep station.", "sleep"))

    order = {"All day": "00:00"}
    blocks.sort(key=lambda b: order.get(b["time"], b["time"]))
    exercise = sum(b["minutes"] for b in blocks if b["kind"] == "exercise")
    done = store.plan_done.get((crew_id, day), set())
    for b in blocks:
        b["done"] = b["id"] in done
    return {
        "crew_id": crew_id,
        "day": day,
        "blocks": blocks,
        "changes": sum(b["changed"] for b in blocks),
        "exercise_minutes": exercise,
        "summary": (
            "Rest day: exercise is suspended until ground clears you." if fever or red_flag else
            f"{exercise} min of exercise, with {sum(b['changed'] for b in blocks)} change(s) for today's flags."
            if any(b["changed"] for b in blocks) else
            f"Standard day: {exercise} min of exercise. Nothing needs adjusting."
        ),
        "references": ISS_REFS,
        "note": "Prototype rules, not a prescription. The flight surgeon and exercise specialists own the real plan.",
    }
