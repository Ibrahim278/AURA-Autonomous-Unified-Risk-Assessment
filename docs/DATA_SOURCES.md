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

## Synthetic telemetry

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
