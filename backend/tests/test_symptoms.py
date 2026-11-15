import pytest
from fastapi.testclient import TestClient

from aura import main, symptoms
from aura.simulator import generate


@pytest.fixture(autouse=True)
def fresh():
    main.store.load(generate())
    yield


client = TestClient(main.app)


def tri(items, day=30, history=None):
    entries = [{"key": k, "severity": v} for k, v in items]
    return symptoms.triage(entries, history or [{"day": day, "symptoms": entries}], day)


def test_red_flag_is_critical():
    t = tri([("chest_pain", 3)])
    assert t["level"] == "critical" and t["escalate"]
    assert "flight surgeon now" in t["actions"][0]


def test_early_adaptation_is_normal_but_late_nausea_warns():
    assert tri([("nausea", 5)], day=2)["level"] == "normal"
    assert tri([("nausea", 5)], day=20)["level"] == "warning"
    assert tri([("congestion", 3)], day=1)["level"] == "normal"


def test_sans_pattern_and_severity():
    t = tri([("headache", 4), ("blurred_vision", 3)])
    assert t["level"] == "warning" and any("SANS" in r for r in t["reasons"])
    assert tri([("headache", 7)])["level"] == "warning"
    assert tri([("headache", 9)])["level"] == "critical"
    assert tri([("headache", 3)])["level"] == "normal"


def test_persistence_raises_warning():
    hist = [{"day": d, "symptoms": [{"key": "insomnia", "severity": 4}]} for d in (27, 28, 30)]
    t = symptoms.triage([{"key": "insomnia", "severity": 4}], hist, 30)
    assert t["level"] == "warning" and any("3 of the last 5" in r for r in t["reasons"])


def test_related_indicators():
    t = tri([("chills", 5)])
    assert t["related_indicators"][0] == "body_temp"


def test_demo_seed_matches_scenarios():
    r = client.get("/api/crew/aura-3/symptoms").json()
    assert r["triage"]["level"] == "warning"  # chills + persistent fatigue
    assert r["log"][0]["day"] == 60 and r["log"][0]["source"] == "synthetic"
    assert client.get("/api/crew/aura-1/symptoms").json()["triage"]["level"] == "normal"
    assert client.get("/api/crew/aura-1/symptoms?day=1").json()["log"][0]["symptoms"][0]["name"]


def test_api_log_and_validation():
    r = client.post("/api/crew/aura-1/symptoms", json={"symptoms": [{"key": "breathing", "severity": 5}], "note": "after EVA"})
    assert r.status_code == 201 and r.json()["triage"]["level"] == "critical"
    assert r.json()["log"][0]["source"] == "manual"
    assert client.post("/api/crew/aura-1/symptoms", json={"symptoms": [{"key": "nope", "severity": 5}]}).status_code == 422
    assert client.post("/api/crew/aura-1/symptoms", json={"symptoms": [{"key": "headache", "severity": 11}]}).status_code == 422
    assert client.post("/api/crew/aura-1/symptoms", json={"symptoms": [{"key": "headache", "severity": 3}], "day": 99}).status_code == 422
    assert len(client.get("/api/symptoms/catalog").json()) == len(symptoms.CATALOG)


def test_offline_assistant_escalates_red_flags():
    from aura import assistant

    r = assistant.offline_reply("I have chest pain and feel dizzy", {"person": None})
    assert r.escalate and r.topic == "health" and r.answer.startswith("Contact the flight surgeon now")
    assert {a.type for a in r.actions} == {"message_ground", "open_symptoms"}
    assert assistant.offline_reply("how do I log a symptom", {"person": None}).actions[0].type == "open_symptoms"
