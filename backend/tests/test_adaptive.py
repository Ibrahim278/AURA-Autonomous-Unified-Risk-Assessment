import pytest
from fastapi.testclient import TestClient

from aura import main
from aura.simulator import generate
from aura.store import ADAPT_MAX_SHIFT_SD, MissionStore


@pytest.fixture(autouse=True)
def fresh():
    main.store.load(generate())
    yield
    main.store.baseline_mode = "preflight"


client = TestClient(main.app)


def test_default_is_preflight():
    s = MissionStore(generate())
    assert s.baseline("aura-1", "heart_rate", 60).kind == "preflight"


def test_adaptive_learns_in_flight_but_falls_back_early():
    s = MissionStore(generate())
    s.baseline_mode = "adaptive"
    assert s.baseline("aura-1", "body_temp", 10).kind == "preflight"  # too few in-flight days yet
    b = s.baseline("aura-1", "body_temp", 60)
    pre = s._baselines[("aura-1", "body_temp")]
    assert b.kind == "adaptive" and b.mean > pre.mean  # core temperature runs warmer in flight


def test_shift_is_clamped_so_slow_drift_is_still_caught():
    s = MissionStore(generate())
    s.baseline_mode = "adaptive"
    for cid in s.crew:
        for key in ("heart_rate", "sleep_hours", "systolic_bp", "mood"):
            pre = s._baselines.get((cid, key))
            b = s.baseline(cid, key, 60)
            if pre and b:
                assert abs(b.mean - pre.mean) <= ADAPT_MAX_SHIFT_SD * pre.sd + 1e-9
    # The demo stories survive: Kenji still warns, Diallo is still critical.
    assert s.status("aura-2")["overall"] == "warning"
    assert s.status("aura-3")["overall"] == "critical"
    hr50 = next(i for i in s.status("aura-2", 50)["indicators"] if i["indicator"] == "heart_rate")
    assert hr50["level"] == "warning" and hr50["baseline"]["kind"] == "adaptive"


def test_api_toggle():
    assert client.get("/api/mission/baseline-mode").json()["mode"] == "preflight"
    assert client.put("/api/mission/baseline-mode", json={"mode": "adaptive"}).json()["mode"] == "adaptive"
    assert client.get("/api/mission").json()["baseline_mode"] == "adaptive"
    s = client.get("/api/crew/aura-1/status").json()
    assert next(i for i in s["indicators"] if i["indicator"] == "body_temp")["baseline"]["kind"] == "adaptive"
    assert client.put("/api/mission/baseline-mode", json={"mode": "other"}).status_code == 422
