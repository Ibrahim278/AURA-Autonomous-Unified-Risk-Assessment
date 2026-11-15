from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from aura import main
from aura.simulator import generate


@pytest.fixture(autouse=True)
def fresh():
    main.store.load(generate())
    main.outbox.clear()
    yield


client = TestClient(main.app)


def test_overview_sorted_by_priority():
    g = client.get("/api/ground").json()
    assert [r["crew_id"] for r in g["crew"]][0] == "aura-3"  # critical fever first
    by = {r["crew_id"]: r for r in g["crew"]}
    assert by["aura-3"]["priority"] == "critical" and by["aura-3"]["escalate"]
    # Ortiz's telemetry is normal, but her radiation budget is at warning, so ground sees warning.
    assert by["aura-1"]["overall"] == "normal" and by["aura-1"]["priority"] == "warning"
    assert by["aura-1"]["radiation"]["career_used_pct"] > 80
    assert by["aura-2"]["flagged"] and by["aura-2"]["flagged"][0]["level"] == "warning"
    assert sum(g["counts"].values()) == 3


def test_replay_day_and_forecast():
    by = {r["crew_id"]: r for r in client.get("/api/ground?day=48").json()["crew"]}
    assert by["aura-2"]["forecast"][0]["indicator"] == "heart_rate"


def test_ground_sees_messages_only_after_arrival():
    link = main._link()
    main.outbox.send("aura-2", "Dr. Kenji Sato", "Can't sleep", "urgent", 60, link, None,
                     now=datetime.now(timezone.utc) - timedelta(seconds=10))
    main.outbox.send("aura-2", "Dr. Kenji Sato", "Still awake", "routine", 60, {**link, "one_way_s": 6000}, None)
    m = {r["crew_id"]: r for r in client.get("/api/ground").json()["crew"]}["aura-2"]["messages"]
    assert m["received"] == 1 and m["urgent"] == 1 and m["in_transit"] == 1
    assert m["last"]["text"] == "Can't sleep"


def test_reports_are_printable_html():
    r = client.get("/api/crew/aura-3/report")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    html = r.text
    assert "Amara Diallo" in html and "Body temperature" in html and "Save as PDF" in html
    assert "ESCALATE" in html and "SYNTHETIC" in html
    full = client.get("/api/report?day=50").text
    assert full.index("Dr. Kenji Sato") > 0 and "mission day 50" in full
    assert client.get("/api/crew/nobody/report").status_code == 404


def test_report_escapes_user_text():
    client.post("/api/crew/aura-1/symptoms", json={"symptoms": [{"key": "headache", "severity": 3}]})
    main.outbox.send("aura-1", "Cmdr. Lena Ortiz", "<script>x</script>", "routine", 60,
                     {**main._link(), "one_way_s": 0}, None)
    html = client.get("/api/crew/aura-1/report").text
    assert "<script>x" not in html and "&lt;script&gt;" in html
