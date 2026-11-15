from fastapi.testclient import TestClient

from aura import ai, forecast, main
from aura.simulator import generate
from aura.store import MissionStore

client = TestClient(main.app)


def test_forecast_catches_heart_rate_before_the_alert():
    s = MissionStore(generate())
    hr = s.status("aura-2", 48)
    assert next(a for a in hr["indicators"] if a["indicator"] == "heart_rate")["level"] == "normal"
    risks = {r["indicator"]: r for r in forecast.forecast(s, "aura-2", 48)["risks"]}
    assert risks["heart_rate"]["crossing"]["in_days"] <= 3
    # ...and the rule engine does flag it two days later.
    assert next(a for a in s.status("aura-2", 50)["indicators"] if a["indicator"] == "heart_rate")["level"] == "warning"


def test_nominal_crew_has_no_risks():
    s = MissionStore(generate())
    assert forecast.forecast(s, "aura-1", 60)["risks"] == []
    assert forecast.forecast(s, "aura-2", 30)["risks"] == []


def test_forecast_endpoint_and_projection_shape():
    main.store.load(generate())
    r = client.get("/api/crew/aura-2/forecast?day=48").json()
    assert r["horizon_days"] == 14 and r["risks"]
    proj = r["series"]["heart_rate"]
    assert [p["day"] for p in proj] == list(range(48, 56))
    assert client.get("/api/crew/nobody/forecast").status_code == 404


def test_ai_context_includes_forecast():
    main.store.load(generate())
    ctx = ai.build_context(main.store, "aura-2", 48)
    assert any(f["indicator"] == "heart_rate" for f in ctx["forecast"])


def test_confidence_band_and_crossing_range():
    s = MissionStore(generate())
    f = forecast.forecast(s, "aura-2", 48)
    proj = f["series"]["heart_rate"]
    assert all(p["lo"] <= p["value"] <= p["hi"] for p in proj)
    widths = [p["hi"] - p["lo"] for p in proj]
    assert widths[-1] > widths[0]  # less certain further ahead
    hr = next(r for r in f["risks"] if r["indicator"] == "heart_rate")
    lo, hi = hr["crossing"]["range"]
    assert lo is not None and lo <= hr["crossing"]["in_days"] and (hi is None or hi >= hr["crossing"]["in_days"])


def test_related_trends_follow_the_story():
    s = MissionStore(generate())
    rel = forecast.forecast(s, "aura-3", 60)["related"]
    # Fever: heart rate climbs with body temperature.
    top = rel["heart_rate"][0]
    assert top["indicator"] == "body_temp" and top["r"] > 0.8 and top["together"] == "same direction"
    assert forecast.forecast(s, "aura-1", 60)["related"] == {}  # nominal crew: no spurious links
