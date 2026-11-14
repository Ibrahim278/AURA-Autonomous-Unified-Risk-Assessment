"""AURA FastAPI application.

Run:  uvicorn aura.main:app --reload     (from the backend/ folder)
Docs: http://localhost:8000/docs

Configuration (environment variables):
    AURA_ENVIRONMENT  iss | lunar_surface | mars_transit   (default lunar_surface)
    AURA_DAYS         mission length in days                (default 60)
    AURA_SEED         random seed for synthetic telemetry   (default 42)
    AURA_CORS_ORIGINS comma-separated allowed origins       (default Vite dev server)
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import __version__, ai, gamification, research
from .indicators import INDICATORS, Hazard
from .simulator import ENVIRONMENTS, generate
from .store import MissionStore, UnknownCrewError


def _config() -> dict:
    return {
        "environment": os.getenv("AURA_ENVIRONMENT", "lunar_surface"),
        "days": int(os.getenv("AURA_DAYS", "60")),
        "seed": int(os.getenv("AURA_SEED", "42")),
    }


app = FastAPI(
    title="AURA: Autonomous Unified Risk Assessment",
    version=__version__,
    description=(
        "Astronaut health self-assessment API. Thresholds are prototype rules, not clinically "
        "validated flight-medicine limits. Telemetry is SYNTHETIC unless labelled otherwise."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "AURA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

store = MissionStore.from_config(**_config())


def _crew_or_404(crew_id: str):
    if crew_id not in store.crew:
        raise HTTPException(status_code=404, detail=f"Unknown crew member '{crew_id}'")
    return store.crew[crew_id]


# ---------------------------------------------------------------- schemas
class CheckIn(BaseModel):
    values: dict[str, float] = Field(
        ..., description="Indicator key -> value, e.g. {'heart_rate': 64, 'mood': 7}",
        examples=[{"heart_rate": 64, "sleep_hours": 6.5, "mood": 7}],
    )
    day: int | None = Field(None, ge=1, description="Mission day (defaults to the current day)")
    note: str | None = Field(None, max_length=1000, description="Optional free-text note")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    history: list[ai.ChatTurn] = Field(default_factory=list, max_length=20)
    day: int | None = Field(None, ge=1)


class BriefingRequest(BaseModel):
    day: int | None = Field(None, ge=1)


class ResetRequest(BaseModel):
    environment: str = Field("lunar_surface", description=f"One of {sorted(ENVIRONMENTS)}")
    days: int = Field(60, ge=10, le=365)
    seed: int = 42


# ---------------------------------------------------------------- routes
@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/mission", tags=["mission"])
def mission():
    return {**store.dataset.meta(), "current_day": store.current_day}


@app.get("/api/environments", tags=["mission"])
def environments():
    return ENVIRONMENTS


@app.post("/api/mission/reset", tags=["mission"])
def reset(req: ResetRequest):
    """Regenerate the synthetic mission (discards manual check-ins)."""
    if req.environment not in ENVIRONMENTS:
        raise HTTPException(422, f"environment must be one of {sorted(ENVIRONMENTS)}")
    store.load(generate(days=req.days, environment=req.environment, seed=req.seed))
    return mission()


@app.get("/api/indicators", tags=["reference"])
def indicators():
    return [ind.to_dict() for ind in INDICATORS.values()]


@app.get("/api/hazards", tags=["reference"])
def hazards():
    return {
        h.value: [k for k, ind in INDICATORS.items() if h in ind.hazards] for h in Hazard
    }


@app.get("/api/crew", tags=["crew"])
def crew_list():
    out = []
    for c in store.crew.values():
        s = store.status(c.id)
        out.append({**c.public(), "overall": s["overall"], "counts": s["counts"],
                    "escalate": s["escalate"]})
    return out


@app.get("/api/crew/{crew_id}", tags=["crew"])
def crew_detail(crew_id: str):
    return _crew_or_404(crew_id).public()


@app.get("/api/crew/{crew_id}/status", tags=["crew"])
def crew_status(crew_id: str, day: int | None = Query(None, ge=1)):
    """Current assessment for every indicator, the overall level and the body-system rollup."""
    _crew_or_404(crew_id)
    return store.status(crew_id, day)


@app.get("/api/crew/{crew_id}/telemetry", tags=["crew"])
def crew_telemetry(
    crew_id: str,
    indicators: str | None = Query(None, description="Comma-separated keys (default: all)"),
    from_day: int | None = None,
    to_day: int | None = None,
):
    """Time series for charts, plus each indicator's personal baseline band."""
    _crew_or_404(crew_id)
    keys = indicators.split(",") if indicators else list(INDICATORS)
    bad = [k for k in keys if k not in INDICATORS]
    if bad:
        raise HTTPException(422, f"Unknown indicators: {bad}")
    series = {}
    for key in keys:
        ind = INDICATORS[key]
        base = store.baseline(crew_id, key)
        rs = [
            r for r in store.readings(crew_id, key)
            if (from_day is None or r.day >= from_day) and (to_day is None or r.day <= to_day)
        ]
        series[key] = {
            "name": ind.name,
            "unit": ind.unit,
            "limits": ind.limits.__dict__,
            "baseline": None if base is None or not ind.use_baseline
            else {"mean": round(base.mean, 2), "sd": round(base.sd, 2)},
            "preflight": store.preflight(crew_id, key),
            "points": [{"day": r.day, "value": r.value, "source": r.source} for r in rs],
        }
    return {"crew_id": crew_id, "series": series}


@app.get("/api/crew/{crew_id}/alerts", tags=["crew"])
def crew_alerts(crew_id: str, from_day: int = 1):
    """Feed of alert-level changes over the mission."""
    _crew_or_404(crew_id)
    return store.alert_timeline(crew_id, from_day)


@app.post("/api/crew/{crew_id}/checkins", tags=["crew"], status_code=201)
def crew_checkin(crew_id: str, body: CheckIn):
    """Record manual measurements (keyboard entry) and return the updated status."""
    _crew_or_404(crew_id)
    try:
        day = store.add_checkin(crew_id, body.values, body.day, body.note)
    except (ValueError, UnknownCrewError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return store.status(crew_id, day)


# ---------------------------------------------------------------- AI flight surgeon
@app.get("/api/ai/status", tags=["ai"])
def ai_status():
    """Whether the Claude-powered assistant is enabled (ANTHROPIC_API_KEY set)."""
    return ai.ai_status()


@app.post("/api/crew/{crew_id}/briefing", tags=["ai"])
def crew_briefing(crew_id: str, body: BriefingRequest | None = None):
    """Daily health briefing. Uses Claude when available, else a rule-based briefing."""
    _crew_or_404(crew_id)
    return ai.generate_briefing(store, crew_id, body.day if body else None)


@app.post("/api/crew/{crew_id}/ask", tags=["ai"])
def crew_ask(crew_id: str, body: AskRequest):
    """Ask the AI flight surgeon a question about this astronaut's data."""
    _crew_or_404(crew_id)
    return ai.ask(store, crew_id, body.question, body.history, body.day)


# ---------------------------------------------------------------- mission routine / gamification
@app.get("/api/crew/{crew_id}/tasks", tags=["routine"])
def crew_tasks(crew_id: str):
    """Today's mission health tasks, streaks, points, level and badges."""
    _crew_or_404(crew_id)
    return gamification.mission_tasks(store, crew_id)


@app.post("/api/crew/{crew_id}/tasks/{task_id}/complete", tags=["routine"])
def complete_task(crew_id: str, task_id: str):
    """Tick off a wellness task. Measurement tasks complete themselves via check-ins."""
    _crew_or_404(crew_id)
    try:
        gamification.complete_wellness(store, crew_id, task_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return gamification.mission_tasks(store, crew_id)


# ---------------------------------------------------------------- real research data (NASA OSDR)
@app.get("/api/research", tags=["research"])
def research_datasets():
    """Real Inspiration4 crew lab datasets from NASA OSDR and whether each file is loaded."""
    return research.available()


@app.post("/api/research/crew/{crew}/review", tags=["research", "ai"])
def research_crew_review(crew: str):
    """AI (or rule-based) review of one Inspiration4 crew member's real bloodwork."""
    profile = research.crew_profile(crew.upper())
    if profile is None:
        raise HTTPException(404, f"No research data for crew '{crew}'")
    return ai.research_review(profile)


@app.get("/api/research/{dataset}", tags=["research"])
def research_dataset(dataset: str):
    """One dataset (cmp or cbc): every analyte per crew member and timepoint, with lab ranges."""
    if dataset not in research.DATASETS:
        raise HTTPException(404, f"Unknown dataset '{dataset}'. Use one of {sorted(research.DATASETS)}")
    data = research.load(dataset)
    if data is None:
        raise HTTPException(404, f"{research.DATASETS[dataset]['file']} is not in data/osdr/")
    return data
