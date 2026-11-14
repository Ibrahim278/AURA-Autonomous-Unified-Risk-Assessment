import pytest
from fastapi.testclient import TestClient

from aura import main
from aura.simulator import generate

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_store():
    main.store.load(generate())


def tasks(crew="aura-2"):
    return client.get(f"/api/crew/{crew}/tasks").json()


def by_id(r):
    return {t["id"]: t for t in r["tasks"]}


def test_manual_tasks_pending_auto_tasks_done():
    t = by_id(tasks("aura-1"))
    assert t["wearable"]["done"] and t["dosimeter"]["done"]
    assert not t["vitals"]["done"] and not t["mood"]["done"]


def test_followups_only_for_spot_measurements():
    t = by_id(tasks("aura-2"))
    assert "followup_heart_rate" in t and "followup_systolic_bp" in t
    assert "followup_sleep_hours" not in t and "followup_exercise_minutes" not in t
    assert "call_home" in t  # sleep/mood warnings -> behavioural wellness tasks


def test_critical_adds_flight_surgeon_task():
    assert "call_surgeon" in by_id(tasks("aura-3"))


def test_checkin_completes_tasks_streak_and_badges():
    before = tasks()
    client.post("/api/crew/aura-2/checkins", json={"values": {
        "systolic_bp": 130, "diastolic_bp": 84, "body_temp": 36.7, "glucose": 95,
        "mood": 6, "heart_rate": 70}})
    after = tasks()
    t = by_id(after)
    assert t["vitals"]["done"] and t["glucose"]["done"] and t["mood"]["done"]
    assert t["followup_heart_rate"]["done"]  # stays listed (ticked) even if HR is now normal
    assert after["streaks"]["checkin"] == before["streaks"]["checkin"] + 1
    assert after["level"]["points"] > before["level"]["points"]
    earned = {b["id"] for b in after["badges"] if b["earned"]}
    assert {"self_aware", "early_catch"} <= earned


def test_exercise_streak_broken_in_behavioural_scenario():
    assert tasks("aura-2")["streaks"]["exercise"] < tasks("aura-1")["streaks"]["exercise"]


def test_wellness_tick_and_validation():
    r = client.post("/api/crew/aura-2/tasks/call_home/complete").json()
    assert by_id(r)["call_home"]["done"]
    assert client.post("/api/crew/aura-2/tasks/vitals/complete").status_code == 422
