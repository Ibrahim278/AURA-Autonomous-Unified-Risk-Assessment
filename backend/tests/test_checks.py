import pytest
from fastapi.testclient import TestClient

from aura import checks, main
from aura.simulator import generate


@pytest.fixture(autouse=True)
def fresh():
    main.store.load(generate())
    yield


client = TestClient(main.app)


def test_unit_mixups_are_errors_with_hints():
    r = checks.check(main.store, "aura-1", {"body_temp": 98.6, "glucose": 5.4, "sleep_hours": 420})
    hints = {e["indicator"]: e["hint"] for e in r["errors"]}
    assert "37.0 °C" in hints["body_temp"]
    assert "97 mg/dL" in hints["glucose"]
    assert "7.0 h" in hints["sleep_hours"]
    assert {e["indicator"]: e["suggested"] for e in r["errors"]}["body_temp"] == 37.0
    assert not r["ok"]


def test_far_from_baseline_and_jump_warn():
    r = checks.check(main.store, "aura-1", {"heart_rate": 110})
    assert not r["errors"] and "SD above your baseline" in r["warnings"][0]["message"]
    ok = checks.check(main.store, "aura-1", {"heart_rate": 60, "sleep_hours": 7.0})
    assert ok["ok"]


def test_swapped_blood_pressure():
    r = checks.check(main.store, "aura-1", {"systolic_bp": 75, "diastolic_bp": 118})
    assert any("swapped" in w["message"] for w in r["warnings"])


def test_api_check_and_save():
    r = client.post("/api/crew/aura-1/checkins/check", json={"values": {"body_temp": 98.6}}).json()
    assert r["errors"] and "°F" in r["errors"][0]["message"]
    bad = client.post("/api/crew/aura-1/checkins", json={"values": {"body_temp": 98.6}})
    assert bad.status_code == 422 and "37.0 °C" in bad.json()["detail"]
    # A warning doesn't block saving: the UI asks the astronaut to confirm first.
    assert client.post("/api/crew/aura-1/checkins", json={"values": {"heart_rate": 110}}).status_code == 201
