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
