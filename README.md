# AURA: Autonomous Unified Risk Assessment

**Health monitoring that lets astronauts on long-duration missions assess their own health,
see changes early, and know exactly when to act or call the ground.**

Built for the **NASA Space Apps Challenge 2026**, "Create Health Monitoring Software for
Astronauts on Space Missions".

![AURA dashboard](docs/screenshots/dashboard.png)

> **Prototype disclaimer:** AURA is a hackathon prototype. Its alert thresholds are
> *prototype rules* drawn from published research, **not clinically validated flight-medicine
> limits**. All demo telemetry is **synthetic** and labelled as such.

## The problem

On long missions to the Moon or Mars, astronauts face NASA's five hazards of human
spaceflight: radiation, isolation and confinement, distance from Earth, altered gravity, and a
hostile closed environment. Communication delays mean they must spot health changes in
themselves. Most changes are gradual, and many stay inside "normal" Earth ranges while
already being abnormal *for that person*.

## What AURA does

| | Feature |
| --- | --- |
| 🩺 | **10 indicators** (heart rate, blood pressure, SpO2, glucose, temperature, sleep, mood, exercise, radiation), each mapped to NASA's hazards, with plain-language "why it matters" and "how to measure" notes |
| 📈 | **Personal baselines.** Each astronaut is compared with their own 7-day preflight baseline, so a sustained shift is caught even when it's still Earth-normal |
| 🚦 | **Three transparent levels.** 🟢 Normal, 🟡 Warning, 🔴 Critical, with the reason and the next actions every time |
| 🧍 | **Clickable body figure** colored by each body system's worst indicator |
| ✦ | **AI flight surgeon** (Claude) that writes a 30-second daily briefing and answers questions grounded in the astronaut's data |
| 🎮 | **Gamified routine.** Daily tasks, streaks, points, levels and badges reward measuring regularly and following up on warnings |
| ⏪ | **Mission replay** to see what AURA showed on any day, plus ISS, lunar surface and Mars transit environments |
| ▶ | **Guided demo tour** that walks through the whole mission story in 8 steps |

### Alert logic (in `backend/aura/alerts.py`)

1. **Critical:** the reading crosses a predefined critical limit, so the app tells the astronaut to contact the flight surgeon now.
2. **Warning:** the reading crosses a warning limit, **or** the last 3 readings all sit ≥1.5 SD on the
   adverse side of the personal baseline (mean ≥2 SD and a clinically meaningful change), **or**
   a single reading is ≥3.5 SD out (the app asks for a re-measure).
3. **Normal:** otherwise.

The AI never sets or changes a level. It explains and coaches, and the back end forces an
escalation whenever any reading is critical.

## Quick start

You need **Python 3.11+** and **Node 20+**. Use two terminals.

**Terminal 1: back end**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn aura.main:app --reload
```

> Using conda? Run `conda deactivate` first, or conda's Python can shadow the venv.

**Terminal 2: front end**

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and click **▶ Demo tour** in the header.
The interactive API docs are at http://localhost:8000/docs.

### Turn on the AI flight surgeon (optional)

Use either of these, then restart the back end:

- **Anthropic CLI login:** `brew install anthropics/tap/ant`, then `ant auth login`. The profile is picked up automatically.
- **API key:** copy `backend/.env.example` to `backend/.env` and set `ANTHROPIC_API_KEY`.

Check http://localhost:8000/api/ai/status. Without credentials, AURA shows a rule-based
briefing instead, so the demo always works.

## Demo crew (synthetic)

| ID | Crew member | Story |
| --- | --- | --- |
| `aura-1` | Cmdr. Lena Ortiz | Adapts well. Only the expected in-flight changes. |
| `aura-2` | Dr. Kenji Sato | Sleep slips (warning day 42), then mood (46), then exercise and resting HR (50: 71 bpm, Earth-normal but well above his 64 bpm baseline), then blood pressure (54) and glucose (58). |
| `aura-3` | Amara Diallo | Viral reactivation: fever builds from day 54 and turns **critical** on day 60. |

Everyone gets a solar particle event dose on day 22 (lunar surface and Mars transit only).
For the presentation script, see [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Architecture

```
frontend/  React 19 + Vite + Recharts dashboard  ──/api──►  backend/  FastAPI (Python)
                                                              ├─ indicators.py    catalog, limits, actions, references
                                                              ├─ alerts.py        baseline-deviation alert engine
                                                              ├─ simulator.py     seeded synthetic mission telemetry
                                                              ├─ store.py         in-memory mission store + check-ins
                                                              ├─ gamification.py  tasks, streaks, points, badges
                                                              └─ ai.py            Claude briefing + Q&A, with offline fallback
```

### API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/mission` | Mission info, current day, environment, data notice |
| POST | `/api/mission/reset` | Regenerate the mission (`environment`, `days`, `seed`) |
| GET | `/api/indicators` | Indicator catalog: limits, explanations, actions, references |
| GET | `/api/hazards` | NASA's five hazards mapped to indicators |
| GET | `/api/crew` | Crew with overall status |
| GET | `/api/crew/{id}/status?day=` | Per-indicator assessment and body-system rollup |
| GET | `/api/crew/{id}/telemetry` | Chart series with baseline and limits |
| GET | `/api/crew/{id}/alerts` | Timeline of alert-level changes |
| POST | `/api/crew/{id}/checkins` | Log manual measurements; returns the updated status |
| GET | `/api/crew/{id}/tasks` | Today's tasks, streaks, level and badges |
| POST | `/api/crew/{id}/tasks/{task}/complete` | Tick off a wellness task |
| GET | `/api/ai/status` | Whether Claude is available |
| POST | `/api/crew/{id}/briefing` | AI (or rule-based) daily briefing |
| POST | `/api/crew/{id}/ask` | Ask the AI flight surgeon a question |

## Data and sources

AURA uses a **hybrid approach**: NASA research (OSDR, the Life Sciences Portal and the Human
Research Program) informs which indicators matter and how spaceflight shifts them, and
seeded **synthetic telemetry** stands in for continuous astronaut readings, which are not
public. Every record carries a `source` (`synthetic`, `research` or `manual`), and each
threshold lists its references. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

Export the dataset with `python -m aura.simulator --out ../data` (from `backend/`).

## Tests

```bash
cd backend && python -m pytest
```

The tests cover the alert engine, the simulator scenarios, every API endpoint, gamification,
and the AI layer (with a mocked Claude API).
