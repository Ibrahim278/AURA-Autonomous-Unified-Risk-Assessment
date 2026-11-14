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

Crew C001–C004, sampled at L-92, L-44 and L-3 (days before launch) and R+1, R+45, R+82 and
R+194 (days after return). `backend/aura/research.py` parses the files, keeps each value and the
lab's own per-sample reference range, and flags it low, normal or high. API:
`GET /api/research` and `GET /api/research/{cmp|cbc}`; every response has `source: research`.

Notes on interpretation:
- An out-of-range value alone is not a diagnosis. The low glucose of three crew at R+45 may
  reflect sample handling (for example delayed processing), so AURA shows it without comment.
- The CBC file labels haemoglobin as `percent`; the values and ranges are clearly g/dL, so the
  UI shows g/dL and says so.
- Quality check: in a CBC, absolute neutrophils must equal WBC × neutrophil %. The published
  C003 L-92 row breaks this (10.1/µL vs about 6,826/µL expected) and several red-cell indices are
  shifted too, so AURA excludes that whole sample from charts and the AI review and says why.
- These crew are separate people from AURA's synthetic demo crew; the two are never mixed.

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
