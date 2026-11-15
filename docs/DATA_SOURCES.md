# Data sources and provenance

AURA follows a **hybrid data approach**: real NASA research informs which indicators we track
and how spaceflight shifts them, and **synthetic telemetry** stands in for the continuous
astronaut readings that are not publicly available.

Every record in the API carries a `source` field: `synthetic`, `research`, or `manual`
(entered by the astronaut). The UI must show this label.

## Research sources

| Source | Used for |
| --- | --- |
| [NASA Open Science Data Repository (OSDR)](https://osdr.nasa.gov/) | Spaceflight physiology studies, including the Inspiration4 commercial crew dataset |
| [NASA Life Sciences Portal (NLSP)](https://nlsp.nasa.gov/) | Human research data on cardiovascular, sleep/circadian and behavioural health |
| [NASA Human Research Program (HRP)](https://www.nasa.gov/hrp/) | The five hazards and the risk catalog that each indicator maps to |
| [OSDR FAQ](https://science.nasa.gov/reference/osdr-faq/) | Data access rules |
| [Inspiration4 health data article](https://science.nasa.gov/humans-in-space/nasas-repository-supports-research-of-commercial-astronaut-health/) | Context for using commercial-crew biomedical data |
| CSA: Monitoring Radiation for Astronaut Health | Radiation dosimetry context for the radiation indicator |

## Real crew data: Inspiration4 bloodwork (NASA OSDR)

The dashboard's **Real crew data** panel shows de-identified clinical labs from the four
Inspiration4 crew (SpaceX, 15–18 Sept 2021), downloaded from OSDR in ALSDA's TRANSFORMED format
and stored unchanged in `data/osdr/`:

| File | Study | Content |
| --- | --- | --- |
| `LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv` | [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575) | Serum metabolic panel: glucose, electrolytes, kidney and liver markers, proteins |
| `LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv` | [OSD-569](https://osdr.nasa.gov/bio/repo/data/studies/OSD-569) | Whole-blood count: red and white cells, haemoglobin, platelets |
| `LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv` | [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575) | Serum immune cytokine array (Eve Technologies multiplex): 71 cytokines and chemokines, pg/mL |
| `LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv` | [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575) | Serum cardiovascular and acute-phase proteins: CRP, fibrinogen, haptoglobin, SAP, α2-macroglobulin, AGP, PF4, L-selectin, fetuin-A |
| `LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv` | [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575) | Serum immune and inflammation proteins (Alamar NULISA 200-plex): 203 proteins in NPQ units, including IL-6, TNF, RANKL, osteopontin, GFAP, EPO and GDF-15 |
| `LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv` | [OSD-656](https://osdr.nasa.gov/bio/repo/data/studies/OSD-656) | The same 200-plex panel in urine (202 proteins, L-92 to R+82), including NGAL, a kidney-stress marker |

Crew C001–C004, sampled at L-92, L-44 and L-3 (days before launch) and R+1, R+45, R+82 and
R+194 (days after return). `backend/aura/research.py` parses the files, keeps each value and the
lab's own per-sample reference range, and flags it low, normal or high. API:
`GET /api/research` and `GET /api/research/{cmp|cbc|immune|cardio}`; every response has `source: research`.

Notes on interpretation:
- An out-of-range value alone is not a diagnosis. The low glucose of three crew at R+45 may
  reflect sample handling (for example delayed processing), so AURA shows it without comment.
- The CBC file labels haemoglobin as `percent`; the values and ranges are clearly g/dL, so the
  UI shows g/dL and says so.
- Quality check: in a CBC, absolute neutrophils must equal WBC × neutrophil %. The published
  C003 L-92 row breaks this (10.1/µL vs about 6,826/µL expected) and several red-cell indices are
  shifted too, so AURA excludes that whole sample from charts and the AI review and says why.
- The multiplex files give `<marker>_concentration_<unit>` and `<marker>_percent` (the value as a
  percent of the panel mean). AURA uses the concentration only. These research assays have no
  clinical reference range, so nothing is flagged high or low; compare each person with their own
  preflight samples.
- Assay-limit check: real concentrations almost never repeat to the last digit, so when 3 or more
  samples of a marker read exactly the same value (with at least 4 significant digits) AURA treats
  them as the assay's measurement limit and excludes them: haptoglobin (7 samples at 17,907,000
  ng/mL), IFN-α2 (4 at 120.88 pg/mL) and IL-28A (5 at 15.56 pg/mL).
- The Alamar files differ from the Eve files: the sample column is `Sample ID` in the serum file,
  markers are gene symbols (`il6`, `tnf`, `cxcl8`), values are `<marker>_concentration_npq` (NULISA
  protein quantification, log2-scale: +1 NPQ is about double) and the `_percent_normalized_value`
  columns are ignored. Gene symbols are matched to the curated names (`il6` is IL-6, `cxcl10` is
  IP-10), so the AI review sees both panels' measurements of a marker.
- Below-detection check: in assays without clinical ranges, a value of exactly 0 means "not
  detected", not a measured zero, so it is excluded (4 serum and 131 urine readings).
- The urine file has two columns with blank headers; they are ignored.
- These crew are separate people from AURA's synthetic demo crew; the two are never mixed.

### Adding more research files

Any other CSV in `data/osdr/` that uses the same layout (a `Sample Name` or `Sample ID` column with
names like `C001_serum_L-3`, and `<analyte>_value_<unit>` or `<analyte>_concentration_<unit>`
columns, with optional `_range_min_` and `_range_max_` columns) is picked up automatically as an
**added** dataset: a new tab in the Real crew data panel, labelled "added data", and included in the
AI review. Crew codes can be any letters and digits (`P01`). A file AURA can't read is listed with
the reason (`GET /api/research` → `problem`) instead of being skipped silently, and an edited file
is read again without a restart.

## Your own data (CSV import)

Click **⬆ Import** in the crew sidebar to add a crew member from your own readings, for example
a week of wearable and blood-pressure data. Records are labelled `imported`.

```csv
day,heart_rate,systolic_bp,diastolic_bp,sleep_hours,mood
-7,61,118,76,7.1,8
-6,60,117,75,7.4,8
-5,62,119,77,6.9,7
1,64,121,78,6.4,7
```

- `day` -7 to -1 is preflight and becomes your personal baseline (3 or more days per indicator);
  1, 2, 3... are mission days. There is no day 0.
- Use any of the indicator keys (`heart_rate`, `systolic_bp`, `diastolic_bp`, `spo2`, `glucose`,
  `body_temp`, `sleep_hours`, `mood`, `exercise_minutes`, `radiation_dose`) or common aliases
  such as `hr`, `sbp`, `sleep`. A long layout (`day,indicator,value`) also works.
- Blank cells are skipped; values outside the plausible range are rejected with the line number.
- A full example is in `data/import_template.csv` (also at `GET /api/crew/import/template`).
- Real exports work too, and AURA lists everything it converted, averaged or skipped:
  - a `date` column instead of `day` (ISO dates or timestamps, `DD.MM.YYYY`, or slash dates when the
    file shows which part is the day). Set **Launch date** in the import form (API: `launch_date`)
    to the date that becomes mission day 1; otherwise the mission start date is used. Dates more
    than 60 days before launch or after the mission's current day are skipped;
  - `;` or tab separators, and decimal commas in those files;
  - units in headers (`Heart rate (bpm)`, `Sleep [min]`, `temp_f`) or cells (`98%`, `7 h`), and
    other units converted to AURA's: °F, glucose in mmol/L, sleep in minutes, SpO2 as a fraction,
    exercise in hours, radiation in µSv. With no unit, only values impossible in AURA's unit trigger
    a conversion (temperature above 50, glucose below 30, sleep above 24, SpO2 at or below 1);
  - blood pressure in one column (`120/80`), and a `unit` column in the long layout;
  - several readings on one day: averaged, or added up for sleep, exercise and radiation dose.
- Sample files in these formats, with custom indicator definitions, are in `data/samples/`.
- Imported data lives in memory with the rest of the mission and keeps through crew edits and
  environment changes, but not a back-end restart.

## Custom indicators

Use **+ Add indicator** to track any extra measurement. You set the name, unit, typical
range, optional warning and critical limits, the body system, the related NASA hazards and
whether it uses a personal baseline. Custom limits are the user's own, not clinically
validated, and each custom indicator says so in its references. Synthetic crew get synthetic
readings for it around the middle of the typical range. These come from a separate random
stream, so the built-in demo data never changes. To include it in a CSV import, add a column
named after its key, for example `body_weight`.

## Synthetic telemetry

The crew is editable in the dashboard (✎ Edit crew): name, role, age, personal baselines and a
health scenario (nominal, behavioural → cardio, immune fever, circadian disruption, exercise
deconditioning). Scenarios are anchored to the end of the mission, so the story always finishes
on the current day.

`backend/aura/simulator.py` generates a deterministic (seeded) mission timeline for a small
crew. It models the documented direction of in-flight change, for example:

- Fluid shift and cardiovascular deconditioning: small drift in resting heart rate and
  blood pressure.
- Circadian disruption: shorter sleep than on Earth (ISS crews often average about 6 h).
- Isolation and confinement: gradual mood/stress drift, with scripted "events".
- Radiation: a steady daily dose, plus solar particle event spikes.

Demo scenarios are injected on purpose (for example, declining sleep and mood that precede a
cardiovascular warning) so the alert engine has something meaningful to show. **None of these
values are real astronaut measurements.**

## Threshold references

The thresholds live in `backend/aura/indicators.py`. Each indicator lists a `references`
field. All thresholds are **prototype rules** and are not clinically validated.

## Symptoms, signal delay and radiation budget

- **Symptom triage** (`backend/aura/symptoms.py`) uses fixed prototype rules informed by NASA HRP
  evidence: red flags escalate, vision changes are treated as possible Spaceflight-Associated
  Neuro-ocular Syndrome (SANS), and motion sickness, fluid-shift congestion and back pain are
  expected only in the first days of flight. Demo symptom logs are synthetic and tagged `demo`.
- **Signal delay** (`backend/aura/comms.py`): ISS about 0.5 s via the TDRS relay; Moon 1.28 s
  (384,400 km at the speed of light); Mars transit grows from about 0.2 to 12.5 minutes one way
  (1.5 AU at mission end), within the real Earth-Mars range of about 3 to 22 minutes. The
  flight-surgeon reply is a simulated, rule-based template.
- **Radiation budget** (`backend/aura/radiation.py`): NASA-STD-3001 Volume 1 Rev B 600 mSv career
  effective dose limit, and the 30-day (250 mGy-Eq) and 1-year (500 mGy-Eq) blood-forming organ
  limits. Dosimeter mSv is compared with the mGy-Eq limits as an approximation. Prior career doses
  of the demo crew (410, 95 and 0 mSv) are invented for the story.
