import pytest
from fastapi.testclient import TestClient

from aura import main, radiation
from aura.simulator import generate


@pytest.fixture(autouse=True)
def fresh():
    main.store.load(generate())
    yield


client = TestClient(main.app)


def test_budget_adds_prior_and_mission_dose():
    b = radiation.budget(main.store, "aura-3")
    mission = sum(r.value for r in main.store.readings("aura-3", "radiation_dose"))
    assert b["prior_mSv"] == 0 and b["mission_mSv"] == pytest.approx(mission, abs=0.1)
    assert b["career_mSv"] == pytest.approx(b["mission_mSv"], abs=0.1)
    assert b["cumulative"][-1]["mSv"] == pytest.approx(b["career_mSv"], abs=0.2)
    assert 22 in b["spe_days"]  # the scripted solar particle event


def test_veteran_commander_gets_budget_warning():
    b = radiation.budget(main.store, "aura-1")
    assert b["prior_mSv"] == 410
    assert b["career_used_pct"] >= 80 and b["level"] == "warning"
    assert any("career limit" in r for r in b["reasons"])


def test_rookie_is_normal_and_rate_excludes_storms():
    b = radiation.budget(main.store, "aura-3")
    assert b["level"] == "normal"
    assert b["rate_mSv_day"] == pytest.approx(1.37, abs=0.15)  # lunar surface background


def test_spe_day_is_critical():
    b = radiation.budget(main.store, "aura-3", day=22)
    assert b["level"] == "critical" and any("solar particle" in r for r in b["reasons"])


def test_projection_warns_before_limit():
    main.store.load(generate(days=200))  # a long mission
    main.store.crew["aura-2"].prior_dose_mSv = 400  # under 80% now, but the mission will push it past 600
    b = radiation.budget(main.store, "aura-2", day=10)
    assert b["career_used_pct"] < 80 and b["projected_end_mSv"] >= 600
    assert b["level"] == "warning" and b["days_to_limit"] is not None


def test_api_and_crew_editor_field():
    r = client.get("/api/crew/aura-1/radiation?day=30").json()
    assert r["day"] == 30 and r["career_limit_mSv"] == 600
    crew = client.get("/api/crew-options").json()["default_crew"]
    crew[2]["prior_dose_mSv"] = 250
    assert client.put("/api/mission/crew", json={"crew": crew}).status_code == 200
    assert client.get("/api/crew/aura-3/radiation").json()["prior_mSv"] == 250
    crew[2]["prior_dose_mSv"] = -5
    assert client.put("/api/mission/crew", json={"crew": crew}).status_code == 422
