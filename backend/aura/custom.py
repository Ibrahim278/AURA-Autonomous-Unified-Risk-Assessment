"""User-defined (custom) indicators, e.g. body weight, hydration, HRV or step count.

A custom indicator is a full AURA indicator: it gets personal-baseline alerts, absolute limits,
charts, check-ins, CSV import and AI context, exactly like the built-in ten. Definitions are
saved to ``data/custom_indicators.json`` so they survive a back-end restart (readings don't).

Synthetic crew members get synthetic readings for a new indicator, drawn around the middle of
its typical range from a separate random stream, so adding one never changes the built-in data.
"""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field, model_validator

from .indicators import BUILTIN_KEYS, INDICATORS, BodySystem, Direction, Hazard, Indicator, Limits
from .simulator import DEFAULTS

STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "custom_indicators.json"
MAX_CUSTOM = 12


class CustomIndicatorSpec(BaseModel):
    name: str = Field(..., min_length=2, max_length=40, examples=["Body weight"])
    unit: str = Field(..., min_length=1, max_length=16, examples=["kg"])
    body_system: BodySystem = BodySystem.WHOLE_BODY
    hazards: list[Hazard] = Field(default_factory=list)
    adverse_direction: Direction = Direction.BOTH
    typical_low: float = Field(..., description="Low end of a healthy, typical value")
    typical_high: float = Field(..., description="High end of a healthy, typical value")
    warning_low: float | None = None
    warning_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    decimals: int = Field(1, ge=0, le=3)
    min_meaningful_change: float | None = Field(None, gt=0, description="Default: 10% of the typical range")
    use_baseline: bool = True
    why_it_matters: str = Field("", max_length=600)
    how_to_measure: str = Field("", max_length=400)

    @model_validator(mode="after")
    def _check_order(self):
        if self.typical_low >= self.typical_high:
            raise ValueError("typical_low must be below typical_high")
        lows = [v for v in (self.critical_low, self.warning_low) if v is not None]
        highs = [v for v in (self.warning_high, self.critical_high) if v is not None]
        if lows != sorted(lows) or highs != sorted(highs):
            raise ValueError("critical limits must sit outside warning limits")
        if any(v >= self.typical_low for v in lows) or any(v <= self.typical_high for v in highs):
            raise ValueError("warning and critical limits must sit outside the typical range")
        return self

    @property
    def key(self) -> str:
        return re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")


def _build(spec: CustomIndicatorSpec) -> Indicator:
    span = spec.typical_high - spec.typical_low
    return Indicator(
        key=spec.key, name=spec.name, unit=spec.unit, body_system=spec.body_system,
        hazards=tuple(spec.hazards), adverse_direction=spec.adverse_direction,
        limits=Limits(spec.warning_low, spec.warning_high, spec.critical_low, spec.critical_high),
        min_meaningful_change=spec.min_meaningful_change or round(span * 0.1, 3),
        decimals=spec.decimals,
        why_it_matters=spec.why_it_matters or "Custom indicator added by the crew.",
        how_to_measure=spec.how_to_measure or "Measure at the same time each day, under the same conditions.",
        actions={
            "warning": ["Re-measure to confirm the reading.",
                        "Note anything that changed today (sleep, food, exercise, stress)."],
            "critical": ["Re-measure now and note any symptoms.", "Contact the flight surgeon."],
        },
        references=("Custom indicator: limits set by the user, not clinically validated.",),
        use_baseline=spec.use_baseline, custom=True,
    )


def _noise_model(spec: CustomIndicatorSpec) -> tuple[float, float, float, float]:
    span = spec.typical_high - spec.typical_low
    mean = (spec.typical_low + spec.typical_high) / 2
    lo = min(v for v in (spec.critical_low, spec.warning_low, spec.typical_low - 3 * span) if v is not None)
    hi = max(v for v in (spec.critical_high, spec.warning_high, spec.typical_high + 3 * span) if v is not None)
    if spec.typical_low >= 0:
        lo = max(lo, 0.0)  # a non-negative quantity stays non-negative
    return (mean, span / 8, lo, hi)


_specs: dict[str, CustomIndicatorSpec] = {}


def register(spec: CustomIndicatorSpec, persist: bool = True) -> Indicator:
    key = spec.key
    if not key:
        raise ValueError("the name needs at least one letter or digit")
    if key in BUILTIN_KEYS or spec.name.strip().lower() in {INDICATORS[k].name.lower() for k in BUILTIN_KEYS}:
        raise ValueError(f"'{spec.name}' is already a built-in indicator")
    if key not in _specs and len(_specs) >= MAX_CUSTOM:
        raise ValueError(f"at most {MAX_CUSTOM} custom indicators")
    ind = _build(spec)
    INDICATORS[key] = ind
    DEFAULTS[key] = _noise_model(spec)
    _specs[key] = spec
    if persist:
        save()
    return ind


def unregister(key: str) -> None:
    if key not in _specs:
        raise KeyError(key)
    del _specs[key], INDICATORS[key], DEFAULTS[key]
    save()


def specs() -> dict[str, CustomIndicatorSpec]:
    return dict(_specs)


def save() -> None:
    try:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STORE_PATH.write_text(json.dumps([s.model_dump(mode="json") for s in _specs.values()], indent=2))
    except OSError:
        pass  # read-only deploy: keep them in memory only


def load_saved(path: Path = STORE_PATH) -> list[str]:
    """Register saved definitions; returns the keys loaded (bad entries are skipped)."""
    if not path.exists():
        return []
    loaded = []
    try:
        items = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    for item in items:
        try:
            loaded.append(register(CustomIndicatorSpec(**item), persist=False).key)
        except ValueError:
            continue
    return loaded


def clear() -> None:
    """Remove every custom indicator from memory (tests)."""
    for key in list(_specs):
        del _specs[key], INDICATORS[key], DEFAULTS[key]


def synthetic_series(key: str, crew_id: str, days: list[int], seed: int, baseline: float | None = None) -> list[float]:
    """Readings for one synthetic crew member, from a stream independent of the built-in data."""
    mean, sd, lo, hi = DEFAULTS[key]
    mean = baseline if baseline is not None else mean
    rng = np.random.default_rng([seed, zlib.crc32(f"{crew_id}:{key}".encode())])
    dec = INDICATORS[key].decimals
    return [round(float(np.clip(rng.normal(mean, sd), lo, hi)), dec) for _ in days]
