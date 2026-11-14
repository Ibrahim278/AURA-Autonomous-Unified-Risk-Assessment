"""Synthetic astronaut telemetry generator.

ALL DATA PRODUCED HERE IS SYNTHETIC. It is not real astronaut data. Records carry
``source="synthetic"``.

The generator models the *documented direction* of in-flight change (see
docs/DATA_SOURCES.md) and injects scripted demo scenarios so the alert engine has meaningful
events to show. It is deterministic for a given seed.

Usage (exports CSV + JSON for the team / front end):

    python -m aura.simulator --out ../data --days 60 --environment lunar_surface
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from .indicators import INDICATORS

PREFLIGHT_DAYS = 7  # baseline data collection days before launch: -7 .. -1

# Typical daily dose by environment (mSv/day).
ENVIRONMENTS: dict[str, dict] = {
    "iss": {
        "name": "International Space Station (low Earth orbit)",
        "radiation_mSv_day": 0.5,
        "gravity_g": 0.0,
        "source": "NASA HRP: ISS crews receive roughly 0.5 to 1 mSv/day",
    },
    "lunar_surface": {
        "name": "Lunar surface base",
        "radiation_mSv_day": 1.37,
        "gravity_g": 0.165,
        "source": "Zhang et al., Science Advances 6 (2020), Chang'e 4 LND: 1.37 mSv/day",
    },
    "mars_transit": {
        "name": "Mars transit vehicle (deep space)",
        "radiation_mSv_day": 1.84,
        "gravity_g": 0.0,
        "source": "Zeitlin et al., Science 340 (2013), MSL RAD cruise: 1.84 mSv/day",
    },
}

# Per-indicator noise model: (default mean, day-to-day SD, clip min, clip max)
DEFAULTS: dict[str, tuple[float, float, float, float]] = {
    "heart_rate": (62, 2.5, 30, 200),
    "systolic_bp": (117, 4.0, 60, 240),
    "diastolic_bp": (75, 3.0, 35, 150),
    "spo2": (98, 0.6, 70, 100),
    "glucose": (88, 5.0, 30, 400),
    "body_temp": (36.6, 0.15, 34, 42),
    "sleep_hours": (7.2, 0.3, 0, 12),
    "mood": (8, 0.7, 1, 10),
    "exercise_minutes": (125, 10, 0, 240),
    "radiation_dose": (0.0, 0.0, 0, 500),  # set by environment
}

OffsetFn = Callable[[int, int], dict[str, float]]  # (day, mission_days) -> indicator offsets


@dataclass
class CrewMember:
    id: str
    name: str
    role: str
    age: int
    scenario: str
    scenario_description: str
    baseline_means: dict[str, float] = field(default_factory=dict)
    offset_fn: OffsetFn | None = field(default=None, repr=False, compare=False)
    # (indicator, day, value) readings uploaded by the user; replaces simulation for this member.
    imported: list[tuple[str, int, float]] | None = field(default=None, repr=False, compare=False)

    def public(self) -> dict:
        d = asdict(self)
        d.pop("offset_fn")
        imported = d.pop("imported")
        d["baseline"] = d.pop("baseline_means")
        d["data_source"] = "imported" if imported is not None else "synthetic"
        d["imported_readings"] = len(imported) if imported is not None else 0
        return d


def _ramp(day: int, start: int, rate: float, cap: float) -> float:
    """Linear change starting on ``start`` at ``rate``/day, capped at ``cap`` (signed)."""
    if day < start:
        return 0.0
    v = (day - start + 1) * rate
    return max(v, cap) if cap < 0 else min(v, cap)


def _late(days: int, before_end: int) -> int:
    """A day ``before_end`` days before the end of the mission (never before day 2).

    Scenarios are anchored to the end of the mission so the story always finishes on the
    current day, whatever the mission length. For the default 60 days these are the original days.
    """
    return max(2, days - before_end)


def _in_flight_adaptation(day: int) -> dict[str, float]:
    """Small, expected changes every crew member shows in flight (day >= 1)."""
    if day < 1:
        return {}
    return {
        "sleep_hours": -0.25,  # shorter sleep in flight (Barger 2014)
        "body_temp": min(0.01 * day, 0.25),  # slow core-temperature rise (Stahn 2017)
        "heart_rate": 1.0,
    }


def _scenario_nominal(day: int, days: int) -> dict[str, float]:
    return {}


def _scenario_behavioural_cardio(day: int, days: int) -> dict[str, float]:
    """Sleep declines, then mood, then exercise slips, then heart rate and BP rise."""
    return {
        "sleep_hours": _ramp(day, _late(days, 28), -0.11, -2.1),
        "mood": _ramp(day, _late(days, 24), -0.2, -4.0),
        "exercise_minutes": _ramp(day, _late(days, 20), -3.5, -60),
        "heart_rate": _ramp(day, _late(days, 18), 0.95, 17),
        "systolic_bp": _ramp(day, _late(days, 15), 1.6, 26),
        "diastolic_bp": _ramp(day, _late(days, 15), 0.9, 15),
        "glucose": _ramp(day, _late(days, 16), 0.9, 14),
    }


def _scenario_immune_fever(day: int, days: int) -> dict[str, float]:
    """Viral reactivation: fever and raised heart rate building over the last days."""
    steps = [0.3, 0.6, 0.9, 1.3, 1.7, 2.1, 2.5]
    i = day - (days - len(steps) + 1)
    fever = steps[i] if 0 <= i < len(steps) else 0.0
    return {
        "body_temp": fever,
        "heart_rate": fever * 9,
        "sleep_hours": -fever * 0.5,
        "mood": -fever * 0.8,
        "spo2": -fever * 0.8,
    }


def _scenario_circadian(day: int, days: int) -> dict[str, float]:
    """Shift work and light exposure erode sleep early; mood dips but the body copes."""
    return {
        "sleep_hours": _ramp(day, _late(days, 45), -0.06, -1.6),
        "mood": _ramp(day, _late(days, 30), -0.08, -1.8),
    }


def _scenario_deconditioning(day: int, days: int) -> dict[str, float]:
    """Exercise countermeasures slip, so resting heart rate and glucose creep up."""
    return {
        "exercise_minutes": _ramp(day, _late(days, 40), -2.2, -75),
        "heart_rate": _ramp(day, _late(days, 30), 0.45, 11),
        "glucose": _ramp(day, _late(days, 25), 0.6, 13),
        "diastolic_bp": _ramp(day, _late(days, 25), 0.3, 6),
    }


SCENARIOS: dict[str, dict] = {
    "nominal": {"label": "Nominal", "fn": _scenario_nominal,
                "description": "Adapts well. Only expected in-flight changes."},
    "behavioural_cardio": {"label": "Behavioural → cardio", "fn": _scenario_behavioural_cardio,
                           "description": (
                               "Sleep starts to decline about four weeks before the current day, then "
                               "mood drops and exercise slips, and resting heart rate and blood pressure "
                               "climb. Shows how AURA catches a behavioural-health pattern before it "
                               "becomes a cardiovascular event.")},
    "immune_fever": {"label": "Immune: fever", "fn": _scenario_immune_fever,
                     "description": ("Latent viral reactivation causes a fever that builds over the last "
                                     "week and becomes critical, with a raised heart rate and falling SpO2.")},
    "circadian": {"label": "Circadian disruption", "fn": _scenario_circadian,
                  "description": "Sleep slowly erodes from mid-mission and mood dips, without vital-sign changes."},
    "deconditioning": {"label": "Exercise deconditioning", "fn": _scenario_deconditioning,
                       "description": ("Exercise sessions get shorter, then resting heart rate, glucose and "
                                       "diastolic pressure creep up: the cost of skipped countermeasures.")},
}

# Personal baselines a user may set per crew member (others use DEFAULTS).
EDITABLE_BASELINES = ("heart_rate", "systolic_bp", "diastolic_bp", "glucose", "body_temp", "sleep_hours", "mood")


def make_member(id: str, name: str, role: str, age: int, scenario: str = "nominal",
                baseline: dict[str, float] | None = None) -> CrewMember:
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {sorted(SCENARIOS)}")
    baseline = baseline or {}
    bad = [k for k in baseline if k not in EDITABLE_BASELINES]
    if bad:
        raise ValueError(f"baseline can only set {list(EDITABLE_BASELINES)}, not {bad}")
    for k, v in baseline.items():
        _, _, lo, hi = DEFAULTS[k]
        if not lo <= v <= hi:
            raise ValueError(f"baseline {k}={v} is outside {lo}-{hi}")
    sc = SCENARIOS[scenario]
    return CrewMember(id=id, name=name, role=role, age=age, scenario=scenario,
                      scenario_description=sc["description"], baseline_means=dict(baseline),
                      offset_fn=sc["fn"])


DEFAULT_CREW_SPECS: list[dict] = [
    {"id": "aura-1", "name": "Cmdr. Lena Ortiz", "role": "Commander", "age": 44, "scenario": "nominal",
     "baseline": {"heart_rate": 58, "systolic_bp": 114, "sleep_hours": 7.0}},
    {"id": "aura-2", "name": "Dr. Kenji Sato", "role": "Flight Engineer", "age": 39,
     "scenario": "behavioural_cardio",
     "baseline": {"heart_rate": 63, "systolic_bp": 119, "diastolic_bp": 77, "mood": 8}},
    {"id": "aura-3", "name": "Amara Diallo", "role": "Mission Specialist", "age": 35,
     "scenario": "immune_fever",
     "baseline": {"heart_rate": 60, "glucose": 85, "sleep_hours": 7.4, "body_temp": 36.5}},
]


def default_crew() -> list[CrewMember]:
    return [make_member(**{**spec, "baseline": dict(spec["baseline"])}) for spec in DEFAULT_CREW_SPECS]


CREW: list[CrewMember] = default_crew()

SPE_DAY = 22  # Solar particle event affecting the whole crew
SPE_DOSE = {21: 0.4, 22: 12.0, 23: 3.1, 24: 0.8}


@dataclass(frozen=True)
class TelemetryRecord:
    crew_id: str
    indicator: str
    day: int
    phase: str  # preflight | inflight
    timestamp: str
    value: float
    source: str = "synthetic"


@dataclass
class MissionDataset:
    mission_name: str
    environment: str
    environment_info: dict
    start_date: str
    days: int
    seed: int
    crew: list[CrewMember]
    records: list[TelemetryRecord]

    def meta(self) -> dict:
        return {
            "mission_name": self.mission_name,
            "environment": self.environment,
            "environment_info": self.environment_info,
            "start_date": self.start_date,
            "days": self.days,
            "current_day": self.days,
            "preflight_days": PREFLIGHT_DAYS,
            "seed": self.seed,
            "data_notice": "All telemetry is SYNTHETIC unless a record's source says otherwise.",
        }


def _timestamp(start: date, day: int) -> str:
    # Day 1 is the launch / arrival day; preflight days are negative.
    offset = day - 1 if day >= 1 else day
    dt = datetime.combine(start + timedelta(days=offset), time(7, 0), tzinfo=timezone.utc)
    return dt.isoformat()


def generate(
    days: int = 60,
    environment: str = "lunar_surface",
    seed: int = 42,
    start_date: date | None = None,
    mission_name: str = "AURA Demo Mission",
    crew: list[CrewMember] | None = None,
) -> MissionDataset:
    crew = default_crew() if crew is None else crew
    if not crew:
        raise ValueError("the crew needs at least one member")
    if environment not in ENVIRONMENTS:
        raise ValueError(f"environment must be one of {sorted(ENVIRONMENTS)}")
    env = ENVIRONMENTS[environment]
    start = start_date or date(2026, 11, 14)
    rng = np.random.default_rng(seed)
    records: list[TelemetryRecord] = []

    for member in crew:
        if member.imported is not None:
            records.extend(imported_records(member, start))
            continue
        for day in [*range(-PREFLIGHT_DAYS, 0), *range(1, days + 1)]:
            offsets: dict[str, float] = {}
            for src in (_in_flight_adaptation(day), member.offset_fn(day, days) if day >= 1 else {}):
                for k, v in src.items():
                    offsets[k] = offsets.get(k, 0.0) + v

            for key, ind in INDICATORS.items():
                mean, sd, lo, hi = DEFAULTS[key]
                mean = member.baseline_means.get(key, mean)
                if key == "radiation_dose":
                    # Preflight on Earth ~0.01 mSv/day; in flight per environment + SPE.
                    base = 0.01 if day < 1 else env["radiation_mSv_day"]
                    spe = SPE_DOSE.get(day, 0.0) if day >= 1 and environment != "iss" else 0.0
                    value = base * rng.normal(1.0, 0.06) + spe
                else:
                    value = rng.normal(mean + offsets.get(key, 0.0), sd)
                value = float(np.clip(value, lo, hi))
                value = round(value, ind.decimals)
                records.append(
                    TelemetryRecord(
                        crew_id=member.id,
                        indicator=key,
                        day=day,
                        phase="preflight" if day < 1 else "inflight",
                        timestamp=_timestamp(start, day),
                        value=value,
                    )
                )

    return MissionDataset(
        mission_name=mission_name,
        environment=environment,
        environment_info=env,
        start_date=start.isoformat(),
        days=days,
        seed=seed,
        crew=crew,
        records=records,
    )


def imported_records(member: CrewMember, start: date) -> list[TelemetryRecord]:
    return [TelemetryRecord(crew_id=member.id, indicator=key, day=day,
                            phase="preflight" if day < 1 else "inflight",
                            timestamp=_timestamp(start, day), value=value, source="imported")
            for key, day, value in member.imported or []]


def export(dataset: MissionDataset, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "synthetic_telemetry.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(dataset.records[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(r) for r in dataset.records)
    meta_path = out_dir / "mission.json"
    meta_path.write_text(
        json.dumps({**dataset.meta(), "crew": [c.public() for c in dataset.crew]}, indent=2)
    )
    return [csv_path, meta_path]


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic AURA mission telemetry.")
    p.add_argument("--out", type=Path, default=Path("data"))
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--environment", choices=sorted(ENVIRONMENTS), default="lunar_surface")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    ds = generate(days=args.days, environment=args.environment, seed=args.seed)
    for path in export(ds, args.out):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
