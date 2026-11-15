"""AI flight-surgeon assistant (Claude API).

Two features:
  * Daily health briefing: a structured summary of one astronaut's status.
  * Ask the flight surgeon: free-text Q&A grounded in the astronaut's data.

Safety design:
  * The rule-based alert engine (alerts.py) is the source of truth for every
    Normal / Warning / Critical level. The AI explains and coaches; it never
    sets or overrides a level, and it is told to escalate whenever a level is critical.
  * Without an API key (or if the API call fails), AURA falls back to a deterministic
    offline briefing, so the app always works in a demo.

Credentials (any one enables the AI features):
    ANTHROPIC_API_KEY  in the environment or backend/.env
    `ant auth login`   the Anthropic CLI profile is picked up automatically
Configuration:
    AURA_AI_MODEL      default claude-opus-5-5
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .indicators import INDICATORS
from .store import MissionStore

log = logging.getLogger("aura.ai")

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _load_dotenv() -> None:
    """Minimal .env loader (KEY=VALUE lines) so no extra dependency is needed."""
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if value and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

SYSTEM_PROMPT = """\
You are AURA's flight-surgeon assistant, built into a health-monitoring tool that astronauts \
use on long-duration missions (space station, lunar base or Mars transit) to assess their own \
health between contacts with the medical team on the ground.

Who you are talking to: the astronaut, a highly trained professional who is not a doctor. \
Use plain, calm, direct language. Explain medical terms briefly the first time you use them.

What you receive: a JSON snapshot of one astronaut's data. It holds each indicator's latest \
value, their personal preflight baseline, the alert level (normal, warning or critical) and the \
reasons for it, the 7-day trend, recent readings, an alert history, any notes they logged, and a \
"forecast": straight-line trend projections of indicators that would cross their baseline edge or a \
limit within two weeks if nothing changes. Use the forecast to suggest prevention, and call it a trend, \
not a prediction. "radiation_budget" is the long-term dose picture against NASA's 600 mSv career limit and \
the 30-day limit; mention it when its level is not normal. "symptoms" is what the astronaut reported \
feeling, with AURA's rule-based triage; connect symptoms to the matching indicators (for example chills \
with body temperature) and never diagnose.

Rules:
1. The alert levels come from AURA's rule engine and are authoritative. Never upgrade, downgrade \
or contradict a level. Your job is to explain levels, connect related indicators, and coach.
2. If any indicator is critical, the first thing you say is that they must follow the critical \
actions and contact the flight surgeon on the ground now.
3. Look for patterns across indicators and over time. For example, poor sleep followed by falling \
mood and a rising resting heart rate, or a fever with a raised heart rate. Link them to the \
spaceflight hazards (radiation, isolation and confinement, distance from Earth, altered \
gravity, hostile closed environment) when that helps.
4. Give specific, practical actions that are doable on a spacecraft or habitat: hydration, \
sleep hygiene, exercise countermeasures, re-measuring, talking to crewmates, or scheduling a \
private medical conference. Never prescribe or dose medication. Defer anything diagnostic to \
the ground team.
5. Ground every claim in the data you were given. If the data can't answer a question, say so \
and suggest a measurement that would help.
6. The telemetry in this demo is synthetic and the thresholds are prototype rules. Don't claim \
clinical certainty.
7. Be brief. Astronauts read this between tasks.
"""


class BriefingPriority(BaseModel):
    title: str = Field(description="Headline of at most 6 words, e.g. 'Sleep debt is building'")
    detail: str = Field(
        description="ONE sentence, at most 25 words: the key number vs baseline and why it matters"
    )
    action: str = Field(
        description="ONE action to do today, at most 15 words, starting with a verb. No lists."
    )
    indicators: list[str] = Field(description="Indicator keys this priority is about")


class Briefing(BaseModel):
    headline: str = Field(description="One sentence, at most 20 words")
    escalate: bool = Field(description="True if the astronaut should contact the flight surgeon now")
    priorities: list[BriefingPriority] = Field(description="At most 3, most important first")
    patterns: list[str] = Field(
        description="0-2 cross-indicator patterns, each one sentence of at most 25 words"
    )
    encouragement: str = Field(description="One genuine line, at most 12 words")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


def _credential_source() -> str | None:
    """Which Claude credentials the SDK will use, or None if there are none.

    Matches the SDK's own lookup order: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, then an
    `ant auth login` profile stored under ~/.config/anthropic/.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        return "api_key"
    if os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return "auth_token"
    try:
        from anthropic.lib.credentials import default_credentials

        return "ant_profile" if default_credentials() is not None else None
    except Exception:  # noqa: BLE001 - SDK missing or a broken profile: treat as no credentials
        return None


def ai_status() -> dict:
    source = _credential_source()
    return {
        "enabled": source is not None,
        "credentials": source,
        "model": os.getenv("AURA_AI_MODEL", DEFAULT_MODEL),
    }


def _client():
    import anthropic  # imported lazily so the app runs even if the SDK is missing

    return anthropic.Anthropic()


def build_context(store: MissionStore, crew_id: str, day: int | None = None) -> dict:
    """Compact, deterministic JSON snapshot of one astronaut for the model."""
    day = store.current_day if day is None else day
    status = store.status(crew_id, day)
    member = store.crew[crew_id]
    indicators = []
    for a in status["indicators"]:
        recent = [
            {"day": r.day, "value": r.value, "source": r.source}
            for r in store.readings(crew_id, a["indicator"], day)[-7:]
        ]
        indicators.append(
            {
                "key": a["indicator"],
                "name": a["name"],
                "unit": a["unit"],
                "level": a["level"],
                "latest": a["value"],
                "baseline_mean": a["baseline"]["mean"] if a["baseline"] else None,
                "trend_7d": a["trend"],
                "reasons": a["reasons"],
                "rule_actions": a["actions"],
                "recent": recent,
                "hazards": [h.value for h in INDICATORS[a["indicator"]].hazards],
            }
        )
    return {
        "mission": {
            "environment": store.dataset.environment_info["name"],
            "day": day,
            "data": ("readings imported by the user from their own CSV (real or self-recorded)"
                     if member.imported is not None else "synthetic demo telemetry"),
        },
        "astronaut": {"name": member.name, "role": member.role, "age": member.age},
        "overall_level": status["overall"],
        "escalate": status["escalate"],
        "indicators": indicators,
        "alert_history": [e for e in store.alert_timeline(crew_id) if e["day"] <= day][-12:],
        "forecast": _forecast_summary(store, crew_id, day),
        "radiation_budget": _radiation_summary(store, crew_id, day),
        "symptoms": _symptom_summary(store, crew_id, day),
        "notes": [n for n in store.notes.get(crew_id, []) if n["day"] <= day][-5:],
    }


def _symptom_summary(store: MissionStore, crew_id: str, day: int) -> dict:
    from .symptoms import report

    r = report(store.symptoms[crew_id], day)
    recent = [{"day": e["day"], "symptoms": [f'{x["name"]} {x["severity"]}/10' for x in e["symptoms"]],
               "note": e["note"]} for e in r["log"] if e["day"] > day - 7]
    return {"today_triage": {k: r["triage"][k] for k in ("level", "reasons")}, "last_7_days": recent}


def _radiation_summary(store: MissionStore, crew_id: str, day: int) -> dict:
    from .radiation import budget

    b = budget(store, crew_id, day)
    keys = ("level", "reasons", "career_mSv", "career_used_pct", "rate_mSv_day", "days_to_limit",
            "projected_end_mSv", "window_30d_mSv")
    return {k: b[k] for k in keys}


def _forecast_summary(store: MissionStore, crew_id: str, day: int) -> list[dict]:
    """Trend projections (straight-line, not clinical predictions) for the model."""
    from .forecast import forecast  # local import: forecast imports store, which ai also uses

    return [{"indicator": r["indicator"], "trend_per_day": r["slope_per_day"],
             "would_reach": f"{r['crossing']['label']} ({r['crossing']['level']}) in ~{r['crossing']['in_days']} days"}
            for r in forecast(store, crew_id, day)["risks"][:5]]


# --------------------------------------------------------------------------- offline
def offline_briefing(ctx: dict) -> Briefing:
    """Deterministic briefing used when the AI is unavailable."""
    order = {"critical": 0, "warning": 1}
    flagged = sorted(
        (i for i in ctx["indicators"] if i["level"] in order),
        key=lambda i: order[i["level"]],
    )
    priorities = [
        BriefingPriority(
            title=f"{i['name']}: {i['level']}",
            detail=i["reasons"][0] if i["reasons"] else "",
            action=i["rule_actions"][0] if i["rule_actions"] else "Re-measure and keep monitoring.",
            indicators=[i["key"]],
        )
        for i in flagged[:3]
    ]
    n = len(flagged)
    if ctx["escalate"]:
        headline = "Critical reading detected. Follow the actions and contact the flight surgeon now."
    elif n:
        headline = f"{n} indicator{'s' if n > 1 else ''} need{'s' if n == 1 else ''} attention today."
    else:
        headline = "All indicators are within your personal baseline."
    return Briefing(
        headline=headline,
        escalate=ctx["escalate"],
        priorities=priorities,
        patterns=[f"Trend watch: {next(i['name'] for i in ctx['indicators'] if i['key'] == f['indicator'])} "
                  f"would reach the {f['would_reach']} if nothing changes."
                  for f in ctx.get("forecast", [])[:2]],
        encouragement="Steady routines win long missions. Keep logging your check-ins.",
    )


def _describe(exc: Exception) -> str:
    """Short, user-facing reason for an AI failure (the API's own message when there is one)."""
    msg = getattr(exc, "message", None) or str(exc)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        msg = (body.get("error") or {}).get("message") or msg
    msg = " ".join(str(msg).split())
    return f"{type(exc).__name__}: {msg[:300]}"


def _refused(response) -> bool:
    return getattr(response, "stop_reason", None) == "refusal"


# --------------------------------------------------------------------------- AI calls
def generate_briefing(store: MissionStore, crew_id: str, day: int | None = None) -> dict:
    ctx = build_context(store, crew_id, day)
    status = ai_status()
    if not status["enabled"]:
        return {"mode": "offline", "model": None, "briefing": offline_briefing(ctx).model_dump(),
                "note": "AI is off (no Claude credentials found). Showing the rule-based briefing."}
    try:
        response = _client().beta.messages.parse(
            model=status["model"],
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": "Write today's health briefing for this astronaut. It is read in under 30 seconds "
                "between tasks, so keep every field to its word limit, give exactly one action per "
                "priority, and leave detailed reasoning for follow-up questions in chat."
                "\n\n<astronaut_data>\n"
                + json.dumps(ctx, separators=(",", ":"))
                + "\n</astronaut_data>",
            }],
            output_format=Briefing,
        )
        if _refused(response) or response.parsed_output is None:
            raise RuntimeError(f"no briefing returned (stop_reason={response.stop_reason})")
        briefing = response.parsed_output
        # The rule engine is authoritative: never let the model hide an escalation.
        briefing.escalate = briefing.escalate or ctx["escalate"]
        return {"mode": "ai", "model": response.model, "briefing": briefing.model_dump(), "note": None}
    except Exception as exc:  # noqa: BLE001 - any failure falls back to the offline briefing
        log.warning("AI briefing failed: %s", _describe(exc))
        return {"mode": "offline", "model": None, "briefing": offline_briefing(ctx).model_dump(),
                "note": f"AI unavailable ({_describe(exc)}). Showing the rule-based briefing."}


def ask(store: MissionStore, crew_id: str, question: str, history: list[ChatTurn],
        day: int | None = None) -> dict:
    ctx = build_context(store, crew_id, day)
    status = ai_status()
    if not status["enabled"]:
        return {"mode": "offline", "model": None, "answer": (
            "The AI assistant is off because no Claude credentials were found (set ANTHROPIC_API_KEY "
            "or run `ant auth login`). In the meantime, open "
            "any indicator card for its explanation and recommended actions"
            + (". Critical readings: contact the flight surgeon now." if ctx["escalate"] else ".")
        )}
    messages = [{"role": t.role, "content": t.content} for t in history[-10:]]
    messages.append({
        "role": "user",
        "content": "<astronaut_data>\n" + json.dumps(ctx, separators=(",", ":"))
        + "\n</astronaut_data>\n\nQuestion: " + question,
    })
    try:
        response = _client().beta.messages.create(
            model=status["model"],
            max_tokens=4000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "low"},
            system=[{"type": "text", "text": SYSTEM_PROMPT
                     + "\nAnswer in at most about 120 words. Use short paragraphs or a short list.",
                     "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        if _refused(response):
            return {"mode": "ai", "model": response.model, "answer": (
                "I can't help with that one. For medical questions outside this data, please "
                "contact the flight surgeon.")}
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return {"mode": "ai", "model": response.model, "answer": text}
    except Exception as exc:  # noqa: BLE001
        log.warning("AI ask failed: %s", _describe(exc))
        return {"mode": "offline", "model": None,
                "answer": f"The AI assistant is unavailable right now ({_describe(exc)}). "
                          "Use the indicator guidance, and contact the flight surgeon if anything is critical."}


# --------------------------------------------------------------------------- real crew data review
RESEARCH_PROMPT = """\
You are AURA's flight-surgeon assistant, reviewing REAL, de-identified clinical lab data from \
one of the four Inspiration4 crew (a 3-day orbital flight in September 2021), published by NASA's \
Open Science Data Repository. The reader is a mission medical team or a judge evaluating AURA.

What you receive: JSON with each blood marker's personal preflight mean (the mean of L-92, L-44 \
and L-3), the value 1 day after return (R+1) and its change from preflight, the latest value, the \
lab's reference range, any out-of-range timepoints, and samples excluded by AURA's quality check.

Rules:
1. Compare the astronaut to their OWN preflight baseline first, then to the lab range. A big \
change inside the range can matter more than a small excursion outside it.
2. Link changes to known spaceflight effects only where it fits: fluid shift and plasma volume \
loss, red cell loss ("space anaemia"), launch and landing stress on white cells, bone calcium \
release, reduced activity and glucose, re-adaptation to gravity. Say "consistent with", never \
"caused by"; three days in orbit is short and there is no control group here.
3. A single odd value at one timepoint, especially if every other crew member shows the same \
jump, may be sample handling or lab variation. Say so instead of building a story on it.
4. Recommendations are what AURA would have this astronaut monitor or do around a future \
flight (measurements to add, countermeasures, follow-up timing). Never diagnose, prescribe or \
dose medication; defer clinical decisions to a physician.
5. Use only the data given. Be brief and concrete, with numbers and units.
"""


class ResearchFinding(BaseModel):
    marker: str = Field(description="Marker name as given, e.g. 'Glucose'")
    observation: str = Field(description="ONE sentence, at most 25 words, with numbers and units vs preflight")
    interpretation: str = Field(description="ONE sentence, at most 25 words, hedged ('consistent with...')")
    concern: Literal["low", "moderate", "high"] = Field(description="How much attention it deserves")


class ResearchRecommendation(BaseModel):
    action: str = Field(description="At most 15 words, starting with a verb")
    rationale: str = Field(description="ONE sentence, at most 20 words")


class ResearchReview(BaseModel):
    headline: str = Field(description="One sentence, at most 25 words: the overall picture")
    findings: list[ResearchFinding] = Field(description="2-4 findings, most important first")
    recommendations: list[ResearchRecommendation] = Field(description="2-3 recommendations")
    data_caveats: list[str] = Field(description="0-2 short caveats about the data itself")


def offline_research_review(profile: dict) -> ResearchReview:
    """Deterministic review: largest return-day shifts and out-of-range markers."""
    ms = [m for m in profile["markers"] if m["change_at_return_pct"] is not None]
    ms.sort(key=lambda m: -abs(m["change_at_return_pct"]))
    findings = []
    for m in ms[:3]:
        pct = m["change_at_return_pct"]
        oor = ", ".join(f"{o['timepoint']} ({o['flag']})" for o in m["out_of_range"]) or "none"
        findings.append(ResearchFinding(
            marker=m["name"],
            observation=f"{m['preflight_mean']:g} → {m['return_day_1']:g} {m['unit']} the day after return "
                        f"({pct:+.0f}% vs preflight).",
            interpretation=f"Out-of-range timepoints: {oor}. Rule-based summary; enable Claude for interpretation.",
            concern="moderate" if m["out_of_range"] or abs(pct) >= 30 else "low"))
    return ResearchReview(
        headline=f"Largest return-day shifts for {profile['crew']} are listed below versus their own preflight mean.",
        findings=findings,
        recommendations=[
            ResearchRecommendation(action="Repeat bloodwork within a week of return",
                                   rationale="Separates real flight effects from one-off sample variation."),
            ResearchRecommendation(action="Track these markers in AURA's daily check-in on future flights",
                                   rationale="A personal baseline makes small shifts visible early."),
        ],
        data_caveats=[q["reason"] for q in profile.get("excluded_samples", [])][:1],
    )


def research_review(profile: dict) -> dict:
    status = ai_status()
    if not status["enabled"]:
        return {"mode": "offline", "model": None, "review": offline_research_review(profile).model_dump(),
                "note": "AI is off (no Claude credentials found). Showing the rule-based summary."}
    try:
        response = _client().beta.messages.parse(
            model=status["model"],
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=[{"type": "text", "text": RESEARCH_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": "Review this crew member's bloodwork across the flight. Keep every field to its "
                "word limit.\n\n<crew_lab_data>\n" + json.dumps(profile, separators=(",", ":"))
                + "\n</crew_lab_data>",
            }],
            output_format=ResearchReview,
        )
        if _refused(response) or response.parsed_output is None:
            raise RuntimeError(f"no review returned (stop_reason={response.stop_reason})")
        return {"mode": "ai", "model": response.model, "review": response.parsed_output.model_dump(), "note": None}
    except Exception as exc:  # noqa: BLE001
        log.warning("AI research review failed: %s", _describe(exc))
        return {"mode": "offline", "model": None, "review": offline_research_review(profile).model_dump(),
                "note": f"AI unavailable ({_describe(exc)}). Showing the rule-based summary."}
