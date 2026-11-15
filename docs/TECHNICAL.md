# AURA technical documentation

*Your crew's health, even when Earth is 20 minutes away.*

**AURA: Autonomous Unified Risk Assessment.** Astronaut health monitoring for long missions far
from Earth. NASA Space Apps Challenge 2026, team NeuralAI (Ibrahim Irfan, lead; Melvyn Avoa).

This document explains how AURA is built: architecture, data, the decision rules, the AI layer,
every API endpoint, the front end, testing, and how to extend it. For a feature tour, see the
[README](../README.md). For data provenance, see [DATA_SOURCES.md](DATA_SOURCES.md). For a 5-minute
walkthrough, see [DEMO_SCRIPT.md](DEMO_SCRIPT.md). For manual test steps, see [TEST_CASES.md](TEST_CASES.md).

---

## Contents

1. [Design principles](#1-design-principles)
2. [Architecture](#2-architecture)
3. [Repository layout](#3-repository-layout)
4. [Running AURA](#4-running-aura)
5. [Data model](#5-data-model)
6. [Core engine: baselines, alerts and forecast](#6-core-engine-baselines-alerts-and-forecast)
7. [Feature modules](#7-feature-modules)
8. [AI layer](#8-ai-layer)
9. [API reference](#9-api-reference)
10. [Front end](#10-front-end)
11. [Testing](#11-testing)
12. [Safety, limitations and known gaps](#12-safety-limitations-and-known-gaps)
13. [Extending AURA](#13-extending-aura)

---

## 1. Design principles

1. **Rules decide, AI explains.** Every Normal / Warning / Critical level comes from fixed,
   readable Python rules (`alerts.py`, `symptoms.py`, `radiation.py`, `checks.py`). The AI
   (Claude) summarises, explains and coaches. It never sets or overrides a level, and it is told
   to escalate whenever a level is critical.
2. **Compare each person with themselves.** Every astronaut has a personal baseline from
   preflight data. A sustained shift is caught even while it is still "Earth-normal".
3. **Works offline.** Every AI feature has a deterministic fallback, so the app works with no
   API key and no network. That matters for a demo, and it reflects a spacecraft with a delayed
   or broken link to Earth.
4. **Always say why.** Every alert, forecast, plan change, triage result and excluded data point
   carries a plain-language reason.
5. **Label every data source.** Each record has a `source`: `synthetic`, `research`, `manual` or
   `imported`. Real NASA data and synthetic demo data are never mixed.
6. **Zero setup.** The mission lives in memory and is regenerated from a seed, so there is no
   database or migration to run.

All thresholds are **prototype rules** drawn from published research and common clinical
reference ranges. They are **not** clinically validated flight-medicine limits.

---

## 2. Architecture

```
┌──────────────────────────── Browser (React 19 + Vite + Recharts) ───────────────────────────┐
│  Home + 12 hash-routed pages: status, check-in/symptoms, plan, radiation, message ground,   │
│  alerts, routine, team, ground view, flight surgeon console (live ground), NASA data        │
│  Ask AURA chat (voice in, voice out, auto-navigation) · guided demo tour · dark/light theme │
└───────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                            │  fetch /api/*  (Vite dev proxy → :8000)
┌───────────────────────────────────────────▼─────────────────────────────────────────────────┐
│ FastAPI app (backend/aura/main.py)  ·  Pydantic v2 request models  ·  /docs (OpenAPI)        │
│                                                                                             │
│  MissionStore (store.py, in memory) ── baselines (preflight | adaptive) ── readings by day   │
│        ▲                                                                                    │
│        │ generate()                                                                         │
│  simulator.py (seeded synthetic telemetry, 5 scenarios)   importer.py (your CSV)            │
│  custom.py (user-defined indicators)                                                        │
│                                                                                             │
│  Rule engines:  alerts · forecast · checks · symptoms · radiation · planner · wellbeing     │
│                 gamification · comms (simulated or live ground) · ground · voice            │
│  Speech:        speech.py → Whisper (faster-whisper, on the CPU, no cloud)                  │
│  Real data:     research.py  ← data/osdr/*.csv (NASA OSDR, Inspiration4)                     │
│  AI:            ai.py (briefing, Q&A, research review) · assistant.py (Ask AURA)             │
│                 → Claude API with structured output, or a deterministic offline fallback    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

**A typical request.** When the dashboard asks for `GET /api/crew/aura-2/status?day=48`:

1. `main.py` checks that the crew member exists (404 if not).
2. `MissionStore.assessments()` runs `alerts.assess()` for each indicator. It uses that
   member's readings up to day 48 and `store.baseline(crew, indicator, 48)`, which is the
   preflight baseline or the adaptive in-flight baseline, depending on the mode.
3. `overall_level()` and `body_system_rollup()` combine the results. The response lists every
   indicator with its level, reasons, actions and a trend, plus a colour for each body system.

**State.** One `MissionStore` per process holds everything: crew, readings, baselines, check-ins,
symptom logs, completed tasks, plan ticks, the comms outbox and Ask AURA memory. A
`threading.Lock` guards reloads. The comms outbox also holds the ground mode (`simulated` or
`live`). Restarting the back end regenerates the mission from
`AURA_SEED`. Custom indicator *definitions* are the one thing persisted, to
`data/custom_indicators.json`.

---

## 3. Repository layout

```
backend/
  aura/
    main.py          FastAPI app: routes, request models, wiring (≈750 lines)
    indicators.py    Catalog of the 10 built-in indicators: limits, hazards, body system, refs
    alerts.py        Baseline + alert engine (levels, reasons, actions, trend, rollup)
    store.py         In-memory MissionStore; preflight and adaptive baselines
    simulator.py     Seeded synthetic telemetry, 5 health scenarios, default crew
    forecast.py      Trend projection, 95% band, crossing range, related trends
    checks.py        Check-in plausibility checks and unit hints
    symptoms.py      Symptom catalog (17) and rule-based triage
    comms.py         Signal-delay model, crew↔ground outbox, live ground console (inbox, seen, reply)
    radiation.py     Career / 30-day / 1-year dose budget
    planner.py       Daily countermeasure plan
    wellbeing.py     Crew wellbeing score and trends
    gamification.py  Routine tasks, streaks, points, levels, badges, challenges, crew board
    voice.py         Spoken check-in parser
    ground.py        Flight-surgeon overview and printable HTML report
    importer.py      CSV import of your own data
    custom.py        User-defined indicators
    research.py      NASA OSDR Inspiration4 lab parser and quality checks
    ai.py            Claude: daily briefing, Q&A, research review (+ offline fallbacks)
    assistant.py     Ask AURA chat: answer, steps, validated actions, memory, auto-navigation
    speech.py        On-device speech-to-text for Ask AURA (Whisper via faster-whisper)
  tests/             pytest suite (193 tests)
  requirements.txt   fastapi, uvicorn, pydantic, numpy, anthropic, faster-whisper; pytest, httpx
  .env.example       ANTHROPIC_API_KEY placeholder
frontend/
  index.html         Fonts (Plus Jakarta Sans, JetBrains Mono) and the pre-paint theme script
  src/App.jsx        Top-level state, data loading, hash routing, action routing
  src/pages.js       Page list, menu groups, related links, PAGE_OF_TARGET
  src/api.js         Thin fetch wrapper, one method per endpoint
  src/levels.js      Level → label, icon, CSS class
  src/components/    28 components (see §10)
  src/styles.css     All styles: dark space theme on :root, light overrides under [data-theme='light']
  vite.config.js     Dev server on :5173, proxies /api to :8000
data/
  osdr/              4 NASA OSDR files, unchanged
  import_template.csv, synthetic_telemetry.csv, mission.json (exported demo data)
Dockerfile, render.yaml  One-container hosted demo (builds the front end, bakes in the speech model)
docs/                README companions: this file, DATA_SOURCES, DEMO_SCRIPT, TEST_CASES, screenshots
```

---

## 4. Running AURA

**Requirements:** Python 3.11+ and Node 20+.

```bash
# Back end (terminal 1)
cd backend
python -m venv .venv && source .venv/bin/activate      # with conda: run `conda deactivate` first
python -m pip install -r requirements.txt
python -m pytest -q                                    # 193 passed
python -m uvicorn aura.main:app --reload --port 8000   # API docs at http://localhost:8000/docs

# Front end (terminal 2)
cd frontend
npm install
npm run dev                                            # http://localhost:5173
                                                       # add `-- --host` to open it from a second device
```

**First voice question.** The Whisper model (about 140 MB) downloads the first time Ask AURA is
opened; `GET /api/speech/status` shows `loading`, then `ready`.

**Hosted demo.** `docker build -t aura . && docker run -p 8000:8000 aura` serves the built front end
and the API from one container on :8000. `render.yaml` deploys the same image to Render; set
`ANTHROPIC_API_KEY` there to turn the AI on.

**Turn on the AI (optional).** Either run `ant auth login` (the Anthropic CLI profile is picked
up automatically), or put `ANTHROPIC_API_KEY=...` in `backend/.env`. Without credentials, every
AI feature uses its offline fallback, and `GET /api/ai/status` says so.

**Environment variables**

| Variable | Default | Effect |
| --- | --- | --- |
| `AURA_ENVIRONMENT` | `lunar_surface` | `iss`, `lunar_surface` or `mars_transit`: radiation level, signal delay |
| `AURA_DAYS` | `60` | Mission length in days |
| `AURA_SEED` | `42` | Random seed for synthetic telemetry (deterministic) |
| `AURA_CORS_ORIGINS` | Vite dev server | Comma-separated allowed origins |
| `AURA_AI_MODEL` | `claude-opus-5-5` | Claude model for the AI features |
| `ANTHROPIC_API_KEY` | none | API key (or use `ant auth login`) |
| `AURA_WHISPER_MODEL` | `base.en` | Whisper model for on-device speech (`tiny.en` is lighter, `small.en` more accurate) |
| `AURA_SPEECH` | `on` | `off` disables on-device speech; the front end falls back to browser speech |
| `AURA_API_URL` | `http://localhost:8000` | Front end only: where Vite proxies `/api` |

**Export the demo data:**
`python -m aura.simulator --out ../data --days 60 --environment lunar_surface` writes
`synthetic_telemetry.csv` and `mission.json`.

---

## 5. Data model

### 5.1 Indicators (`indicators.py`)

Each `Indicator` has a key, name, unit, body system, NASA hazards, a direction (which way is
adverse), absolute `Limits`, a plausible range, `min_meaningful_change`, `use_baseline`,
plain-language "why it matters" and "how to measure" text, and references.

| Key | Name | Unit | Body system | Warning (low / high) | Critical (low / high) |
| --- | --- | --- | --- | --- | --- |
| `heart_rate` | Resting heart rate | bpm | heart | 45 / 100 | 38 / 130 |
| `systolic_bp` | Systolic blood pressure | mmHg | heart | 90 / 140 | 80 / 180 |
| `diastolic_bp` | Diastolic blood pressure | mmHg | heart | 55 / 90 | 45 / 120 |
| `spo2` | Blood oxygen (SpO2) | % | lungs | 94 / – | 90 / – |
| `glucose` | Blood glucose (fasting) | mg/dL | metabolic | 70 / 125 | 54 / 250 |
| `body_temp` | Body temperature | °C | immune | 35.5 / 37.9 | 35.0 / 39.0 |
| `sleep_hours` | Sleep duration | h | brain | 5.5 / – | 4.0 / – |
| `mood` | Mood (self-report) | /10 | brain | 4 / – | 2 / – |
| `exercise_minutes` | Exercise countermeasures | min | musculoskeletal | 75 / – | 30 / – |
| `radiation_dose` | Radiation dose (daily) | mSv | whole body | – / 2.0 | – / 10.0 |

Indicators map to NASA's five hazards of human spaceflight (radiation, isolation and
confinement, distance from Earth, gravity fields, hostile and closed environments) and to HRP
risks. Users can add up to **12 custom indicators** (`custom.py`, see §7.10).

### 5.2 Readings and sources

A reading is `(crew_id, indicator, day, value, source, timestamp)`. Days ≤ −1 are **preflight**
and build the baseline. Days ≥ 1 are **in flight**; there is no day 0.

| `source` | Where it comes from |
| --- | --- |
| `synthetic` | `simulator.py`: seeded, deterministic demo telemetry |
| `manual` | A check-in typed or spoken by the astronaut |
| `imported` | A user's own CSV (`importer.py`) |
| `research` | Real Inspiration4 labs from NASA OSDR (`research.py`). Shown in a separate panel and never mixed with crew telemetry |

### 5.3 Synthetic crew (`simulator.py`)

- 7 preflight days (`PREFLIGHT_DAYS`), then `AURA_DAYS` mission days.
- Each crew member has personal baseline means (editable), a health **scenario**, and a
  `prior_dose_mSv` from earlier missions.
- Every reading is baseline + documented in-flight adaptation + scenario effect + noise, drawn
  from a seeded RNG. The same seed always gives the same mission.
- A solar particle event happens around day 22 (`SPE_DOSE`: 0.4, **12.0**, 3.1, 0.8 mSv on days
  21–24). Doses scale with the environment.

| Scenario | Story |
| --- | --- |
| `nominal` | Normal adaptation only |
| `behavioural_cardio` | Sleep declines, then mood, then exercise slips, then heart rate and BP rise |
| `immune_fever` | Viral reactivation: fever and a raised heart rate build over the last days |
| `circadian` | Shift work erodes sleep early; mood dips but the body copes |
| `deconditioning` | Exercise slips, so resting heart rate and glucose creep up |

**Default crew:**

| ID | Name | Scenario | Prior dose |
| --- | --- | --- | --- |
| `aura-1` | Cmdr. Lena Ortiz | nominal | 410 mSv |
| `aura-2` | Dr. Kenji Sato | behavioural_cardio | 95 mSv |
| `aura-3` | Amara Diallo | immune_fever | 0 mSv |

`PUT /api/mission/crew` replaces the crew (any size, with a safety cap of 100 for the hosted demo) and regenerates the mission.
`POST /api/mission/next-day` appends one more day of synthetic readings.

---

## 6. Core engine: baselines, alerts and forecast

### 6.1 Personal baseline

`Baseline.from_values()` takes the mean and SD of an indicator's preflight readings. It needs
at least `MIN_BASELINE_READINGS = 3`. The SD has a floor of half the indicator's
`min_meaningful_change`, so a very steady person doesn't get flagged for tiny wobbles.

**Adaptive in-flight baseline** (`store.baseline`, optional, `PUT /api/mission/baseline-mode`).
Long missions shift some values for expected reasons, such as fluid shifts. In adaptive mode, the
baseline for day *d* is learned from readings on days *d*−28 to *d*−8. The last week is left
out, because that's the week being judged. Readings more than 2 preflight SD away are dropped,
and at least 10 readings are needed (`ADAPT_MIN`). The learned mean may move **at most 1
preflight SD** (`ADAPT_MAX_SHIFT_SD`), so a slow drift is still caught. The SD is at least 0.75 ×
the preflight SD. Each baseline is labelled `kind: preflight | adaptive`.

### 6.2 Alert rules (`alerts.py`)

Checked in order, and the first match wins:

| # | Level | Rule |
| --- | --- | --- |
| 1 | Critical | The latest reading crosses an absolute critical limit |
| 2 | Warning | The latest reading crosses an absolute warning limit |
| 3 | Warning | **Sustained deviation:** the last 3 readings (`SUSTAINED_WINDOW`) are each ≥ 1.5 SD on the adverse side of the baseline, their mean is ≥ 2.0 SD away, and the shift is ≥ `min_meaningful_change` |
| 4 | Warning | **Unusual reading:** a single reading ≥ 3.5 SD (`SPIKE_Z`) on the adverse side, with a shift ≥ 2 × `min_meaningful_change` |
| 5 | Normal | Otherwise |

Each `Assessment` returns the level, the latest value, the z-score, reasons ("3 readings in a row
1.8–2.4 SD above your baseline…"), actions, a 7-day trend (`TREND_WINDOW`) and `escalate`
(true for any critical). `overall_level()` is the worst indicator. `body_system_rollup()` colours
each body system by its worst indicator, for the clickable body figure.

`store.alert_timeline()` lists the days on which an indicator changed level. The front end can
filter it by level, body system and day range.

### 6.3 Early-warning forecast (`forecast.py`)

For each indicator:

1. Fit a straight line to the last 10 in-flight readings (`FIT_WINDOW`; at least 5 are needed).
2. Keep only trends that are adverse, clear (R² ≥ 0.3) and meaningful.
3. Find when the line crosses the next threshold: the baseline band edge (mean ± 2 SD), then the
   warning limit, then the critical limit, within `HORIZON = 14` days.
4. Project 7 days ahead (`PROJECT_DAYS`) with a **95% prediction band** (Student-t table `T95`).
   Turn the band into an earliest-to-latest crossing range.
5. **Related trends:** over the last 14 days, list indicators whose readings correlate at
   |r| ≥ 0.6 with this one, among indicators that are themselves trending. For example, in
   Diallo's fever, heart rate moves with body temperature (r ≈ 0.95).

The forecast never changes a level. It says "if nothing changes, this is where the trend goes".
Kenji Sato's heart-rate warning is forecast 2 days before it fires.

---

## 7. Feature modules

### 7.1 Check-in plausibility (`checks.py`)

`POST /api/crew/{id}/checkins/check` runs before any check-in is saved.

- **Errors (blocked):** a value outside the indicator's plausible range. `_unit_hint` spots
  common mix-ups and suggests a fix: °F → °C (98.6 → 37.0), mmol/L → mg/dL for glucose, minutes →
  hours for sleep, fractions → percent for SpO2, and a missing digit.
- **Warnings (saved only after the astronaut confirms):** |z| ≥ 4 from the baseline (`Z_LIMIT`),
  a jump from the last reading ≥ 5 SD (`JUMP_SD`), or systolic ≤ diastolic.

`POST /checkins` repeats the error check on the server, so a client can't skip it.

### 7.2 Symptom log and triage (`symptoms.py`)

17 symptoms in body-area groups, each with flags (`red_flag`, `follow_up`, `early_ok`) and the
indicators worth checking. A severity from 1 to 10 is triaged as follows:

- **Critical:** any red flag (chest pain, breathing difficulty, sudden vision loss, fainting,
  confusion, severe flank pain), or severity ≥ 9. The advice is "contact the flight surgeon now".
- **Warning:** a follow-up symptom (a vision change, which may be SANS; a persistent headache;
  motion sickness after day 3), severity ≥ 7, or the same symptom on 3 of the last 5 days.
- **Normal:** expected early adaptation (congestion, back pain, early motion sickness) or a
  mild symptom. The advice is self-care.

`seed_demo()` gives each synthetic scenario a believable symptom history.

### 7.3 Messages to ground with signal delay (`comms.py`)

One-way delay: ISS ≈ 0.5 s; lunar surface ≈ 1.3 s; Mars transit grows from 0.02 AU to 1.5 AU
over the mission, at 8.317 light-minutes per AU (up to about 12.5 min one way).

`Outbox.send()` records a message with the status packet attached. The reply time is
`2 × delay + 300 s` handling time (`GROUND_HANDLING_S`). A demo clock (`DEMO_SPEED = 60`) makes a
12-minute wait take 12 seconds on screen, but the true delay is always shown.

Who answers depends on the **ground mode** (`GET/PUT /api/comms/mode`):

- **Simulated** (default): a rule-based reply built from the crew member's AURA status, labelled
  as simulated, queued for `2 × delay + 300 s`.
- **Live**: no reply is queued. A person on the **Flight surgeon console** (a second laptop or
  phone) answers. `Outbox.inbox()` lists only messages whose signal has reached Earth, plus a count
  still in transit. `mark_seen()` records `seen_at` when the console shows a message.
  `reply()` creates a `from_ground` message (`simulated: False`) that arrives after one more
  one-way delay. Answering or marking a message before it has reached Earth raises `ValueError`
  (HTTP 409).

Replies are hidden from the crew until they "arrive". The crew's **delivery status** ticks through
Sent → Delivered to Earth → Seen by flight surgeon → Reply received. A live "seen" receipt also
travels back, so the crew sees it at `seen_at + one-way delay`. The ground view sees crew messages
only after their signal arrives.

### 7.4 Radiation dose budget (`radiation.py`)

Limits from NASA-STD-3001 Vol. 1 Rev B: **600 mSv career**, 250 mGy-Eq in any 30 days and
500 mGy-Eq in a year (mSv is used as an approximation for these). Career dose = `prior_dose_mSv`
plus this mission. The budget reports the current rate over the last 7 days, the days left at
that rate and a projection to the end of the mission.

- **Warning:** ≥ 80% of any limit used, or the current rate would pass the career limit before
  the mission ends.
- **Critical:** a limit is reached, or a daily dose is ≥ 10 mSv (a solar particle event).

Ortiz is the demo case: she uses about 85% of her career limit and gets a warning.

### 7.5 Countermeasure planner (`planner.py`)

`plan(store, crew_id, day)` starts from a standard ISS-style day with about 2.5 h of exercise.
It then adapts each timed block to that day's alerts, symptom triage and radiation budget. The
blocks are: bright-light session, morning vitals, aerobic, resistive (or rest when exercise is
unsafe), post-meal cycle, limit high-dose time, private family call, evening check-in, wind-down
and sleep window. Each block has `changed`, `because` and `indicator`, so the UI can show why it
changed and link to the cause. Ticks are stored per crew and day (`plan_done`).

### 7.6 Crew wellbeing (`wellbeing.py`)

Over the last 7 days, the score is 100 minus capped penalties:

- mood below baseline: 10 per SD, at most 30
- sleep below baseline: 8 per SD, at most 25
- days with insomnia, low mood or fatigue logged: 5 per day, at most 20
- the share of days under the 90-minute exercise target: up to 10

Bands: **thriving ≥ 75**, **watch 55–74**, **needs support < 55**. The crew score is the
average of the member scores. The overview also returns 30-day mood and sleep series (each
person plus the crew average), the 14-day mood slope, and team suggestions (private check-in,
protect sleep, shared meal). It is a prototype composite, not a psychological assessment.

### 7.7 Gamified routine (`gamification.py`)

- **Daily tasks** are completed by the data itself. Wearable-synced indicators count when a
  reading exists. Manual ones (BP, temperature, glucose, mood) must be entered that day. A
  **follow-up** task (15 points) appears for each flagged spot measurement and is done when it is
  re-measured. Wellness tasks are ticked by hand.
- **Points and levels:** Cadet 0, Mission Specialist 1,500, Flight Engineer 3,000, Commander
  4,500, Mission Legend 6,000.
- **Streaks:** check-in, exercise (≥ 90 min) and sleep (≥ 6.5 h).
- **11 badges**, for example Baseline Builder, Storm Survivor, Iron Crew, 30-Day Streak, Ground
  Link, Honest Reporter, On Plan and Challenger.
- **Weekly challenges** (+50 points each): sleep 7+ h on 5 nights, 90+ min exercise on 6 days,
  symptoms logged on 3 days, and the plan completed on 3 days.
- **Crew board:** ranks by points, highlights "you", and sets a shared crew goal: everyone logs
  their routine today.

### 7.8 Voice check-in (`voice.py`)

The browser turns speech into text with the Web Speech API (Chrome and Safari). People can also
type the sentence. (Ask AURA uses the on-device model instead, see §7.12.) `parse(text)`:

1. `words_to_numbers()` turns "sixty two point five" into 62.5 and "a hundred and eighteen" into
   118.
2. Keyword patterns pick out heart rate or pulse, blood pressure ("118 over 76"), SpO2, glucose,
   temperature, sleep ("six and a half"), mood, exercise and dose.
3. Symptom phrases ("headache", "can't sleep", "chest pain") are mapped to symptom catalog keys.

It returns `values`, `symptoms` and `understood`. **Nothing is saved**: the form is filled in for
review, and the plausibility checks still apply.

### 7.9 Ground view and reports (`ground.py`)

`overview()` lists every crew member, sorted by priority. Priority is the worst of telemetry
level, symptom triage and radiation status. Each row has the top issues and the messages that
have arrived. `report_html()` builds a printable, self-contained HTML health report for one
person or the whole crew, with user text HTML-escaped. People save it as PDF from the browser.

### 7.10 Custom indicators (`custom.py`) and CSV import (`importer.py`)

- **Custom indicators** (up to 12): a name, unit, typical range, warning and critical limits,
  body system and hazards. They get baselines, alerts, charts, check-ins, import and AI coverage.
  Synthetic crew get readings drawn from a separate random stream, so the built-in data never
  changes. Definitions persist in `data/custom_indicators.json`, which is gitignored.
- **CSV import** accepts a wide layout (one row per day) or a long layout (`day,indicator,value`),
  up to 5,000 rows, with case-insensitive aliases. Every value is range-checked. The result is a
  new crew member with `source: imported`.

### 7.11 Real NASA data (`research.py`)

The parser reads ALSDA "TRANSFORMED" CSVs for the Inspiration4 crew (C001–C004). Samples are
taken at L−92, L−44 and L−3 (days before launch) and R+1, R+45, R+82 and R+194 (days after
return).

| Dataset key | File | Study | Content |
| --- | --- | --- | --- |
| `cmp` | LSDS-8 Comprehensive Metabolic Panel | OSD-575 | Serum chemistry, with lab ranges |
| `cbc` | LSDS-7 Complete Blood Count | OSD-569 | Whole blood, with lab ranges |
| `immune` | LSDS-8 Multiplex immune (Eve panel) | OSD-575 | 71 cytokines, pg/mL, no clinical range |
| `cardio` | LSDS-8 Multiplex cardiovascular (Eve panel) | OSD-575 | 9 acute-phase and vascular proteins |

- **Columns:** `<analyte>_value_<unit>` with `_range_min` and `_range_max` (CMP and CBC), or
  `<analyte>_concentration_<unit>` (multiplex). Units are made readable (mg/dL, ×10³/µL, pg/mL…).
  Values are never altered.
- **Flags:** CMP and CBC values are flagged low, normal or high against each sample's own lab
  range. The multiplex panels have no clinical range, so they are compared only with the
  person's own preflight samples.
- **Quality checks:**
  - *CBC consistency:* absolute neutrophils must ≈ WBC × neutrophil % × 10. C003 at L−92 fails
    this, so the whole sample is excluded.
  - *Assay limit:* 3 or more samples of one marker with the exact same value (at least 4
    significant digits) are treated as the assay's measurement limit and excluded. This catches
    haptoglobin (7 samples at 17,907,000 ng/mL), IFN-α2 (4 at 120.88 pg/mL) and IL-28A (5 at
    15.56 pg/mL).
  - Excluded points stay in the data with `suspect: true` and a reason. They are left out of
    charts and the AI.
- **`crew_profile(crew)`** builds the input for the AI review. For each featured marker, it
  gives the preflight mean, the R+1 value, the % change, the latest value, out-of-range
  timepoints and all values.

### 7.12 On-device speech for Ask AURA (`speech.py`)

Spoken questions are recorded in the browser (MediaRecorder) and sent to AURA's own server, where
OpenAI's open-source **Whisper** model (`base.en`, via faster-whisper on the CPU, int8) turns them
into text. No cloud speech service is involved, so it works with no link to Earth and in every
browser. The browser stops recording after about 1.5 s of silence (30 s cap). Audio is decoded
with PyAV to 16 kHz mono; a short vocabulary prompt helps with words like SpO2 and paracetamol.
The model loads once, in the background, when Ask AURA is first opened. If faster-whisper is not
installed, the model can't load, or `AURA_SPEECH=off`, the front end falls back to the browser's
Web Speech API. The Docker image bakes the model in at build time.

Ask AURA reads answers aloud with the browser's `speechSynthesis` (the answer, then "Step N." for
each step). Questions asked by voice are answered by voice unless the 🔊 toggle is off
(`localStorage` key `aura-voice-replies`).

---

## 8. AI layer

### 8.1 Features

| Feature | Endpoint | Module | Output | Offline fallback |
| --- | --- | --- | --- | --- |
| Daily briefing | `POST /api/crew/{id}/briefing` | `ai.py` | Structured `Briefing` (headline, escalate, priorities, patterns, encouragement) | `offline_briefing()` from the rule results |
| Ask the flight surgeon | `POST /api/crew/{id}/ask` | `ai.py` | Free text grounded in that person's data | A fixed message pointing to the indicator cards, escalating if anything is critical |
| Research review | `POST /api/research/crew/{C00n}/review` | `ai.py` | `ResearchReview`: headline, 2–4 findings, 2–3 recommendations, caveats | Largest return-day shifts |
| Ask AURA | `POST /api/assistant` | `assistant.py` | `AssistantReply`: answer, steps, actions | Regex FAQ + red-flag escalation |

### 8.2 How the Claude calls are made

- **SDK and model:** the official `anthropic` Python SDK. The briefing, research review and Ask
  AURA use `client.beta.messages.parse(...)` with a Pydantic `output_format`, so replies are
  validated JSON. Ask the flight surgeon uses `messages.create` for free text, with the last 10
  turns of history. The model is `AURA_AI_MODEL` (default
  `claude-opus-5-5`), with `fallbacks="default"` so the API can serve a fallback model if the
  primary is unavailable.
- **Effort:** `effort: medium` for the briefing and research review, and `low` for Q&A and Ask
  AURA, to keep the chat fast.
- **Prompt caching:** system prompts are cached (`cache_control: ephemeral`).
- **Grounding:** `build_context()` sends a compact JSON of that day's status: levels, reasons,
  forecast, symptom triage, radiation budget and recent check-ins. The AI is told to use only
  this data.
- **Failures:** any exception, refusal or empty output falls back to the offline version, with
  a `note` explaining why. The UI shows whether an answer came from AI or offline.

### 8.3 Safety rules (in every prompt)

1. The rule engine owns every alert level. The AI never changes one.
2. Any critical level means: tell them to contact the flight surgeon now.
3. Never diagnose, prescribe or dose medication. Defer to a physician.
4. Say "consistent with", never "caused by", and point out sample-handling or one-off effects in
   the research data.
5. Stay within the data given, and be brief and concrete.

### 8.4 Ask AURA specifics (`assistant.py`)

- **Context:** the current view (crew member, day, open indicator, panel), the app guide
  (`APP_GUIDE`: every feature and the 17 tour steps), a research summary, symptom keys and saved
  memory notes.
- **Actions:** the model can only choose from a fixed set of action types, which `_clean()`
  validates. Targets must exist, so the model can't invent a target. The action types cover
  opening any page (`open_page`, including the console), an indicator, check-in, symptoms, radiation,
plan, team, ground or the crew editor;
  jumping to a day; drafting a message to ground; pre-filling a symptom; and remembering a note.
- **Memory:** "remember that…" saves a note (`GET/POST/DELETE /api/memory`). Notes are included
  in later context and survive a mission reset.
- **Auto-navigation:** when the question asks to go somewhere ("take me to Ground view", "open the
  console", "show me Amara"), `auto_action()` returns the index of the first view-only action
  (`NAV_ACTIONS`: open a page, indicator, crew member, day…). The front end runs it at once and
  shows "✓ Opened: …" instead of a button. "How/why/what…" questions never auto-run, and actions that
  change data (remember, draft a message, log a symptom) always need a click. The response carries
  it as `auto_action` next to `reply`, so the AI's output schema is unchanged.
- **Voice:** questions can be spoken (on-device Whisper, §7.12) and answers read aloud.
- **Offline order:** red-flag words come first (escalate), then "remember…", then "show me day
  N", then the FAQ patterns.

---

## 9. API reference

All routes are under `/api`, return JSON (except reports) and are documented live at
`http://localhost:8000/docs`. `{id}` is a crew ID such as `aura-1`. `?day=` replays any past
day; leave it out for "live" (the current day).

**Mission and crew**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| GET | `/mission` | Mission info, current day, environment, baseline mode, data notice |
| GET | `/environments` | ISS, lunar surface, Mars transit |
| POST | `/mission/reset` | Regenerate (`environment`, `days`, `seed`); keeps the crew |
| POST | `/mission/next-day` | Advance one day |
| GET / PUT | `/mission/baseline-mode` | `preflight` or `adaptive` |
| GET | `/crew-options` | Scenarios, editable baselines, default crew |
| PUT | `/mission/crew` | Replace the crew and regenerate |
| GET | `/crew` | Crew with overall status |
| GET | `/crew/{id}` | One member |
| GET | `/crew/import/template` | Example CSV |
| POST | `/crew/import` | Add a member from CSV |

**Indicators, status and telemetry**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/indicators` | Catalog with limits, explanations, actions, references |
| GET | `/indicators/options` | Choices for the Add indicator form |
| POST | `/indicators` | Add a custom indicator |
| DELETE | `/indicators/{key}` | Remove a custom indicator |
| GET | `/hazards` | NASA's five hazards → indicators |
| GET | `/crew/{id}/status?day=` | Assessment per indicator and body-system rollup |
| GET | `/crew/{id}/telemetry` | Chart series with baseline and limits |
| GET | `/crew/{id}/alerts` | Timeline of level changes |
| GET | `/crew/{id}/forecast?day=` | Trend crossings, 7-day projection with 95% band, related trends |

**Check-ins and symptoms**

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/checkins/parse` | Spoken or typed sentence → values and symptoms |
| POST | `/crew/{id}/checkins/check` | Plausibility check: errors with hints, warnings to confirm |
| POST | `/crew/{id}/checkins` | Save readings; returns the updated status |
| GET | `/symptoms/catalog` | Symptoms with red flags marked |
| GET / POST | `/crew/{id}/symptoms` | Log with triage / log symptoms (severity 1–10) |

**Care planning, radiation and wellbeing**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/crew/{id}/plan?day=` | Countermeasure plan |
| POST | `/crew/{id}/plan/{block}/toggle` | Tick a block |
| GET | `/crew/{id}/radiation?day=` | Dose budget |
| GET | `/wellbeing?day=` | Crew wellbeing scores, trends, suggestions |
| GET | `/crew/{id}/tasks` | Tasks, streaks, level, badges, challenges, crew board |
| POST | `/crew/{id}/tasks/{task}/complete` | Tick a wellness task |

**Ground**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/comms?day=` | Signal delay for the environment and day |
| GET / POST | `/crew/{id}/messages` | Thread with ground / send a message (response includes `mode`) |
| GET / PUT | `/comms/mode` | `simulated` (template reply) or `live` (a person at the console) |
| GET | `/ground/inbox` | Messages that have reached Earth, newest first, with replies; `in_transit` count |
| POST | `/ground/messages/{id}/seen` | Seen receipt (409 if the message hasn't reached Earth yet) |
| POST | `/ground/messages/{id}/reply` | Human reply, delayed by the one-way time (409 too early, 404 unknown) |
| GET | `/ground?day=` | Flight-surgeon overview |
| GET | `/report?day=` | Printable HTML report, whole crew |
| GET | `/crew/{id}/report?day=` | Printable HTML report, one member |

**AI and research**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/ai/status` | `enabled`, `credentials` (where they were found) and `model` |
| POST | `/crew/{id}/briefing` | Daily briefing |
| POST | `/crew/{id}/ask` | Ask the flight surgeon |
| POST | `/assistant` | Ask AURA (answer, steps, actions) |
| GET | `/speech/status` | On-device speech: `available`, `state` (idle/loading/ready/error), model. Starts loading the model |
| POST | `/speech/transcribe` | Raw audio body (webm/opus, mp4, ogg, wav) → `{text, seconds, audio_seconds}`; 503 if unavailable, 413 over 10 MB |
| GET / POST | `/memory` | Ask AURA's saved notes |
| DELETE | `/memory/{note_id}` | Forget a note |
| GET | `/research` | Datasets and whether each file is present |
| GET | `/research/{cmp\|cbc\|immune\|cardio}` | One Inspiration4 dataset |
| POST | `/research/crew/{C001..C004}/review` | AI review of one real crew member |

**Errors.** 404 for an unknown crew member, indicator or dataset. 422 for invalid input
(Pydantic validation, an implausible check-in value, a bad CSV), with a readable `detail`.

**Example**

```bash
curl -s localhost:8000/api/crew/aura-2/status?day=48 | jq '.overall, .indicators[0]'
curl -s -X POST localhost:8000/api/checkins/parse -H 'content-type: application/json' \
     -d '{"text":"pulse sixty two, slept six and a half hours, mild headache"}'
```

---

## 10. Front end

**Stack:** React 19, Vite 8, Recharts 3. There is no router library (a small hash router in `App.jsx`)
and no state library. `App.jsx`
holds the state and passes props and callbacks down.

**Data flow.** `App.jsx` loads the mission, catalog and crew on start. When the selected crew
member or day changes, it loads status, telemetry, alerts, routine, forecast and radiation in
parallel. `day = null` means live. After any write (check-in, symptom, plan tick), the affected
panels reload. `handleAction()` routes every action, from Ask AURA, the
tour or a button, to UI state: open a panel, scroll, select a day or indicator, pre-fill a form.

**Pages.** AURA opens on a **landing page** (story, mission at a glance, crew snapshot, ▶ demo tour and a
menu of feature cards). Every feature has its own page, reached from the menu bar or the cards, with a URL
hash route so the browser's back button works: `#/home`, `#/status` (banner, AI briefing and forecast, body
figure, indicators, detail), `#/checkin` (check-in and symptom log), `#/plan`, `#/radiation`, `#/comms`,
`#/timeline`, `#/routine`, `#/team`, `#/ground`, `#/console`, `#/research`. `pages.js` defines the pages, their menu
groups and their `related` links (shown at the bottom of each page), and `PAGE_OF_TARGET`, which tells the
demo tour and Ask AURA which page holds an element. The crew picker and mission replay stay in the sidebar,
and the status banner is shown on every crew page. Ask AURA's `open_page` action (validated against the page
list) moves the user between pages, and runs by itself when the user asks to go somewhere (§8.4).

**Look and layout.** A dark space theme by default (navy `#020617` background, cyan accent, glass
header), with a light theme under `:root[data-theme='light']`. The ☀ Light / ☾ Dark button stores the
choice in `localStorage` (`aura-theme-v2`), and an inline script in `index.html` applies it before the
first paint. Content sits in a centred 1280 px column under a full-width sticky header (brand and
mission controls, then the centred page menu). The home page is one centred column: badge, title,
gradient tagline, buttons, a check row, then the mission card as a console window. Page titles and
section headings are centred. On phones the header is static and the layout stacks. Both themes
pass an axe WCAG 2 AA audit on every page.

| Component | Role |
| --- | --- |
| `Header`, `NavBar` | Glass header: brand, mission, environment, day, demo tour, reset, theme switch; centred page menu |
| `Landing` | Centred home page: hero, mission at a glance, feature cards by group |
| `CrewList`, `DayScrubber` | Crew picker and mission replay slider (sidebar) |
| `StatusBanner` | Overall level, reasons, Message ground and Report buttons |
| `BodyFigure` | Clickable body coloured per body system |
| `IndicatorGrid`, `IndicatorDetail`, `TrendChart` | Cards, detail with related trends, chart with baseline band, limits and 95% projection band |
| `ForecastPanel` | Early warnings with crossing range |
| `AlertTimeline` | Level changes with filters |
| `CheckInForm` | Typed or voice check-in, plausibility review, symptom hand-off |
| `SymptomLog` | Chips by body area, severity sliders, triage |
| `PlanPanel` | Today's plan with reasons and ticks |
| `RadiationPanel` | Dose budget chart and projection |
| `CommsPanel` | Signal delay, countdown, thread, delivery status (Sent → Delivered → Seen → Reply), live/simulated pill |
| `GroundConsole` | Flight surgeon console: simulated/live switch, inbox polled every 2 s, seen receipts, replies |
| `MissionRoutine` | Tasks, streaks, challenges, crew board, badges |
| `AIPanel` | AI briefing and Q&A |
| `TeamView` | Wellbeing scores and trends |
| `GroundView` | Flight-surgeon overview |
| `ResearchPanel`, `ResearchReview` | Real Inspiration4 data (4 panels) and the AI review |
| `CrewEditor`, `IndicatorManager` | Edit crew, add or remove custom indicators, CSV import |
| `AssistantWidget` | Floating Ask AURA chat: memory panel, 🎙 voice input (Whisper, browser fallback), spoken answers, auto-navigation |
| `DemoTour` | 19-step guided tour |

**Notes for contributors**

- `api.js` has one method per endpoint. Errors throw an `Error` with the server's `detail`.
- Recharts 3 freezes chart data. Copy objects before changing them, or you'll get "Cannot
  assign to read only property".
- Browser storage holds only per-viewer conveniences: chat history (`aura-chat-v1`), theme
  (`aura-theme-v2`), voice replies (`aura-voice-replies`) and the console's signature
  (`aura-console-author`). Everything else is server state.
- `npm run build` writes `frontend/dist/`. FastAPI serves it in the Docker image, or use any static
  host that proxies `/api`.

---

## 11. Testing

```bash
cd backend && python -m pytest -q      # 193 passed in about 11 s
```

| File | Tests | Covers |
| --- | --- | --- |
| `test_custom_data.py` | 35 | Real-world CSV formats, unit conversions, dates to mission days, messy-file errors, sample imports |
| `test_api.py` | 15 | End-to-end endpoints, validation errors, replay |
| `test_assistant.py` | 14 | Action validation, offline FAQ, red-flag escalation, memory, auto-navigation |
| `test_alerts.py` | 11 | Every alert rule, precedence, edge cases |
| `test_import.py` | 11 | Both CSV layouts, validation |
| `test_ai.py` | 10 | Briefing, Q&A and review with a **mocked Claude API**; offline fallbacks |
| `test_research.py` | 10 | OSDR parsing, units, CBC and assay-limit checks, endpoints |
| `test_research_new_data.py` | 8 | Added OSDR panels (serum proteins, urine), dropped-in files, unreadable files |
| `test_gamification.py` | 8 | Tasks, streaks, badges, challenges, crew board |
| `test_symptoms.py` | 8 | Triage rules, persistence, red flags |
| `test_comms.py` | 7 | Delay model, outbox timing, live ground console (inbox, seen, reply, mode API) |
| `test_custom.py` | 7 | Custom indicator lifecycle |
| `test_speech.py` | 6 | Transcribe endpoint with a stand-in model, real webm/mp4 decoding, fallbacks |
| `test_forecast.py` | 6 | Crossings, 95% band, related trends |
| `test_radiation.py` | 6 | Budget, warnings, projection |
| `test_simulator.py` | 6 | Determinism, scenarios |
| `test_ground.py` | 5 | Priority sorting, report escaping |
| `test_planner.py` | 5 | Plan adaptations and reasons |
| `test_adaptive.py` | 4 | Adaptive baseline window and clamp |
| `test_checks.py` | 4 | Errors, unit hints, warnings |
| `test_voice.py` | 4 | Number words, patterns, symptoms |
| `test_wellbeing.py` | 3 | Score, bands, suggestions |

193 tests in total, counting parametrised cases. Tests never call the real Claude API or download the
speech model. The front end was checked in a real browser with Playwright: the 19-step tour, an axe
audit of every page in both themes, phone width, the message status, voice input and talk-back, and a
two-browser run of the live ground console. Manual end-to-end steps are in
[TEST_CASES.md](TEST_CASES.md).
API. Manual end-to-end steps are in [TEST_CASES.md](TEST_CASES.md) (sections A–K).

---

## 12. Safety, limitations and known gaps

- **Not a medical device.** The thresholds are prototype rules, and the clinical logic is not
  validated. Real use would need flight-surgeon review and validation against flight data.
- **Synthetic telemetry.** Continuous astronaut telemetry is not public. The simulator
  reproduces documented directions of change, not real people.
- **Inspiration4 is small and short:** 4 people, 3 days in orbit, and no control group. Cytokines
  vary a lot between people and days.
- **No real ground link.** Ground replies are either rule-based placeholders or typed by a person on
  the Flight surgeon console. The delay is real; the radio link is not.
- **Speech.** The Whisper model is English-only (`base.en`) and needs a few hundred MB of memory. On a
  very small server, set `AURA_WHISPER_MODEL=tiny.en` or `AURA_SPEECH=off`.
- **No authentication and no persistence.** Anyone who can reach the server can read and write.
  Data resets on restart. Swapping `MissionStore` for SQLite and adding sign-in are the natural
  next steps.
- **Single process.** The in-memory store assumes one worker.
- **Voice parsing** handles English and the patterns listed. Anything it doesn't recognise is
  left blank for the user.

---

## 13. Extending AURA

| To add… | Do this |
| --- | --- |
| A built-in indicator | Add an `Indicator` to `INDICATORS` in `indicators.py` (limits, plausible range, direction, body system, hazards, refs), give it noise in `simulator.py`, and add test cases |
| An indicator without code | Use **+ Add indicator** in the UI or `POST /api/indicators` |
| A health scenario | Write `_scenario_x(day, days) -> {indicator: offset}` in `simulator.py` and register it in `SCENARIOS` |
| An OSDR dataset | Put the TRANSFORMED CSV in `data/osdr/`, add a `DATASETS` entry in `research.py` (`ranges: False` if it has no lab range), optionally add `ANALYTE_INFO` text, and add a label in `ResearchPanel.jsx` |
| A symptom | Add a `Symptom` to `CATALOG` in `symptoms.py` with its flags and related indicators |
| An Ask AURA action | Add the type to `AssistantAction` and `_clean()` in `assistant.py`, describe it in `APP_GUIDE`, and handle it in `App.jsx` `handleAction()`. If it only moves the view, add it to `NAV_ACTIONS` so it can auto-run |
| A page | Add it to `PAGES` in `pages.js` and `NavBar.jsx`, render it in `App.jsx`, and add it to `PAGES` in `assistant.py` so Ask AURA can open it |
| A language for voice | Set `AURA_WHISPER_MODEL` to a multilingual model (e.g. `base`) and drop `language="en"` in `speech.py` |
| A badge or challenge | Add a `_badge(...)` in `mission_tasks()` or an entry in `weekly_challenges()` in `gamification.py` |
| Persistence | Implement the `MissionStore` query methods over SQLite; routes don't need to change |
