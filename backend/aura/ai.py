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
reasons for it, the 7-day trend, recent readings, an alert history and any notes they logged.

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
    title: str = Field(description="Short headline, e.g. 'Sleep debt is building'")
    detail: str = Field(description="1-2 sentences: what the data shows and why it matters")
    action: str = Field(description="One concrete thing to do today")
    indicators: list[str] = Field(description="Indicator keys this priority is about")


class Briefing(BaseModel):
    headline: str = Field(description="One-sentence overall assessment")
    escalate: bool = Field(description="True if the astronaut should contact the flight surgeon now")
    priorities: list[BriefingPriority] = Field(description="Up to 3, most important first")
    patterns: list[str] = Field(description="Cross-indicator patterns or trends worth knowing (0-3)")
    encouragement: str = Field(description="One short, genuine line of encouragement")


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
            "data": "synthetic demo telemetry",
        },
        "astronaut": {"name": member.name, "role": member.role, "age": member.age},
        "overall_level": status["overall"],
        "escalate": status["escalate"],
        "indicators": indicators,
        "alert_history": [e for e in store.alert_timeline(crew_id) if e["day"] <= day][-12:],
        "notes": [n for n in store.notes.get(crew_id, []) if n["day"] <= day][-5:],
    }


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
        patterns=[],
        encouragement="Steady routines win long missions. Keep logging your check-ins.",
    )


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
                "content": "Write today's health briefing for this astronaut.\n\n<astronaut_data>\n"
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
        log.warning("AI briefing failed: %s", exc)
        return {"mode": "offline", "model": None, "briefing": offline_briefing(ctx).model_dump(),
                "note": f"AI unavailable ({type(exc).__name__}). Showing the rule-based briefing."}


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
        log.warning("AI ask failed: %s", exc)
        return {"mode": "offline", "model": None,
                "answer": f"The AI assistant is unavailable right now ({type(exc).__name__}). "
                          "Use the indicator guidance, and contact the flight surgeon if anything is critical."}
