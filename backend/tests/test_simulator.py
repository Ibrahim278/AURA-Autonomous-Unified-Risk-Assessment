from collections import defaultdict

from aura.alerts import Baseline, Level, Reading, assess
from aura.indicators import INDICATORS
from aura.simulator import CREW, PREFLIGHT_DAYS, generate


def _levels(ds, crew_id, key):
    recs = [r for r in ds.records if r.crew_id == crew_id and r.indicator == key]
    ind = INDICATORS[key]
    base = Baseline.from_values([r.value for r in recs if r.phase == "preflight"], ind)
    inflight = [Reading(r.day, r.value) for r in recs if r.phase == "inflight"]
    return [assess(ind, inflight[: i + 1], base).level for i in range(len(inflight))]


def test_shape_and_labels():
    ds = generate(days=60)
    assert len(ds.records) == len(CREW) * len(INDICATORS) * (PREFLIGHT_DAYS + 60)
    assert all(r.source == "synthetic" for r in ds.records)


def test_deterministic():
    assert generate(seed=7).records == generate(seed=7).records


def test_values_within_physical_bounds():
    ds = generate()
    by = defaultdict(list)
    for r in ds.records:
        by[r.indicator].append(r.value)
    assert all(1 <= v <= 10 for v in by["mood"])
    assert all(v <= 100 for v in by["spo2"])
    assert all(v >= 0 for v in by["sleep_hours"])


def test_nominal_astronaut_is_quiet():
    ds = generate()
    for key in INDICATORS:
        if key == "radiation_dose":
            continue
        levels = _levels(ds, "aura-1", key)
        assert sum(lvl > Level.NORMAL for lvl in levels) <= 2, key


def test_behavioural_scenario_sleep_warns_before_heart():
    ds = generate()
    sleep = _levels(ds, "aura-2", "sleep_hours")
    hr = _levels(ds, "aura-2", "heart_rate")
    first = lambda xs: next(i for i, lvl in enumerate(xs) if lvl >= Level.WARNING)  # noqa: E731
    assert first(sleep) < first(hr)
    assert hr[-1] >= Level.WARNING


def test_fever_scenario_ends_critical():
    ds = generate()
    assert _levels(ds, "aura-3", "body_temp")[-1] is Level.CRITICAL
