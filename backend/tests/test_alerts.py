from aura.alerts import Baseline, Level, Reading, assess, body_system_rollup, overall_level
from aura.indicators import INDICATORS

HR = INDICATORS["heart_rate"]
SLEEP = INDICATORS["sleep_hours"]
RAD = INDICATORS["radiation_dose"]


def readings(values, start_day=1):
    return [Reading(day=start_day + i, value=v) for i, v in enumerate(values)]


def hr_baseline():
    return Baseline.from_values([60, 62, 61, 59, 60, 61, 60], HR)


def test_normal_when_close_to_baseline():
    a = assess(HR, readings([61, 60, 62, 61]), hr_baseline())
    assert a.level is Level.NORMAL
    assert a.actions == []
    assert not a.escalate


def test_absolute_critical_overrides_everything():
    a = assess(HR, readings([60, 61, 135]), hr_baseline())
    assert a.level is Level.CRITICAL
    assert a.escalate
    assert any("critical limit" in r for r in a.reasons)
    assert a.actions == HR.actions["critical"]


def test_absolute_warning():
    a = assess(HR, readings([60, 61, 104]), hr_baseline())
    assert a.level is Level.WARNING


def test_sustained_deviation_warns_inside_earth_normal_range():
    # 72-74 bpm is a normal resting HR on Earth, but ~12 bpm above this astronaut's baseline.
    a = assess(HR, readings([61, 72, 73, 74]), hr_baseline())
    assert a.level is Level.WARNING
    assert any("personal baseline" in r for r in a.reasons)


def test_single_moderate_rise_is_not_sustained():
    a = assess(HR, readings([61, 60, 66]), hr_baseline())
    assert a.level is Level.NORMAL


def test_single_large_spike_warns():
    a = assess(HR, readings([61, 60, 85]), hr_baseline())
    assert a.level is Level.WARNING
    assert any("Re-measure" in r for r in a.reasons)


def test_non_adverse_direction_is_ignored():
    # More sleep than baseline is not a problem.
    base = Baseline.from_values([6.5, 6.8, 7.0, 6.6, 6.9], SLEEP)
    a = assess(SLEEP, readings([8.5, 8.7, 8.9]), base)
    assert a.level is Level.NORMAL


def test_sleep_decline_warns():
    base = Baseline.from_values([7.0, 7.2, 6.9, 7.1, 7.0], SLEEP)
    a = assess(SLEEP, readings([7.0, 5.9, 5.8, 5.7]), base)
    assert a.level is Level.WARNING
    assert a.trend == "falling"


def test_radiation_spike_critical():
    base = Baseline.from_values([0.5, 0.55, 0.52, 0.5], RAD)
    a = assess(RAD, readings([0.5, 0.52, 12.0]), base)
    assert a.level is Level.CRITICAL


def test_no_readings():
    a = assess(HR, [], hr_baseline())
    assert a.level is Level.NORMAL
    assert a.value is None


def test_rollup_and_overall():
    a1 = assess(HR, readings([60, 61, 135]), hr_baseline())
    a2 = assess(RAD, readings([0.5, 0.5, 0.5]), Baseline.from_values([0.5, 0.5, 0.5], RAD))
    assert overall_level([a1, a2]) is Level.CRITICAL
    rollup = body_system_rollup([a1, a2])
    assert rollup["heart"]["level"] == "critical"
    assert rollup["whole_body"]["level"] == "normal"
    assert rollup["brain"]["indicators"] == []
