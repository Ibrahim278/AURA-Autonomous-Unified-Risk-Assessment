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

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, Field

from . import __version__, ai, assistant, comms, custom, radiation, symptoms, ground, forecast, gamification, importer, research
from .indicators import INDICATORS, Hazard
from .simulator import (DEFAULT_CREW_SPECS, DEFAULTS, EDITABLE_BASELINES, ENVIRONMENTS, SCENARIOS,
                        generate, imported_records, make_member)
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

custom.load_saved()
store = MissionStore.from_config(**_config())
outbox = comms.Outbox()


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


class CrewSpec(BaseModel):
    id: str | None = Field(None, pattern=r"^[a-z0-9-]{1,32}$", description="Keep to edit; omit to add")
    name: str = Field(..., min_length=1, max_length=60)
    role: str = Field("Mission Specialist", min_length=1, max_length=40)
    age: int = Field(40, ge=18, le=80)
    scenario: str = Field("nominal", description=f"One of {sorted(SCENARIOS)}")
    baseline: dict[str, float] = Field(default_factory=dict,
                                       description=f"Optional personal means for {list(EDITABLE_BASELINES)}")
    prior_dose_mSv: float = Field(0, ge=0, le=2000, description="Career radiation dose from earlier missions")


class CrewUpdate(BaseModel):
    crew: list[CrewSpec] = Field(..., min_length=1, max_length=6)


class CrewImport(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    role: str = Field("Mission Specialist", min_length=1, max_length=40)
    age: int = Field(40, ge=18, le=80)
    csv: str = Field(..., min_length=1, max_length=2_000_000, description="CSV text (see /api/crew/import/template)")


class SymptomItem(BaseModel):
    key: str = Field(..., description="Symptom key from /api/symptoms/catalog")
    severity: int = Field(..., ge=1, le=10)


class SymptomLog(BaseModel):
    symptoms: list[SymptomItem] = Field(..., min_length=1, max_length=17)
    note: str | None = Field(None, max_length=1000)
    day: int | None = Field(None, ge=1)


class GroundMessage(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    priority: Literal["routine", "urgent"] = "routine"
    attach_status: bool = Field(True, description="Attach today's AURA status packet")


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
    store.load(generate(days=req.days, environment=req.environment, seed=req.seed,
                        crew=list(store.dataset.crew)))
    outbox.clear()
    return mission()


@app.post("/api/mission/next-day", tags=["mission"])
def next_day():
    """Advance the mission by one day (max 365). Synthetic crew get new readings; log yours with a check-in."""
    if store.current_day >= 365:
        raise HTTPException(422, "The mission can't run past day 365. Reset it from the header.")
    store.advance_day()
    return mission()


@app.get("/api/crew-options", tags=["mission"])
def crew_options():
    """Scenarios, editable baselines and the default demo crew, for the crew editor."""
    return {
        "scenarios": [{"key": k, "label": v["label"], "description": v["description"]}
                      for k, v in SCENARIOS.items()],
        "baselines": [{"key": k, "name": INDICATORS[k].name, "unit": INDICATORS[k].unit,
                       "default": DEFAULTS[k][0], "min": DEFAULTS[k][2], "max": DEFAULTS[k][3]}
                      for k in EDITABLE_BASELINES],
        "roles": ["Commander", "Pilot", "Flight Engineer", "Mission Specialist", "Payload Specialist",
                  "Flight Surgeon"],
        "default_crew": DEFAULT_CREW_SPECS,
    }


@app.put("/api/mission/crew", tags=["mission"])
def set_crew(body: CrewUpdate):
    """Replace the crew and regenerate the synthetic mission (discards manual check-ins).

    Each member's synthetic telemetry follows their personal baselines and chosen health
    scenario. The AI briefing reads the new crew's data automatically.
    """
    used = {c.id for c in body.crew if c.id}
    if len(used) != len([c for c in body.crew if c.id]):
        raise HTTPException(422, "crew ids must be unique")
    members, n = [], 1
    for spec in body.crew:
        cid = spec.id
        if not cid:
            while f"aura-{n}" in used:
                n += 1
            cid = f"aura-{n}"
            used.add(cid)
        old = store.crew.get(cid)
        try:
            if old is not None and old.imported is not None:
                # Imported members keep their uploaded data; only the profile changes.
                m = make_member(cid, spec.name.strip(), spec.role.strip(), spec.age, prior_dose_mSv=spec.prior_dose_mSv)
                m.scenario, m.scenario_description, m.imported = "imported", old.scenario_description, old.imported
            else:
                m = make_member(cid, spec.name.strip(), spec.role.strip(), spec.age, spec.scenario, spec.baseline,
                                spec.prior_dose_mSv)
        except ValueError as exc:
            raise HTTPException(422, f"{spec.name}: {exc}") from exc
        members.append(m)
    ds = store.dataset
    store.load(generate(days=ds.days, environment=ds.environment, seed=ds.seed, crew=members))
    return crew_list()


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


@app.get("/api/crew/{crew_id}/forecast", tags=["crew"])
def crew_forecast(crew_id: str, day: int | None = Query(None, ge=1)):
    """Early warning: indicators whose trend will cross a baseline edge or limit within 14 days."""
    _crew_or_404(crew_id)
    return forecast.forecast(store, crew_id, day)


@app.get("/api/crew/{crew_id}/radiation", tags=["crew"])
def crew_radiation(crew_id: str, day: int | None = Query(None, ge=1)):
    """Radiation dose budget: career (600 mSv), 30-day and 1-year use, rate and projection."""
    _crew_or_404(crew_id)
    return radiation.budget(store, crew_id, day)


@app.get("/api/symptoms/catalog", tags=["symptoms"])
def symptom_catalog():
    """Symptoms crew can log, grouped by body area. Red flags trigger a critical triage."""
    return symptoms.catalog()


@app.get("/api/crew/{crew_id}/symptoms", tags=["symptoms"])
def crew_symptoms(crew_id: str, day: int | None = Query(None, ge=1)):
    """Symptom log up to the day, with the rule-based triage for that day."""
    _crew_or_404(crew_id)
    return symptoms.report(store.symptoms[crew_id], day or store.current_day)


@app.post("/api/crew/{crew_id}/symptoms", tags=["symptoms"], status_code=201)
def log_symptoms(crew_id: str, body: SymptomLog):
    """Log symptoms (severity 1-10) and get the triage: self-care, follow-up or contact ground now."""
    _crew_or_404(crew_id)
    try:
        day = store.log_symptoms(crew_id, [x.model_dump() for x in body.symptoms], body.day, body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return symptoms.report(store.symptoms[crew_id], day)


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


# ---------------------------------------------------------------- ground comms
@app.get("/api/comms", tags=["comms"])
def comms_link(day: int | None = Query(None, ge=1)):
    """Signal delay to Earth for this environment and mission day."""
    return _link(day)


def _link(day: int | None = None) -> dict:
    return comms.link_status(store.dataset.environment, day or store.current_day, store.dataset.days)


@app.get("/api/crew/{crew_id}/messages", tags=["comms"])
def crew_messages(crew_id: str):
    """Messages to and from ground. Replies show as pending until their signal arrives."""
    _crew_or_404(crew_id)
    return {"link": _link(), "messages": outbox.thread(crew_id)}


@app.post("/api/crew/{crew_id}/messages", tags=["comms"], status_code=201)
def send_message(crew_id: str, body: GroundMessage):
    """Send a message to ground. It arrives after the one-way delay; a SIMULATED flight-surgeon
    reply comes back after the round trip (shortened by the demo clock)."""
    member = _crew_or_404(crew_id)
    status = store.status(crew_id)
    link = _link()
    outbox.send(crew_id, member.name, body.text, body.priority, store.current_day, link,
                status if body.attach_status else None)
    return {"link": link, "messages": outbox.thread(crew_id)}


# ---------------------------------------------------------------- ground view and reports
@app.get("/api/ground", tags=["ground"])
def ground_overview(day: int | None = Query(None, ge=1)):
    """Flight-surgeon view: every crew member, sorted by who needs attention first."""
    return ground.overview(store, outbox, day)


@app.get("/api/report", tags=["ground"], response_class=HTMLResponse)
def crew_report(day: int | None = Query(None, ge=1)):
    """Printable whole-crew health report (HTML; use the browser's Save as PDF)."""
    order = [r["crew_id"] for r in ground.overview(store, outbox, day)["crew"]]
    return ground.report_html(store, outbox, order, day)


@app.get("/api/crew/{crew_id}/report", tags=["ground"], response_class=HTMLResponse)
def member_report(crew_id: str, day: int | None = Query(None, ge=1)):
    """Printable health report for one crew member."""
    _crew_or_404(crew_id)
    return ground.report_html(store, outbox, [crew_id], day)


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


# ---------------------------------------------------------------- import your own data
@app.get("/api/crew/import/template", tags=["crew"], response_class=PlainTextResponse)
def import_template():
    """Example CSV (wide layout: one row per day; negative days are preflight)."""
    return PlainTextResponse(importer.template(), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="aura_import_template.csv"'})


@app.post("/api/crew/import", tags=["crew"], status_code=201)
def import_crew(body: CrewImport):
    """Add a crew member from your own CSV data. Other members and check-ins are kept."""
    if len(store.crew) >= 6:
        raise HTTPException(422, "The crew is full (6 members). Remove someone in the crew editor first.")
    try:
        readings, warnings = importer.parse_csv(body.csv, store.dataset.days)
    except importer.ImportError_ as exc:
        raise HTTPException(422, str(exc)) from exc
    n = 1
    while f"aura-{n}" in store.crew:
        n += 1
    member = make_member(f"aura-{n}", body.name.strip(), body.role.strip(), body.age)
    member.scenario = "imported"
    member.scenario_description = (f"Your own data: {len(readings)} readings imported from CSV "
                                   f"(days {min(d for _, d, _ in readings)} to {max(d for _, d, _ in readings)}).")
    member.imported = readings
    store.add_member(member, imported_records(member, date.fromisoformat(store.dataset.start_date)))
    status = store.status(member.id)
    return {"member": {**member.public(), "overall": status["overall"]}, "warnings": warnings,
            "readings": len(readings),
            "indicators": sorted({k for k, _, _ in readings}),
            "last_day": max(d for _, d, _ in readings)}


# ---------------------------------------------------------------- custom indicators
@app.get("/api/indicators/options", tags=["reference"])
def indicator_options():
    """Choices for the 'Add indicator' form."""
    from .indicators import BodySystem, Direction
    return {"body_systems": [b.value for b in BodySystem], "hazards": [h.value for h in Hazard],
            "directions": [d.value for d in Direction], "max_custom": custom.MAX_CUSTOM,
            "custom": {k: v.model_dump(mode="json") for k, v in custom.specs().items()}}


@app.post("/api/indicators", tags=["reference"], status_code=201)
def add_indicator(spec: custom.CustomIndicatorSpec):
    """Add (or redefine) a custom indicator. Synthetic crew get synthetic readings for it;
    imported members and check-ins can log it straight away."""
    try:
        ind = custom.register(spec)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    store.add_indicator(ind.key)
    return ind.to_dict()


@app.delete("/api/indicators/{key}", tags=["reference"])
def delete_indicator(key: str):
    """Remove a custom indicator and its readings. Built-in indicators can't be removed."""
    if key not in custom.specs():
        raise HTTPException(404 if key not in INDICATORS else 422,
                            f"'{key}' is not a custom indicator")
    store.remove_indicator(key)
    custom.unregister(key)
    return {"deleted": key}


# ---------------------------------------------------------------- Ask AURA (floating assistant)
class AssistantRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    history: list[assistant.ChatTurn] = Field(default_factory=list, max_length=20)
    crew_id: str | None = Field(None, description="Who the user is looking at")
    day: int | None = Field(None, ge=1)
    indicator: str | None = Field(None, description="Selected indicator, if any")


@app.post("/api/assistant", tags=["ai"])
def ask_assistant(body: AssistantRequest):
    """Answer any question with an answer, steps and one-click dashboard actions."""
    crew_id = body.crew_id if body.crew_id in store.crew else None
    return assistant.ask_assistant(store, body.question, body.history, crew_id, body.day, body.indicator)
