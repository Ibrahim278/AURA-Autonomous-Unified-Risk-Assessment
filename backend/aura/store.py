"""In-memory mission store: holds telemetry, baselines and manual check-ins.

Kept in memory on purpose so the demo is zero-setup. It's easy to swap for SQLite later.
"""

from __future__ import annotations

import threading
from bisect import insort
from collections import defaultdict
from datetime import datetime, timezone

from .alerts import Assessment, Baseline, Level, Reading, assess, body_system_rollup, overall_level
from .indicators import INDICATORS
from .simulator import DEFAULTS, MissionDataset, generate


class UnknownCrewError(KeyError):
    pass


class MissionStore:
    def __init__(self, dataset: MissionDataset):
        self._lock = threading.Lock()
        self.load(dataset)

    # ------------------------------------------------------------------ loading
    def load(self, dataset: MissionDataset) -> None:
        with self._lock:
            self.dataset = dataset
            self.current_day = dataset.days
            self.crew = {c.id: c for c in dataset.crew}
            self._preflight: dict[tuple[str, str], list[float]] = defaultdict(list)
            self._inflight: dict[tuple[str, str], list[Reading]] = defaultdict(list)
            self.notes: dict[str, list[dict]] = defaultdict(list)
            self.task_completions: dict[str, dict[int, set[str]]] = {}
            for r in dataset.records:
                key = (r.crew_id, r.indicator)
                if r.phase == "preflight":
                    self._preflight[key].append(r.value)
                else:
                    self._inflight[key].append(Reading(r.day, r.value, r.source, r.timestamp))
            for readings in self._inflight.values():
                readings.sort(key=lambda r: r.day)
            self._baselines = {
                key: Baseline.from_values(values, INDICATORS[key[1]])
                for key, values in self._preflight.items()
            }

    @classmethod
    def from_config(cls, days: int, environment: str, seed: int) -> "MissionStore":
        return cls(generate(days=days, environment=environment, seed=seed))

    # ------------------------------------------------------------------ queries
    def _require(self, crew_id: str) -> None:
        if crew_id not in self.crew:
            raise UnknownCrewError(crew_id)

    def baseline(self, crew_id: str, indicator: str) -> Baseline | None:
        return self._baselines.get((crew_id, indicator))

    def readings(self, crew_id: str, indicator: str, up_to_day: int | None = None) -> list[Reading]:
        self._require(crew_id)
        rs = self._inflight.get((crew_id, indicator), [])
        if up_to_day is None:
            return list(rs)
        return [r for r in rs if r.day <= up_to_day]

    def preflight(self, crew_id: str, indicator: str) -> list[float]:
        self._require(crew_id)
        return list(self._preflight.get((crew_id, indicator), []))

    def assessments(self, crew_id: str, day: int | None = None) -> list[Assessment]:
        self._require(crew_id)
        day = self.current_day if day is None else day
        return [
            assess(ind, self.readings(crew_id, key, day), self.baseline(crew_id, key))
            for key, ind in INDICATORS.items()
        ]

    def status(self, crew_id: str, day: int | None = None) -> dict:
        day = self.current_day if day is None else day
        assessments = self.assessments(crew_id, day)
        overall = overall_level(assessments)
        counts = {lvl.label: sum(a.level is lvl for a in assessments) for lvl in Level}
        return {
            "crew_id": crew_id,
            "day": day,
            "overall": overall.label,
            "escalate": any(a.escalate for a in assessments),
            "counts": counts,
            "indicators": [a.to_dict() for a in assessments],
            "body_systems": body_system_rollup(assessments),
        }

    def alert_timeline(self, crew_id: str, from_day: int = 1) -> list[dict]:
        """Days on which an indicator *changed* level, for an event feed."""
        self._require(crew_id)
        events: list[dict] = []
        for key, ind in INDICATORS.items():
            rs = self.readings(crew_id, key)
            base = self.baseline(crew_id, key)
            prev = Level.NORMAL
            for i in range(len(rs)):
                a = assess(ind, rs[: i + 1], base)
                if a.level != prev and rs[i].day >= from_day:
                    events.append(
                        {
                            "day": rs[i].day,
                            "indicator": key,
                            "name": ind.name,
                            "from": prev.label,
                            "to": a.level.label,
                            "value": a.to_dict()["value"],
                            "unit": ind.unit,
                            "reason": a.reasons[0] if a.reasons else "",
                        }
                    )
                prev = a.level
        events.sort(key=lambda e: (e["day"], e["indicator"]))
        return events

    # ------------------------------------------------------------------ writes
    def add_checkin(
        self, crew_id: str, values: dict[str, float], day: int | None = None, note: str | None = None
    ) -> int:
        """Record manual readings. A manual reading replaces any reading for that day."""
        self._require(crew_id)
        unknown = set(values) - set(INDICATORS)
        if unknown:
            raise ValueError(f"Unknown indicators: {sorted(unknown)}")
        day = self.current_day if day is None else day
        if day < 1:
            raise ValueError("Check-ins are for in-flight days (day >= 1)")
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            for key, raw in values.items():
                _, _, lo, hi = DEFAULTS[key]
                if not lo <= raw <= hi:
                    raise ValueError(f"{key}={raw} is outside the plausible range {lo} to {hi}")
            for key, raw in values.items():
                value = round(float(raw), INDICATORS[key].decimals)
                rs = self._inflight[(crew_id, key)]
                rs[:] = [r for r in rs if r.day != day]
                insort(rs, Reading(day, value, "manual", ts), key=lambda r: r.day)
            if note:
                self.notes[crew_id].append({"day": day, "timestamp": ts, "note": note})
            self.current_day = max(self.current_day, day)
        return day
