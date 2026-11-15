"""Symptom log with rule-based triage.

Numbers miss things an astronaut feels: a headache, blurry near vision, nausea. Crew log
symptoms with a 1 to 10 severity, and AURA triages them with fixed rules (no AI decides the level):

* critical: a red-flag symptom (chest pain, breathing difficulty, sudden vision loss, fainting,
  confusion, severe flank pain) or any symptom at severity 9 or more. Contact the flight surgeon now.
* warning: a symptom that needs follow-up (vision change: possible SANS; persistent headache;
  motion sickness after the first 3 days), severity 7 or more, or the same symptom on 3 of the
  last 5 days.
* normal: expected adaptation (fluid-shift congestion, back pain and motion sickness early in the
  mission) or mild symptoms. Self-care advice.

Each symptom links to the AURA indicators worth checking, so the log and the telemetry tell
one story. Prototype rules informed by NASA HRP evidence; not clinically validated.
"""

from __future__ import annotations

from dataclasses import dataclass

EARLY_DAYS = 3
PERSIST_WINDOW = 5
PERSIST_COUNT = 3


@dataclass(frozen=True)
class Symptom:
    key: str
    name: str
    group: str
    red_flag: bool = False
    follow_up: bool = False  # always at least a warning
    early_ok: bool = False  # expected in the first EARLY_DAYS of flight
    advice: str = ""
    related: tuple[str, ...] = ()
    why: str = ""


CATALOG: dict[str, Symptom] = {s.key: s for s in [
    Symptom("chest_pain", "Chest pain or pressure", "Heart and lungs", red_flag=True,
            advice="Stop activity, sit or lie down, take vitals and contact the flight surgeon now.",
            related=("heart_rate", "systolic_bp", "spo2"), why="Could be cardiac; needs urgent review."),
    Symptom("breathing", "Difficulty breathing", "Heart and lungs", red_flag=True,
            advice="Check SpO2 and cabin CO2, use oxygen if available and contact the flight surgeon now.",
            related=("spo2", "heart_rate"), why="Low oxygen or high cabin CO2 can be dangerous fast."),
    Symptom("vision_loss", "Sudden vision loss", "Eyes and head", red_flag=True,
            advice="Stop tasks, note which eye and contact the flight surgeon now.",
            related=(), why="Sudden loss needs urgent eye and neurological review."),
    Symptom("fainting", "Fainting or near-fainting", "Heart and lungs", red_flag=True,
            advice="Stay secured, take blood pressure and heart rate, contact the flight surgeon now.",
            related=("systolic_bp", "heart_rate"), why="Orthostatic intolerance or heart rhythm problem."),
    Symptom("confusion", "Confusion or slurred speech", "Eyes and head", red_flag=True,
            advice="A crewmate should stay with you; contact the flight surgeon now.",
            related=("spo2", "glucose", "body_temp"), why="Possible stroke, hypoxia, low glucose or high CO2."),
    Symptom("flank_pain", "Severe side or back pain with urine changes", "Kidneys", red_flag=True,
            advice="Drink water, record urine changes and contact the flight surgeon now.",
            related=(), why="Bone loss in flight raises kidney stone risk."),
    Symptom("blurred_vision", "Blurry near vision or visual distortion", "Eyes and head", follow_up=True,
            advice="Log which eye, avoid straining, and ask ground to schedule an eye exam (OCT, fundoscopy).",
            related=("systolic_bp",),
            why="A sign of Spaceflight-Associated Neuro-ocular Syndrome (SANS), seen in many long-duration crew."),
    Symptom("headache", "Headache", "Eyes and head",
            advice="Hydrate, check cabin CO2 and rest. Log it again if it comes back.",
            related=("sleep_hours", "systolic_bp"), why="Common with fluid shift and CO2; persistent headache with vision change can mean SANS."),
    Symptom("nausea", "Nausea or vomiting", "Stomach",
            early_ok=True, advice="Move slowly, keep your head still and use the anti-nausea medication on the flight plan.",
            related=("glucose",), why="Space motion sickness is common in the first 2 to 3 days; later it needs a look."),
    Symptom("congestion", "Stuffy nose or puffy face", "Eyes and head", early_ok=True,
            advice="Expected from fluid shifting to the head. Hydrate and use saline spray.",
            related=(), why="Fluid shift in microgravity."),
    Symptom("back_pain", "Back pain", "Bones and muscles", early_ok=True,
            advice="Gentle stretching and knees-to-chest position. Report if it spreads to the legs.",
            related=("exercise_minutes",), why="The spine lengthens in microgravity; very common early on."),
    Symptom("muscle_pain", "Muscle or joint pain", "Bones and muscles",
            advice="Check your exercise load and form; rest the area for a day.",
            related=("exercise_minutes",), why="Exercise countermeasure strain or deconditioning."),
    Symptom("fatigue", "Unusual tiredness", "Whole body",
            advice="Prioritise sleep tonight and log temperature in your next check-in.",
            related=("sleep_hours", "body_temp", "mood"), why="Sleep loss, workload or a starting infection."),
    Symptom("chills", "Chills or feeling feverish", "Whole body", follow_up=True,
            advice="Take your temperature now, hydrate, and isolate from the crew if you can.",
            related=("body_temp", "heart_rate"), why="Latent viruses can reactivate in flight; infection spreads fast in a small cabin."),
    Symptom("insomnia", "Trouble sleeping", "Mind and sleep",
            advice="Keep the light schedule, avoid screens before sleep, and use the sleep station.",
            related=("sleep_hours", "mood"), why="Circadian disruption and stress; affects mood and performance."),
    Symptom("low_mood", "Low mood or anxiety", "Mind and sleep",
            advice="Talk to a crewmate, schedule a private call with family or the psychologist.",
            related=("mood", "sleep_hours"), why="Isolation and confinement are a known behavioural-health risk."),
    Symptom("rash", "Skin rash or irritation", "Skin",
            advice="Keep the skin clean and dry; photograph the rash for ground.",
            related=("body_temp",), why="Skin sensitivity is common in flight; with fever it can mean viral reactivation."),
]}

RANK = {"normal": 0, "warning": 1, "critical": 2}


def triage(entries: list[dict], history: list[dict], day: int) -> dict:
    """Triage one day's logged symptoms, using the earlier log for persistence."""
    level, reasons, actions, related = "normal", [], [], []

    def raise_to(lvl: str) -> None:
        nonlocal level
        if RANK[lvl] > RANK[level]:
            level = lvl

    recent = [h for h in history if day - PERSIST_WINDOW < h["day"] <= day]
    keys_today = {e["key"] for e in entries}
    for e in sorted(entries, key=lambda x: -x["severity"]):
        s = CATALOG[e["key"]]
        sev = e["severity"]
        days_logged = len({h["day"] for h in recent if any(x["key"] == s.key for x in h["symptoms"])})
        if s.red_flag:
            raise_to("critical")
            reasons.append(f"{s.name} is a red-flag symptom.")
        elif sev >= 9:
            raise_to("critical")
            reasons.append(f"{s.name} at severity {sev}/10 is severe.")
        elif s.follow_up:
            raise_to("warning")
            reasons.append(f"{s.name} needs follow-up. {s.why}")
        elif s.early_ok and day <= EARLY_DAYS and sev < 7:
            reasons.append(f"{s.name} is expected in the first days of flight.")
        elif s.early_ok and s.key == "nausea" and day > EARLY_DAYS:
            raise_to("warning")
            reasons.append(f"{s.name} after day {EARLY_DAYS} is not typical motion sickness.")
        elif sev >= 7:
            raise_to("warning")
            reasons.append(f"{s.name} at severity {sev}/10.")
        if days_logged >= PERSIST_COUNT and not s.red_flag:
            raise_to("warning")
            reasons.append(f"{s.name} logged on {days_logged} of the last {PERSIST_WINDOW} days.")
        actions.append(s.advice)
        related += [r for r in s.related if r not in related]
    if {"headache", "blurred_vision"} <= keys_today:
        raise_to("warning")
        reasons.append("Headache with a vision change: ask ground for a SANS eye exam.")
    if level == "critical":
        actions.insert(0, "Contact the flight surgeon now (use Message ground).")
    if not entries:
        reasons = ["No symptoms logged for this day."]
    elif level == "normal" and not reasons:
        reasons = ["Mild symptoms. Self-care is enough for now; log again if they change."]
    return {"day": day, "level": level, "reasons": reasons, "actions": actions,
            "related_indicators": related, "escalate": level == "critical"}


def seed_demo(crew, days: int) -> dict[str, list[dict]]:
    """Synthetic symptom logs that match each demo scenario's story (labelled synthetic)."""
    logs: dict[str, list[dict]] = {}

    def log(cid: str, day: int, items: list[tuple[str, int]], note: str = "") -> None:
        if 1 <= day <= days:
            logs.setdefault(cid, []).append({"day": day, "symptoms": [{"key": k, "severity": v} for k, v in items],
                                             "note": note, "source": "synthetic"})

    for m in crew:
        if m.imported is not None:
            continue
        log(m.id, 1, [("congestion", 3), ("back_pain", 4)], "Puffy face, lower back ache after launch")
        if m.scenario == "immune_fever":
            log(m.id, days - 3, [("fatigue", 5)])
            log(m.id, days - 1, [("fatigue", 6), ("chills", 6)], "Cold and achy all afternoon")
            log(m.id, days, [("chills", 7), ("fatigue", 7), ("headache", 4)])
        elif m.scenario == "behavioural_cardio":
            for d in (days - 16, days - 11, days - 6, days - 2):
                log(m.id, d, [("insomnia", 6), ("low_mood", 4)])
        elif m.scenario == "circadian":
            for d in (days - 9, days - 5, days - 2):
                log(m.id, d, [("insomnia", 6), ("fatigue", 5)])
        elif m.scenario == "deconditioning":
            for d in (days - 10, days - 4):
                log(m.id, d, [("muscle_pain", 4), ("fatigue", 4)])
    return logs


def day_symptoms(logs: list[dict], day: int) -> list[dict]:
    """All symptoms logged on one day, merged (highest severity wins)."""
    merged: dict[str, int] = {}
    for entry in logs:
        if entry["day"] == day:
            for x in entry["symptoms"]:
                merged[x["key"]] = max(merged.get(x["key"], 0), x["severity"])
    return [{"key": k, "severity": v} for k, v in merged.items()]


def report(logs: list[dict], day: int) -> dict:
    """The log up to ``day`` with names, and the triage for that day."""
    shown = [e for e in logs if e["day"] <= day]
    named = [{**e, "symptoms": [{**x, "name": CATALOG[x["key"]].name} for x in e["symptoms"]]} for e in shown]
    t = triage(day_symptoms(shown, day), shown, day)
    return {"day": day, "triage": t, "log": sorted(named, key=lambda e: -e["day"])}


def catalog() -> list[dict]:
    return [{"key": s.key, "name": s.name, "group": s.group, "red_flag": s.red_flag, "why": s.why}
            for s in CATALOG.values()]
