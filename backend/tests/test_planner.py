import pytest
from fastapi.testclient import TestClient

from aura import main, planner
from aura.simulator import generate


@pytest.fixture(autouse=True)
def fresh():
    main.store.load(generate())
    yield


client = TestClient(main.app)


def ids(p):
    return {b["id"]: b for b in p["blocks"]}


def test_fever_suspends_exercise():
    p = planner.plan(main.store, "aura-3")
    b = ids(p)
    assert "rest" in b and "aerobic" not in b and "resistive" not in b
    assert p["exercise_minutes"] == 0 and p["summary"].startswith("Rest day")


def test_sato_plan_adapts_to_his_flags():
    b = ids(planner.plan(main.store, "aura-2"))
    assert b["aerobic"]["changed"] and "No intervals" in b["aerobic"]["detail"]
    assert b["light"]["indicator"] == "sleep_hours"
    assert b["sleep"]["minutes"] == 510 and "winddown" in b
    assert "walk" in b  # glucose warning
    assert "social" in b  # mood warning


def test_nominal_day_and_radiation_block():
    p = planner.plan(main.store, "aura-1", day=30)
    b = ids(p)
    assert not any(x["changed"] for x in p["blocks"]) and p["summary"].startswith("Standard day")
    assert p["exercise_minutes"] == 105
    assert "shield" in ids(planner.plan(main.store, "aura-1"))  # live: radiation budget warning


def test_back_pain_lightens_resistive():
    client.post("/api/crew/aura-1/symptoms", json={"symptoms": [{"key": "back_pain", "severity": 4}]})
    r = ids(client.get("/api/crew/aura-1/plan").json())["resistive"]
    assert r["changed"] and "Lighter loads" in r["detail"]


def test_toggle_block():
    r = client.post("/api/crew/aura-1/plan/aerobic/toggle").json()
    assert ids(r)["aerobic"]["done"] is True
    r = client.post("/api/crew/aura-1/plan/aerobic/toggle").json()
    assert ids(r)["aerobic"]["done"] is False
    assert client.post("/api/crew/aura-1/plan/nope/toggle").status_code == 404
