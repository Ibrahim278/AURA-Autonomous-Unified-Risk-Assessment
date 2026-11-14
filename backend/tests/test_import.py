import pytest
from fastapi.testclient import TestClient

from aura import importer, main
from aura.simulator import DEFAULT_CREW_SPECS, generate

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_store():
    main.store.load(generate())
    yield
    main.store.load(generate())


def test_template_imports_cleanly():
    readings, warnings = importer.parse_csv(importer.template(), 60)
    assert warnings == []
    assert {d for _, d, _ in readings} == {*range(-7, 0), *range(1, 11)}


def test_long_layout_aliases_and_blanks():
    text = "Day,Indicator,Value\n-3,HR,60\n-2,hr,61\n-1,pulse,62\n1,hr,\n2,hr,75\n"
    readings, warnings = importer.parse_csv(text, 60)
    assert readings == [("heart_rate", -3, 60), ("heart_rate", -2, 61), ("heart_rate", -1, 62),
                        ("heart_rate", 2, 75)]


@pytest.mark.parametrize("text,msg", [
    ("heart_rate\n60\n", "'day' column"),
    ("day,heart_rate\n0,60\n", "no day 0"),
    ("day,heart_rate\n99,60\n", "after the end"),
    ("day,heart_rate\n1,900\n", "plausible range"),
    ("day,heart_rate\n-1,60\n", "at least one mission day"),
    ("day,foo\n1,2\n", "No indicator columns"),
])
def test_helpful_errors(text, msg):
    with pytest.raises(importer.ImportError_, match=msg):
        importer.parse_csv(text, 60)


def test_few_preflight_days_warns_but_imports():
    readings, warnings = importer.parse_csv("day,mood\n-1,8\n1,7\n", 60)
    assert len(readings) == 2 and "no personal baseline" in warnings[0]


def test_import_endpoint_adds_member_and_keeps_others():
    main.store.add_checkin("aura-1", {"mood": 9})
    r = client.post("/api/crew/import", json={"name": "My Data", "role": "Pilot", "age": 30,
                                              "csv": importer.template()})
    assert r.status_code == 201, r.text
    m = r.json()["member"]
    assert m["id"] == "aura-4" and m["data_source"] == "imported"
    assert main.store.readings("aura-1", "mood")[-1].source == "manual"  # check-ins kept
    t = client.get("/api/crew/aura-4/telemetry?indicators=heart_rate").json()["series"]["heart_rate"]
    assert t["baseline"] is not None and t["points"][0]["source"] == "imported"
    # Editing the profile keeps the imported data.
    specs = [*DEFAULT_CREW_SPECS, {"id": "aura-4", "name": "Renamed", "age": 31}]
    crew = {c["id"]: c for c in client.put("/api/mission/crew", json={"crew": specs}).json()}
    assert crew["aura-4"]["name"] == "Renamed" and crew["aura-4"]["imported_readings"] == r.json()["readings"]


def test_import_rejects_bad_csv():
    r = client.post("/api/crew/import", json={"name": "X", "csv": "day,heart_rate\n0,60\n"})
    assert r.status_code == 422 and "day 0" in r.json()["detail"]
