"""AURA assistant: the floating "Ask AURA" chat, available on every screen.

Unlike the flight-surgeon panel (which is about one astronaut's data), the assistant answers any
question: health questions about whoever is on screen, how to use AURA, the real NASA research
data, or general spaceflight-health questions. Every reply has a short answer, optional numbered
steps, and optional one-click actions that drive the dashboard (open an indicator, the check-in
form, the crew editor...). Actions are validated here, so the model can't invent targets.

Safety: the same rules as the flight surgeon. The rule engine owns every alert level, critical
readings always escalate, and it never diagnoses, prescribes or doses medication.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from . import research, symptoms
from .ai import FALLBACK_BETA, _client, _describe, _refused, ai_status, build_context
from .alerts import Level
from .store import MissionStore

log = logging.getLogger("aura.assistant")

ActionType = Literal["open_indicator", "open_checkin", "open_briefing", "open_crew_editor",
                     "open_import", "add_indicator", "open_research", "start_tour", "select_crew",
                     "message_ground", "open_radiation", "open_symptoms", "open_ground", "open_plan", "open_team",
                     "remember", "draft_ground_message", "go_to_day", "log_symptom"]
TARGETED = {"open_indicator", "select_crew", "remember", "draft_ground_message", "go_to_day", "log_symptom"}

APP_GUIDE = """\
AURA dashboard guide (use these exact names when telling the user where to click):
- Crew box (left sidebar): click a crew member to view them. "✎ Edit" opens the crew editor (add/remove \
members, name, role, age, personal baselines, health scenario). "⬆ Import" adds a crew member from the \
user's own CSV (a 'day' column; days -7..-1 are preflight baseline, 1, 2, 3... mission days; one column per \
indicator; template at data/import_template.csv).
- Mission replay (sidebar): drag the slider to see any past day; "Live" is the current day.
- Message ground (sidebar, 📡): send a message to the flight surgeon with today's status packet attached. \
It shows the real signal delay for the environment (ISS ~0.5 s, Moon ~1.3 s, Mars transit grows to ~12.5 min \
one way) with a countdown; a SIMULATED ground reply comes back after the round trip. A demo clock runs 60x \
faster. When the delay is minutes, AURA's own guidance is the crew's first line of support. The red escalate \
line on the status banner has "Message ground now →", which drafts an urgent message.
- Today's countermeasure plan panel (below the indicator cards): a timed daily schedule (bright light, \
vitals, aerobic and resistive exercise, post-meal cycle, radiation limits, family call, wind-down, sleep \
window) adapted to the person's flags; adjusted blocks say why and link to the indicator. Fever or a \
red-flag symptom suspends exercise. Tick blocks off on the live day.
- Symptom log panel (below the indicator cards): pick symptoms by body area, rate each 1-10, click "Log and \
triage". Rule-based triage: red flags (chest pain, breathing difficulty, sudden vision loss, fainting, confusion, \
severe flank pain) or severity 9+ = critical, contact the flight surgeon now; vision change (possible SANS), \
chills, late nausea, severity 7+ or a symptom on 3 of the last 5 days = warning; early fluid-shift symptoms = \
self-care. It links to the indicators worth checking.
- Radiation dose budget panel (below the indicator cards): career dose against NASA's 600 mSv limit \
(earlier missions plus this one), dose rate, days left at this rate, the last 30 days against the 250 limit, \
and a cumulative chart projected to the planned mission end. Prior career dose is set per person in ✎ Edit.
- Mission routine (sidebar): daily tasks, streaks, points, levels and badges. Measurement tasks tick \
themselves when a check-in logs the reading.
- Header: "👩‍🚀 Crew / 👥 Team / 🛰 Ground" toggle. Team is crew wellbeing: a 0-100 wellbeing score per person \
and for the crew (mood and sleep below baseline, behavioural symptoms, missed exercise over 7 days; thriving \
>= 75, watch 55-74, needs support < 55), mood and sleep trend charts for everyone, and team suggestions. Ground is the flight-surgeon console: every crew member on one screen, \
sorted by priority (the worst of telemetry, symptom triage and radiation), with flagged readings, symptoms, \
radiation, trends and messages received (only once their signal has arrived). "🖨 Crew report" and each \
card's "🖨 Report" (also "🖨 Report" on the status banner) open a printable report; save it as PDF from the \
print dialog. Environment selector (ISS, lunar surface, Mars transit) regenerates the mission; "▶ Demo tour" \
walks through the story in 17 steps.
- Status banner: the overall Normal / Warning / Critical level for the selected person and day.
- AI flight surgeon panel: "Generate daily briefing" (left) and the "Early-warning forecast" (right): \
indicators whose straight-line trend would cross the edge of the personal baseline, a warning or a critical \
limit within 14 days. The trend chart in an indicator's detail view shows the 7-day projection as a dashed line.
- Ask AURA: this chat (bottom-right button), available on every screen. The conversation is kept across \
reloads. 🧠 Memory (in the chat header) lists notes the user saved by asking "remember that …"; they are used \
in later answers and can be deleted there. Buttons can open things, replay a day, preselect a symptom in the \
symptom log, or draft a message to ground for the user to review.
- Body status: clickable body figure coloured by each body system's worst indicator; click a region to \
filter the indicator cards.
- Health indicators panel: "Compare with: Preflight baseline / Adaptive in-flight" switch. Adaptive learns \
the person's in-flight normal from days d-28 to d-8 (outliers left out) but moves at most 1 preflight SD, so \
expected adaptation (e.g. slightly warmer core temperature in flight) isn't flagged while slow drifts still are. \
One card per indicator; click a card for the detail view (trend chart with \
personal baseline band and limits, why it matters, how to measure, actions, references). "+ Add indicator" \
(top right of that panel) creates a custom indicator (presets: body weight, heart rate variability, daily \
steps, water intake).
- Daily check-in panel: type today's readings (and mood, notes). Only for the live day.
- Alert timeline: every change of alert level; click one to jump there.
- Real crew data · Inspiration4 panel (bottom): real NASA OSDR bloodwork (metabolic panel and blood count) \
for 4 civilian crew, 92 days before launch to 194 days after return; "Review C00n" gives an AI review.
Alert rules: Critical = a predefined critical limit is crossed (contact the flight surgeon now). Warning = a \
warning limit is crossed, or the last 3 readings sit on the adverse side of the personal baseline (each \
>=1.5 SD, mean >=2 SD and a meaningful change), or one reading is >=3.5 SD out (re-measure). Baselines come \
from 7 preflight days. Demo telemetry is synthetic; the Inspiration4 data is real; imported data is the user's.
"""

ASSISTANT_PROMPT = """\
You are "Ask AURA", the assistant built into AURA, a health self-monitoring tool for astronauts on \
long-duration missions. You appear as a chat window on every screen. The user may be an astronaut, a \
mission medical team member, or a hackathon judge trying the demo.

You receive: the app guide, what the user is looking at (crew member, day, selected indicator), a JSON \
snapshot of that person's indicators and alerts, the crew roster, and a summary of the real NASA research \
data. Answer ANY question:
- Health questions: ground every claim in the data given, with numbers and units. Explain what a level \
means, link related indicators and spaceflight hazards, and give practical steps doable on a spacecraft.
- "How do I..." questions: give the exact clicks, using the names in the app guide.
- General spaceflight or health questions: answer briefly from general knowledge and say when something \
is general information rather than this person's data.
- Off-topic questions: answer briefly if harmless, then offer to help with AURA.

Rules:
1. Alert levels come from AURA's rule engine and are authoritative; never change or contradict them.
2. If the person on screen has any critical reading, or the user describes an emergency (chest pain, \
trouble breathing, confusion, fainting, severe bleeding), set escalate=true and say first: follow the \
critical actions and contact the flight surgeon now.
3. Never diagnose, prescribe or dose medication. Defer clinical decisions to the flight surgeon.
4. Steps: 0-4 short imperative steps when the user should do something; empty for simple facts.
5. Actions: 0-3 buttons that help right now, chosen ONLY from the allowed types. These need a target: \
open_indicator (an indicator key from the context), select_crew (a crew id), go_to_day (a mission day number \
up to mission_day, to replay that day), log_symptom (a symptom key from symptom_keys, preselects it in the \
symptom log), draft_ground_message (the full text of a short message to the flight surgeon, which the user \
reviews before sending), remember (a short note, at most 200 characters, to save to AURA's memory). Other \
types take no target.
7. Memory: "memory" lists notes the user asked AURA to remember (preferences, history, context). Use them \
when relevant. When the user asks you to remember something, offer a remember action with a concise note; \
it is only saved if they click it.
6. Be brief: the answer is at most about 90 words. Plain language; explain medical terms briefly.
"""


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class AssistantAction(BaseModel):
    type: ActionType
    label: str = Field(description="Button text, at most 5 words")
    target: str | None = Field(None, description="See rule 5: indicator key, crew id, day, symptom key, message or note")


class AssistantReply(BaseModel):
    answer: str = Field(description="At most about 90 words, plain language")
    steps: list[str] = Field(description="0-4 short imperative steps")
    actions: list[AssistantAction] = Field(description="0-3 one-click actions")
    escalate: bool = Field(description="True if the user should contact the flight surgeon now")
    topic: Literal["health", "app_help", "research", "general", "off_topic"]


def _research_summary() -> dict | None:
    sets = research.all_datasets()
    if not sets:
        return None
    return {
        "mission": "Inspiration4 (3-day orbital flight, Sept 2021), 4 civilian crew C001-C004, real NASA OSDR data",
        "panels": [{"title": d["title"], "osd": d["osd"],
                    "most_out_of_range": [f"{a['name']} ({a['out_of_range']})" for a in
                                          sorted(d["analytes"], key=lambda a: -a["out_of_range"])[:4]
                                          if a["out_of_range"]]} for d in sets],
        "quality_issues": [q["reason"] for d in sets for q in d["quality_issues"]],
    }


def build_assistant_context(store: MissionStore, crew_id: str | None, day: int | None,
                            indicator: str | None) -> dict:
    roster = []
    for c in store.crew.values():
        s = store.status(c.id)
        roster.append({"id": c.id, "name": c.name, "role": c.role, "overall": s["overall"],
                       "data": "imported" if c.imported is not None else "synthetic"})
    ctx: dict = {"mission_day": store.current_day, "environment": store.dataset.environment_info["name"],
                 "crew_roster": roster, "research_data": _research_summary(),
                 "symptom_keys": sorted(symptoms.CATALOG),
                 "memory": [m["text"] for m in store.memory if m["crew_id"] in (None, crew_id)][-20:]}
    if crew_id in store.crew:
        snap = build_context(store, crew_id, day)
        for i in snap["indicators"]:  # keep the snapshot compact
            i["recent"] = [r["value"] for r in i["recent"]]
        ctx["viewing"] = {"crew_id": crew_id, "day": snap["mission"]["day"], "selected_indicator": indicator}
        ctx["person"] = snap
    return ctx


# --------------------------------------------------------------------------- validation
def _clean(reply: AssistantReply, ctx: dict) -> AssistantReply:
    person = ctx.get("person") or {}
    keys = {i["key"] for i in person.get("indicators", [])}
    crew_ids = {c["id"] for c in ctx["crew_roster"]}
    ok = []
    for a in reply.actions:
        t = (a.target or "").strip()
        if a.type == "open_indicator" and t not in keys:
            continue
        if a.type == "select_crew" and t not in crew_ids:
            continue
        if a.type == "go_to_day" and not (t.isdigit() and 1 <= int(t) <= ctx["mission_day"]):
            continue
        if a.type == "log_symptom" and t not in symptoms.CATALOG:
            continue
        if a.type in ("remember", "draft_ground_message") and not 1 <= len(t) <= (200 if a.type == "remember" else 1000):
            continue
        a.target = t if a.type in TARGETED else None
        ok.append(a)
    reply.actions = ok[:3]
    reply.steps = reply.steps[:4]
    # A critical reading always escalates health answers; "how do I..." answers aren't nagged.
    if reply.topic == "health":
        reply.escalate = reply.escalate or bool(person.get("escalate"))
    return reply


# --------------------------------------------------------------------------- offline
FAQ: list[tuple[str, str, list[str], list[tuple[str, str]]]] = [
    (r"import|csv|upload|my (own )?data", "You can add yourself as a crew member from a CSV of your own readings.",
     ["Click ⬆ Import in the Crew box.", "Enter your name, role and age.",
      "Choose a CSV with a 'day' column (−7 to −1 = baseline, 1, 2, 3… = mission days).",
      "Click Import and add to crew."], [("open_import", "Import my data")]),
    (r"(add|new|custom).*(indicator|measure|metric)|weight|hrv|steps", "Add any measurement with + Add indicator.",
     ["Open the Health indicators panel.", "Click + Add indicator (top right).",
      "Pick a preset or fill in the name, unit, typical range and limits.", "Click Add indicator."],
     [("add_indicator", "Add an indicator")]),
    (r"edit|crew member|add (a )?(person|member)|scenario|rename", "The crew editor lets you change who is on the mission.",
     ["Click ✎ Edit in the Crew box.", "Change names, roles, ages, baselines or the health scenario.",
      "Click Save and regenerate."], [("open_crew_editor", "Edit the crew")]),
    (r"ground view|flight surgeon (view|console)|health report|crew report|export|pdf|print|whole crew|all crew",
     "The Ground view shows the whole crew for the flight surgeon, and every view can export a printable report.",
     ["Click 🛰 Ground in the header to see every crew member sorted by priority.",
      "Click 🖨 Crew report for the whole crew, or 🖨 Report on one person's card or status banner.",
      "In the report tab, click Print / Save as PDF."], [("open_ground", "Open the Ground view")]),
    (r"team|wellbeing|well-being|morale|crew mood|cohesion|behavioural health|behavioral health",
     "The Team view shows the crew's wellbeing together: a score per person and for the crew, with mood and sleep trends.",
     ["Click 👥 Team in the header.", "Cards are sorted with whoever needs support first; each lists what drives the score.",
      "Follow the team suggestions at the top."], [("open_team", "Open the Team view")]),
    (r"plan|schedule|countermeasure|workout|what should i do today",
     "Today's countermeasure plan turns your flags into a timed schedule for the day.",
     ["Scroll to 🗓 Today's countermeasure plan below the indicator cards.",
      "Blocks marked 'adjusted' changed because of a flag; the 'Why' line links to the indicator.",
      "Tick each block off as you do it."], [("open_plan", "Open today's plan")]),
    (r"symptom",
     "Log how you feel in the Symptom log. AURA triages it straight away with fixed rules.",
     ["Scroll to 🩺 Symptom log below the indicator cards.", "Pick your symptoms and rate each 1 to 10.",
      "Click Log and triage, then follow the actions. Red-flag symptoms mean contact the flight surgeon now."],
     [("open_symptoms", "Open the symptom log")]),
    (r"check.?in|log|enter|record|measure", "Log today's readings in the Daily check-in panel.",
     ["Go back to Live if you are replaying a past day.", "Type the values you measured.",
      "Click Log check-in. The status updates straight away."], [("open_checkin", "Open check-in")]),
    (r"ground|mission control|flight surgeon|message|delay|earth|signal|comms",
     "Use Message ground in the sidebar. It shows how long your message takes to reach Earth and when to expect a reply.",
     ["Find 📡 Message ground in the left sidebar.", "Type your message; tick Urgent if needed and keep Attach status on.",
      "Click Send. A countdown shows the signal travelling; the simulated flight-surgeon reply arrives after the round trip.",
      "While you wait, follow AURA's actions on the flagged indicators."], [("message_ground", "Message ground")]),
    (r"radiation|dose|msv|career limit|solar|sievert",
     "The Radiation dose budget panel shows how much of the 600 mSv career limit is used and how fast it's going.",
     ["Scroll to ☢ Radiation dose budget below the indicator cards.", "Check the % used, the dose rate and days left at this rate.",
      "Set a person's dose from earlier missions in ✎ Edit (☢ mSv before)."], [("open_radiation", "Show radiation budget")]),
    (r"tour|demo|judge|present", "The demo tour walks through AURA's story in 17 steps.",
     ["Click ▶ Demo tour in the header.", "Use Next → to move through the steps."], [("start_tour", "Start the tour")]),
    (r"real|nasa|osdr|inspiration|blood", "The Real crew data panel shows real NASA OSDR bloodwork from the Inspiration4 crew.",
     ["Scroll to Real crew data · Inspiration4.", "Switch panels and pick a marker.",
      "Choose a crew member and click Review for an AI summary."], [("open_research", "Show real data")]),
    (r"warning|critical|level|threshold|baseline|alert", "Critical means a predefined critical limit was crossed: contact the flight surgeon now. "
     "Warning means a warning limit was crossed, or your last 3 readings sit well away from your own preflight baseline.",
     ["Open a flagged indicator card to see the reason and the actions."], []),
]


RED_FLAG_RE = (r"chest (pain|pressure|tight)|can'?t breathe|short(ness)? of breath|difficulty breathing|"
               r"faint|pass(ed)? out|lost (my )?vision|vision loss|can'?t see|confus|slurred|seizure|"
               r"severe (pain|headache)|worst headache")


REMEMBER_RE = re.compile(r"^\s*(?:please\s+)?remember(?:\s+that)?\s*[:,]?\s*(.+)$", re.I | re.S)


def offline_reply(question: str, ctx: dict) -> AssistantReply:
    q = question.lower()
    if re.search(RED_FLAG_RE, q):
        return AssistantReply(
            answer="Contact the flight surgeon now. What you describe is a red-flag symptom, and it needs a "
                   "medical review straight away, whatever your readings show.",
            steps=["Stop what you're doing and stay secured; ask a crewmate to stay with you.",
                   "Take your vitals (heart rate, blood pressure, SpO2) if you can.",
                   "Log it in the Symptom log so the triage and your data go to ground.",
                   "Message ground as urgent."],
            actions=[AssistantAction(type="message_ground", label="Message ground"),
                     AssistantAction(type="open_symptoms", label="Log the symptom")],
            escalate=True, topic="health")
    m = REMEMBER_RE.match(question)
    if m and m.group(1).strip():
        note = m.group(1).strip().rstrip(".")[:200]
        return AssistantReply(answer=f"I can remember this: “{note}”. Click Save to memory to keep it; I'll use it in "
                                     "future answers.", steps=[],
                              actions=[AssistantAction(type="remember", label="Save to memory", target=note)],
                              escalate=False, topic="app_help")
    d = re.search(r"\b(?:go to|show(?: me)?|replay|jump to|open) day (\d{1,3})\b", q)
    if d and 1 <= int(d.group(1)) <= ctx["mission_day"]:
        return AssistantReply(answer=f"Here's day {d.group(1)} in mission replay.", steps=[],
                              actions=[AssistantAction(type="go_to_day", label=f"Go to day {d.group(1)}",
                                                       target=d.group(1))], escalate=False, topic="app_help")
    person = ctx.get("person")
    escalate = bool(person and person.get("escalate"))
    for pattern, answer, steps, actions in FAQ:
        if re.search(pattern, q):
            return AssistantReply(answer=answer, steps=steps,
                                  actions=[AssistantAction(type=t, label=lbl) for t, lbl in actions],
                                  escalate=False, topic="app_help")
    if person:
        order = {Level.CRITICAL.label: 0, Level.WARNING.label: 1}
        flagged = sorted((i for i in person["indicators"] if i["level"] in order), key=lambda i: order[i["level"]])
        name = person["astronaut"]["name"]
        if flagged:
            top = flagged[0]
            answer = (f"{name} is {person['overall_level']} today. {len(flagged)} indicator(s) flagged; most urgent: "
                      f"{top['name']} ({top['level']}). {top['reasons'][0] if top['reasons'] else ''}")
            return AssistantReply(
                answer=("Critical reading: follow the actions and contact the flight surgeon now. " if escalate else "") + answer,
                steps=top["rule_actions"][:3],
                actions=[AssistantAction(type="open_indicator", label=f"Open {i['name']}"[:40], target=i["key"]) for i in flagged[:2]],
                escalate=escalate, topic="health")
        return AssistantReply(answer=f"{name}'s indicators are all within their personal baseline. Keep up the daily routine.",
                              steps=[], actions=[AssistantAction(type="open_briefing", label="Daily briefing")],
                              escalate=False, topic="health")
    return AssistantReply(answer="I can help with crew health, using AURA, and the real NASA data. Select a crew member to start.",
                          steps=[], actions=[AssistantAction(type="start_tour", label="Start the tour")],
                          escalate=False, topic="app_help")


# --------------------------------------------------------------------------- AI
def ask_assistant(store: MissionStore, question: str, history: list[ChatTurn], crew_id: str | None = None,
                  day: int | None = None, indicator: str | None = None) -> dict:
    ctx = build_assistant_context(store, crew_id, day, indicator)
    status = ai_status()
    if not status["enabled"]:
        return {"mode": "offline", "model": None, "reply": _clean(offline_reply(question, ctx), ctx).model_dump(),
                "note": "Rule-based answers (no Claude login)."}
    messages = [{"role": t.role, "content": t.content} for t in history[-10:]]
    messages.append({"role": "user", "content": "<aura_context>\n" + json.dumps(ctx, separators=(",", ":"))
                     + "\n</aura_context>\n\nQuestion: " + question})
    try:
        response = _client().beta.messages.parse(
            model=status["model"],
            max_tokens=8000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "low"},
            system=[{"type": "text", "text": ASSISTANT_PROMPT + "\n" + APP_GUIDE,
                     "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_format=AssistantReply,
        )
        if _refused(response) or response.parsed_output is None:
            reply = AssistantReply(answer="I can't help with that one. For medical concerns, contact the flight surgeon.",
                                   steps=[], actions=[], escalate=False, topic="off_topic")
        else:
            reply = response.parsed_output
        return {"mode": "ai", "model": response.model, "reply": _clean(reply, ctx).model_dump(), "note": None}
    except Exception as exc:  # noqa: BLE001
        log.warning("Assistant failed: %s", _describe(exc))
        return {"mode": "offline", "model": None, "reply": _clean(offline_reply(question, ctx), ctx).model_dump(),
                "note": f"AI unavailable ({_describe(exc)}). Rule-based answer."}
