import pytest
from fastapi.testclient import TestClient

from aura import main, wellbeing
from aura.simulator import generate
from aura.store import MissionStore

client = TestClient(main.app)


@pytest.fixture
def s():
    return MissionStore(generate())


def test_early_mission_crew_is_thriving(s):
    o = wellbeing.overview(s, 30)
    assert o["crew_band"] == "thriving" and all(m["band"] == "thriving" for m in o["members"])


def test_end_of_mission_flags_who_needs_support(s):
    o = wellbeing.overview(s, 60)
    by = {m["crew_id"]: m for m in o["members"]}
    assert by["aura-2"]["band"] == "support" and by["aura-1"]["band"] == "thriving"
    assert o["members"][0]["crew_id"] == "aura-2"  # lowest score first
    assert any("mood" in d for d in by["aura-2"]["drivers"])
    assert any("Dr. Kenji Sato" in t for t in o["suggestions"])
    assert by["aura-2"]["score"] >= 15  # each part is capped


def test_series_and_api():
    main.store.load(generate())
    r = client.get("/api/wellbeing?day=45").json()
    assert r["day"] == 45 and len(r["series"]["mood"]) == 30
    assert set(r["names"]) == {"aura-1", "aura-2", "aura-3"}
    assert r["series"]["mood"][-1]["crew"] is not None
