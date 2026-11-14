# AURA: Autonomous Unified Risk Assessment

Health-monitoring software that lets astronauts on long-duration missions assess their own
health, see trends at a glance, and know when to act or escalate to flight surgeons.

Built for the **NASA Space Apps Challenge 2026**, "Create Health Monitoring Software for
Astronauts on Space Missions".

> **Prototype disclaimer:** AURA is a hackathon prototype. Its alert thresholds are
> *prototype rules* drawn from published research, **not clinically validated flight-medicine
> limits**. Telemetry shown in the demo is **synthetic** unless explicitly labelled otherwise.

## How it works

1. **Indicators:** heart rate, blood pressure, blood glucose, body temperature, sleep,
   mood/stress, SpO2 and radiation dose. Each one is mapped to NASA's five hazards of
   human spaceflight.
2. **Personal baselines:** each astronaut's readings are compared with *their own* pre-flight
   or early-mission baseline, not only Earth-based clinical ranges. A sustained deviation can
   raise a warning even when the reading is still "normal" on Earth.
3. **Three transparent alert levels:**
   - 🟢 **Normal:** no significant deviation from baseline.
   - 🟡 **Warning:** a sustained or unusual change that deserves attention.
   - 🔴 **Critical:** a predefined high-risk condition that needs immediate review and
     escalation to the ground.
4. **Guidance:** every alert explains *why* it fired, what the astronaut can do, and when to
   contact the flight surgeon.

## Project layout

```
backend/    Python (FastAPI) API, alert engine, synthetic telemetry generator
frontend/   React (Vite) dashboard
docs/       Data sources, provenance and threshold references
```

## Run the back end

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn aura.main:app --reload
```

Then open http://localhost:8000/docs for the interactive API.

Run the tests with `pytest` from the `backend/` folder.

To pick a different mission environment, set `AURA_ENVIRONMENT=iss|lunar_surface|mars_transit`
before starting the server (or call `POST /api/mission/reset`).

### API overview

| Method | Path | What it returns |
| --- | --- | --- |
| GET | `/api/mission` | Mission info, current day, environment, data notice |
| GET | `/api/indicators` | Indicator catalog: limits, explanations, how to measure, actions, references |
| GET | `/api/hazards` | NASA's five hazards mapped to the indicators |
| GET | `/api/crew` | Crew list with overall status (normal / warning / critical) |
| GET | `/api/crew/{id}/status?day=` | Per-indicator assessment, reasons, actions and body-system rollup |
| GET | `/api/crew/{id}/telemetry` | Time series with preflight baseline and limits, for charts |
| GET | `/api/crew/{id}/alerts` | Timeline of alert-level changes |
| POST | `/api/crew/{id}/checkins` | Manual measurement entry; returns the updated status |
| POST | `/api/mission/reset` | Regenerate the synthetic mission (environment, days, seed) |

### Demo crew (synthetic)

| ID | Crew member | Scenario |
| --- | --- | --- |
| `aura-1` | Cmdr. Lena Ortiz | Nominal. Only expected in-flight changes. |
| `aura-2` | Dr. Kenji Sato | Sleep declines (day 42 warning), then mood, exercise and resting HR (71 bpm: Earth-normal, but well above his baseline), then blood pressure. |
| `aura-3` | Amara Diallo | Fever from viral reactivation, critical on day 60. |

All three receive a solar particle event dose on day 22 (lunar surface / Mars transit).

Regenerate the CSV/JSON export in `data/` with
`python -m aura.simulator --out ../data` (from `backend/`).

![AURA dashboard](docs/screenshots/dashboard.png)

## Run the front end

In a second terminal (needs Node 20+), with the back end already running on port 8000:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the back end.

**Dashboard features**

- Crew list with each astronaut's overall status (color plus icon, so it doesn't rely on color alone).
- Clickable body figure: each region is colored by its worst indicator. Click it to filter the cards.
- Indicator cards with value, personal baseline, trend and a 14-day sparkline.
- Detail panel: a trend chart with the preflight baseline band and the warning/critical limits,
  why the status fired, what to do now, why it matters in space, how to measure, and sources.
- Daily check-in form (manual entry, mood slider, notes). It updates the status immediately.
- Alert timeline. Click an event to jump to that day.
- Mission replay slider to see what AURA showed on any day, plus an environment switcher
  (ISS, lunar surface, Mars transit).

## Data

See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for what is real research data, what is
synthetic, and where each threshold comes from.
