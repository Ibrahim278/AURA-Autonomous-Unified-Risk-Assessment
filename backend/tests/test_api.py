import pytest
from fastapi.testclient import TestClient

from aura import main
from aura.simulator import generate


@pytest.fixture(autouse=True)
def fresh_store():
    main.store.load(generate())
    yield


client = TestClient(main.app)


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_mission_and_reference():
    m = client.get("/api/mission").json()
    assert m["current_day"] == 60 and "SYNTHETIC" in m["data_notice"]
    inds = client.get("/api/indicators").json()
    assert {i["key"] for i in inds} >= {"heart_rate", "sleep_hours", "mood", "glucose"}
    assert all(i["references"] for i in inds)
    hz = client.get("/api/hazards").json()
    assert "radiation_dose" in hz["space_radiation"]


def test_crew_overview_levels():
    crew = {c["id"]: c for c in client.get("/api/crew").json()}
    assert crew["aura-1"]["overall"] == "normal"
    assert crew["aura-2"]["overall"] == "warning"
    assert crew["aura-3"]["overall"] == "critical"
    assert crew["aura-3"]["escalate"] is True


def test_status_shape_and_body_rollup():
    s = client.get("/api/crew/aura-3/status").json()
    assert s["overall"] == "critical"
    assert s["body_systems"]["immune"]["level"] == "critical"
    temp = next(i for i in s["indicators"] if i["indicator"] == "body_temp")
    assert temp["actions"] and temp["escalate"]


def test_status_on_earlier_day():
    s = client.get("/api/crew/aura-2/status", params={"day": 10}).json()
    assert s["overall"] == "normal"


def test_telemetry():
    t = client.get(
        "/api/crew/aura-2/telemetry", params={"indicators": "heart_rate,radiation_dose"}
    ).json()
    hr = t["series"]["heart_rate"]
    assert len(hr["points"]) == 60 and len(hr["preflight"]) == 7
    assert hr["baseline"]["mean"] > 0
    assert t["series"]["radiation_dose"]["baseline"] is None
    assert client.get("/api/crew/aura-2/telemetry", params={"indicators": "nope"}).status_code == 422


def test_alert_feed_contains_spe_and_scenario():
    events = client.get("/api/crew/aura-2/alerts").json()
    assert any(e["indicator"] == "radiation_dose" and e["to"] == "critical" for e in events)
    assert any(e["indicator"] == "sleep_hours" and e["to"] == "warning" for e in events)


def test_manual_checkin_updates_status():
    r = client.post(
        "/api/crew/aura-1/checkins",
        json={"values": {"heart_rate": 140}, "note": "felt dizzy after EVA"},
    )
    assert r.status_code == 201
    s = r.json()
    hr = next(i for i in s["indicators"] if i["indicator"] == "heart_rate")
    assert hr["level"] == "critical" and hr["source"] == "manual"
    assert s["overall"] == "critical"


def test_checkin_advances_day():
    r = client.post("/api/crew/aura-1/checkins", json={"values": {"mood": 7}, "day": 61})
    assert r.json()["day"] == 61
    assert client.get("/api/mission").json()["current_day"] == 61


def test_checkin_validation():
    assert client.post("/api/crew/aura-1/checkins", json={"values": {"nope": 1}}).status_code == 422
    assert client.post("/api/crew/aura-1/checkins", json={"values": {"mood": 50}}).status_code == 422
    assert client.post("/api/crew/ghost/checkins", json={"values": {"mood": 5}}).status_code == 404


def test_reset_environment():
    m = client.post("/api/mission/reset", json={"environment": "iss", "days": 30}).json()
    assert m["environment"] == "iss" and m["current_day"] == 30
    assert client.post("/api/mission/reset", json={"environment": "venus"}).status_code == 422


def test_edit_crew_regenerates_mission():
    from aura.simulator import DEFAULT_CREW_SPECS
    opts = client.get("/api/crew-options").json()
    assert {s["key"] for s in opts["scenarios"]} >= {"nominal", "immune_fever", "deconditioning"}
    r = client.put("/api/mission/crew", json={"crew": [
        {"id": "aura-1", "name": "Ibrahim Test", "role": "Commander", "age": 30, "scenario": "immune_fever",
         "baseline": {"heart_rate": 55}},
        {"name": "New Member", "scenario": "nominal"},
    ]})
    assert r.status_code == 200
    crew = {c["id"]: c for c in r.json()}
    assert set(crew) == {"aura-1", "aura-2"}
    assert crew["aura-1"]["name"] == "Ibrahim Test" and crew["aura-1"]["overall"] == "critical"
    assert crew["aura-2"]["overall"] == "normal"
    t = client.get("/api/crew/aura-1/telemetry?indicators=heart_rate").json()
    pre = t["series"]["heart_rate"]["preflight"]
    assert abs(sum(pre) / len(pre) - 55) < 3
    bad = client.put("/api/mission/crew", json={"crew": [{"name": "X", "scenario": "nope"}]})
    assert bad.status_code == 422
    bad = client.put("/api/mission/crew", json={"crew": [{"name": "X", "baseline": {"spo2": 90}}]})
    assert bad.status_code == 422
    assert client.put("/api/mission/crew", json={"crew": DEFAULT_CREW_SPECS}).status_code == 200


def test_shorter_mission_still_tells_the_scenario_story():
    from aura.simulator import generate
    from aura.store import MissionStore
    s = MissionStore(generate(days=30))
    assert s.status("aura-3")["overall"] == "critical"


def test_next_day_extends_mission_without_changing_history():
    from aura.simulator import generate
    main.store.load(generate())
    before = client.get("/api/crew/aura-2/telemetry?indicators=heart_rate").json()["series"]["heart_rate"]["points"]
    m = client.post("/api/mission/next-day").json()
    assert m["current_day"] == 61
    after = client.get("/api/crew/aura-2/telemetry?indicators=heart_rate").json()["series"]["heart_rate"]["points"]
    assert after[:-1] == before and after[-1]["day"] == 61
    # The fever persists past the planned end, and a check-in lands on the new day.
    assert client.get("/api/crew/aura-3/status").json()["overall"] == "critical"
    st = client.post("/api/crew/aura-1/checkins", json={"values": {"mood": 3}}).json()
    assert st["day"] == 61
    assert client.get("/api/crew/aura-1/tasks").json()["day"] == 61
    main.store.load(generate())
