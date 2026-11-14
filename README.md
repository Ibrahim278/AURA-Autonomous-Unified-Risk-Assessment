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
frontend/   React (Vite) dashboard (coming next)
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

## Data

See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for what is real research data, what is
synthetic, and where each threshold comes from.
