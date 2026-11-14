import pytest
from fastapi.testclient import TestClient

from aura import custom, importer, main
from aura.simulator import generate

client = TestClient(main.app)

WEIGHT = {"name": "Body weight", "unit": "kg", "body_system": "musculoskeletal",
          "hazards": ["gravity_fields"], "adverse_direction": "low",
          "typical_low": 68, "typical_high": 74, "warning_low": 64, "critical_low": 60, "decimals": 1}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(custom, "STORE_PATH", tmp_path / "custom.json")
    custom.clear()
    main.store.load(generate())
    yield
    custom.clear()
    main.store.load(generate())


def test_add_custom_indicator_flows_everywhere():
    before = client.get("/api/crew/aura-2/telemetry?indicators=heart_rate").json()
    r = client.post("/api/indicators", json=WEIGHT)
    assert r.status_code == 201 and r.json()["key"] == "body_weight" and r.json()["custom"] is True
    # Built-in synthetic data is unchanged by adding an indicator.
    assert client.get("/api/crew/aura-2/telemetry?indicators=heart_rate").json() == before
    st = client.get("/api/crew/aura-1/status").json()
    w = next(i for i in st["indicators"] if i["indicator"] == "body_weight")
    assert w["baseline"] is not None and w["value"] is not None
    # Check-in a low weight: critical limit applies.
    st = client.post("/api/crew/aura-1/checkins", json={"values": {"body_weight": 58}}).json()
    assert next(i for i in st["indicators"] if i["indicator"] == "body_weight")["level"] == "critical"
    # CSV import recognises it.
    readings, _ = importer.parse_csv("day,body_weight\n-3,70\n-2,70.4\n-1,69.8\n1,69\n", 60)
    assert readings[0][0] == "body_weight"
    # Persisted, and survives a mission regenerate.
    assert custom.STORE_PATH.exists()
    client.post("/api/mission/reset", json={"environment": "iss"})
    assert client.get("/api/crew/aura-3/telemetry?indicators=body_weight").json()["series"]["body_weight"]["points"]


def test_delete_custom_only():
    client.post("/api/indicators", json=WEIGHT)
    assert client.delete("/api/indicators/heart_rate").status_code == 422
    assert client.delete("/api/indicators/body_weight").status_code == 200
    assert all(i["key"] != "body_weight" for i in client.get("/api/indicators").json())
    assert client.delete("/api/indicators/body_weight").status_code == 404


@pytest.mark.parametrize("patch", [
    {"typical_low": 80},                      # low above high
    {"warning_low": 70},                      # inside typical range
    {"warning_low": 60, "critical_low": 64},  # critical inside warning
    {"name": "Resting heart rate"},           # clashes with built-in
])
def test_invalid_specs_rejected(patch):
    assert client.post("/api/indicators", json={**WEIGHT, **patch}).status_code == 422


def test_saved_definitions_reload(tmp_path):
    client.post("/api/indicators", json=WEIGHT)
    custom.clear()
    assert custom.load_saved(custom.STORE_PATH) == ["body_weight"]
