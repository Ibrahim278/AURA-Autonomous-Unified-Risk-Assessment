from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from aura import comms, main
from aura.simulator import generate


@pytest.fixture(autouse=True)
def fresh():
    main.store.load(generate())
    main.outbox.clear()
    yield
    main.outbox.mode = "simulated"


client = TestClient(main.app)


def test_delay_by_environment():
    assert comms.one_way_seconds("iss", 10, 60) < 1
    assert comms.one_way_seconds("lunar_surface", 10, 60) == pytest.approx(1.3)
    early = comms.one_way_seconds("mars_transit", 1, 60)
    late = comms.one_way_seconds("mars_transit", 60, 60)
    assert early < 60 < late
    assert late / 60 == pytest.approx(1.5 * comms.LIGHT_MIN_PER_AU, rel=0.01)
    # past the planned end the distance stops growing
    assert comms.one_way_seconds("mars_transit", 90, 60) == late


def test_link_modes():
    assert comms.link_status("lunar_surface", 30, 60)["mode"] == "live"
    mars = comms.link_status("mars_transit", 60, 60)
    assert mars["mode"] == "autonomous" and mars["one_way"].endswith("min")
    assert mars["round_trip_s"] == pytest.approx(2 * mars["one_way_s"])


def test_reply_waits_for_round_trip():
    box = comms.Outbox()
    link = comms.link_status("mars_transit", 60, 60)
    t0 = datetime(2030, 1, 1, tzinfo=timezone.utc)
    status = main.store.status("aura-3")
    box.send("aura-3", "Amara Diallo", "I feel feverish", "urgent", 60, link, status, now=t0)
    msgs = box.thread("aura-3", now=t0)
    assert msgs[0]["direction"] == "to_ground" and msgs[0]["delivered"] is False
    assert msgs[1]["pending"] is True and "text" not in msgs[1]
    wait = (2 * link["one_way_s"] + comms.GROUND_HANDLING_S) / comms.DEMO_SPEED
    later = box.thread("aura-3", now=t0 + timedelta(seconds=wait + 0.1))
    assert later[0]["delivered"] and later[1]["pending"] is False
    assert "critical" in later[1]["text"] and later[1]["simulated"] is True
    assert box.thread("aura-1", now=t0) == []


def test_reply_without_status_packet():
    text = comms.ground_reply(None, "Lena Ortiz", "hello", "routine", 5)
    assert "No status packet" in text and "nominal" not in text


def test_api_send_and_reset_clears():
    r = client.post("/api/crew/aura-2/messages", json={"text": "Sleeping badly", "priority": "routine"})
    assert r.status_code == 201
    body = r.json()
    assert body["link"]["environment"] == "lunar_surface"
    sent = body["messages"][0]
    assert sent["status_packet"]["overall"] == "warning"
    assert any("Sleep" in f for f in sent["status_packet"]["flagged"])
    assert client.post("/api/crew/aura-2/messages", json={"text": ""}).status_code == 422
    assert client.post("/api/crew/nobody/messages", json={"text": "hi"}).status_code == 404
    client.post("/api/mission/reset", json={"environment": "mars_transit"})
    assert client.get("/api/crew/aura-2/messages").json()["messages"] == []
    assert client.get("/api/comms").json()["mode"] == "autonomous"


def test_live_ground_reply_travels_back_with_the_delay():
    box = comms.Outbox()
    box.mode = "live"
    link = comms.link_status("mars_transit", 60, 60)
    t0 = datetime(2030, 1, 1, tzinfo=timezone.utc)
    out = box.send("aura-3", "Amara Diallo", "Fever since this morning", "urgent", 60, link, None, now=t0)
    # live mode: no simulated reply is queued
    assert [m["direction"] for m in box.thread("aura-3", now=t0)] == ["to_ground"]
    # the console can't see or answer it before its signal reaches Earth
    assert box.inbox(now=t0) == ([], 1)
    with pytest.raises(ValueError):
        box.reply(out["id"], "Too early", "Dr. Reyes", now=t0)
    travel = timedelta(seconds=link["one_way_s"] / comms.DEMO_SPEED)
    t1 = t0 + travel + timedelta(seconds=1)
    inbox, in_transit = box.inbox(now=t1)
    assert in_transit == 0 and inbox[0]["id"] == out["id"] and inbox[0]["replies"] == []
    box.mark_seen(out["id"], now=t1)
    r = box.reply(out["id"], "Take paracetamol and rest. Re-measure in 1 h.", "Dr. Reyes", now=t1)
    assert r["simulated"] is False and r["author"] == "Dr. Reyes"
    crew_view = box.thread("aura-3", now=t1)
    assert crew_view[0]["seen_at"] and crew_view[1]["pending"] is True  # still on its way back
    later = box.thread("aura-3", now=t1 + travel + timedelta(seconds=0.1))
    assert later[1]["pending"] is False and later[1]["text"].startswith("Take paracetamol")


def test_live_ground_api():
    assert client.get("/api/comms/mode").json()["mode"] == "simulated"
    assert client.put("/api/comms/mode", json={"mode": "live"}).json()["mode"] == "live"
    assert client.put("/api/comms/mode", json={"mode": "robot"}).status_code == 422
    client.post("/api/mission/reset", json={"environment": "lunar_surface", "days": 60})
    client.post("/api/crew/aura-3/messages", json={"text": "Feverish", "priority": "urgent"})
    import time
    time.sleep(0.1)  # lunar delay on the demo clock is ~0.02 s
    box = client.get("/api/ground/inbox").json()
    assert box["mode"] == "live" and box["messages"][0]["crew_name"] == "Amara Diallo"
    mid = box["messages"][0]["id"]
    assert client.post(f"/api/ground/messages/{mid}/seen").status_code == 200
    r = client.post(f"/api/ground/messages/{mid}/reply", json={"text": "Rest and hydrate.", "author": "Dr. Reyes"})
    assert r.status_code == 201 and r.json()["simulated"] is False
    assert client.post("/api/ground/messages/9999/reply", json={"text": "x"}).status_code == 404
    assert client.post(f"/api/ground/messages/{mid}/reply", json={"text": ""}).status_code == 422
