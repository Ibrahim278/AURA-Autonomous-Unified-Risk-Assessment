"""Bring-your-own-data: real-world CSV formats and the sample files in data/samples/.

Each sample is imported through the API and then every endpoint is exercised for that person,
including mission changes (next day, a shorter mission, another environment), so new data can't
quietly break a panel.
"""

import csv
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aura import custom, importer, main
from aura.simulator import generate

client = TestClient(main.app)
SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
LAUNCH = "2026-10-01"
CREW_GETS = ["status", "telemetry", "forecast", "radiation", "plan", "symptoms", "alerts", "tasks", "report", "messages"]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(custom, "STORE_PATH", tmp_path / "custom.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path / "no-claude"))
    custom.clear()
    main.store.load(generate())
    yield
    custom.clear()
    main.store.load(generate())


def sample(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def add_sample_indicators():
    for spec in json.loads(sample("custom_indicators.json")):
        assert client.post("/api/indicators", json=spec).status_code == 201


def parse(text, days=60, launch=date(2026, 10, 1)):
    return importer.parse_csv(text, days, launch=launch)


# ------------------------------------------------------------------ formats seen in real exports
@pytest.mark.parametrize("text,expect", [
    # wearable export: dates instead of day numbers (launch 2026-10-01 is day 1)
    ("date,resting_heart_rate\n2026-09-28,60\n2026-09-29,61\n2026-09-30,59\n2026-10-01,64\n",
     {("heart_rate", -3): 60, ("heart_rate", -1): 59, ("heart_rate", 1): 64}),
    # ISO timestamps, units in headers
    ("Date,Heart Rate (bpm),Temp (°C)\n2026-09-30T06:40:00Z,60,36.6\n2026-10-02T06:40:00Z,62,36.8\n",
     {("heart_rate", -1): 60, ("body_temp", 2): 36.8}),
    # European Excel: ';' separator, decimal comma, day-first dates
    ("Date;heart_rate;body_temp\n30.09.2026;60;36,6\n01.10.2026;64;36,9\n",
     {("body_temp", -1): 36.6, ("body_temp", 1): 36.9}),
    # tab-separated
    ("day\theart_rate\n-1\t60\n1\t64\n", {("heart_rate", 1): 64}),
    # day-first slash dates, proven by a day > 12
    ("date,mood\n30/09/2026,8\n01/10/2026,7\n", {("mood", -1): 8, ("mood", 1): 7}),
    # month-first slash dates, proven by a day > 12
    ("date,mood\n09/30/2026,8\n10/01/2026,7\n", {("mood", -1): 8, ("mood", 1): 7}),
    # units inside cells
    ("day,spo2,sleep_hours\n-1,98%,7h\n1,96 %,6.5 hrs\n", {("spo2", -1): 98, ("sleep_hours", -1): 7}),
    # blood pressure in one column
    ("day,Blood pressure\n-1,118/76\n1,125/80\n", {("systolic_bp", 1): 125, ("diastolic_bp", 1): 80}),
    # unit suffixes in header names
    ("day,sleep_minutes,temp_f,glucose_mmol_l\n1,420,98.6,5.0\n",
     {("sleep_hours", 1): 7.0, ("body_temp", 1): 37.0, ("glucose", 1): 90}),
])
def test_real_world_formats(text, expect):
    readings, _ = parse(text)
    got = {(k, d): v for k, d, v in readings}
    for k, v in expect.items():
        assert got[k] == pytest.approx(v), k


@pytest.mark.parametrize("text,key,value,note", [
    ("day,body_temp\n-1,98.4\n1,99.1\n", "body_temp", 37.3, "°F to °C"),             # no unit: guessed
    ("day,glucose\n-1,4.9\n1,5.4\n", "glucose", 97, "mmol/L to mg/dL"),
    ("day,sleep\n-1,430\n1,390\n", "sleep_hours", 6.5, "minutes to hours"),
    ("day,spo2\n-1,0.98\n1,0.97\n", "spo2", 97, "fraction to %"),
    ("day,exercise (h)\n1,1.5\n", "exercise_minutes", 90, "hours to minutes"),
    ("day,indicator,value,unit\n1,dose,480,µSv\n", "radiation_dose", 0.48, "µSv to mSv"),
])
def test_unit_conversions_are_applied_and_reported(text, key, value, note):
    readings, warnings = parse(text)
    assert {(k, d): v for k, d, v in readings}[(key, 1)] == pytest.approx(value, abs=0.06)
    assert any(note in w for w in warnings), warnings


def test_mmhg_glucose_is_not_mistaken_for_mmol():
    readings, warnings = parse("day,glucose\n-1,88\n1,92\n")
    assert readings[-1][2] == 92 and not any("converted" in w for w in warnings)


def test_several_readings_per_day_are_averaged_or_summed():
    text = "day,indicator,value\n1,hr,60\n1,hr,70\n1,sleep,5\n1,sleep,1.5\n1,exercise,30\n1,exercise,45\n"
    readings, warnings = parse(text)
    got = {k: v for k, _, v in readings}
    assert got == {"heart_rate": 65, "sleep_hours": 6.5, "exercise_minutes": 75}
    assert any("daily average" in w for w in warnings) and any("daily total" in w for w in warnings)


def test_dates_outside_the_mission_are_skipped_with_a_note():
    text = "date,heart_rate\n2026-01-01,60\n2026-09-29,60\n2026-09-30,61\n2026-10-01,62\n2030-01-01,70\n"
    readings, warnings = parse(text)
    assert [d for _, d, _ in readings] == [-2, -1, 1]
    assert "2 preflight day(s) and 1 mission day(s)" in warnings[0] and "Skipped 2 row(s)" in warnings[1]


def test_extra_columns_are_listed_and_kept_once_defined():
    text = "day,heart_rate,Body weight (kg),Steps,Notes\n-1,60,70.1,8000,ok\n1,62,69.8,4000,\n"
    readings, warnings = parse(text)
    assert {k for k, _, _ in readings} == {"heart_rate"}
    assert "Body weight (kg), Steps" in warnings[0] and "+ Add indicator" in warnings[0]  # Notes ignored quietly
    add_sample_indicators()
    readings, warnings = parse(text)
    assert {k for k, _, _ in readings} == {"heart_rate", "body_weight"}


@pytest.mark.parametrize("text,msg", [
    ("date,mood\n03/04/2026,8\n", "day/month or month/day"),
    ("date,mood\n2026-13-45,8\n", "not a date"),
    ("date,mood\n2025-01-01,8\n2025-01-02,7\n", "none of them is a mission day"),
    ("day,heart_rate,pulse\n1,60,61\n", "Keep one"),
    ("day,bp\n1,120-80\n", "should look like 120/80"),
    ("day,sleep\n1,7h30\n", "not a number"),
    ("day,glucose (bpm)\n1,90\n", "unexpected unit"),
    ("day,indicator,value\n1,sleep,8\n1,sleep,8\n", "Is a day listed twice?"),
    ("day,body_temp\n-1,36.6\n1,98.6\n1,36.7\n", "plausible range"),  # one °F value among °C ones
])
def test_helpful_errors_for_messy_files(text, msg):
    with pytest.raises(importer.ImportError_, match=msg):
        parse(text)


# ------------------------------------------------------------------ the sample files, end to end
def import_sample(name, launch=LAUNCH):
    r = client.post("/api/crew/import", json={"name": name[:30], "csv": sample(name), "launch_date": launch})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize("name,indicators,notes", [
    ("wearable_export.csv", {"heart_rate", "hrv", "spo2", "sleep_hours", "exercise_minutes"},
     ["minutes to hours", "Steps"]),
    ("clinic_visits_eu.csv", {"systolic_bp", "diastolic_bp", "glucose", "body_temp", "body_weight"},
     ["mmol/L to mg/dL"]),
    ("lab_results_long.csv", {"heart_rate", "body_temp", "glucose", "radiation_dose", "grip_strength"},
     ["°F to °C", "µSv to mSv", "daily average", "daily total"]),
    ("analog_mission_60d.csv", {"heart_rate", "systolic_bp", "diastolic_bp", "spo2", "glucose", "body_temp",
                                "sleep_hours", "mood", "exercise_minutes", "radiation_dose", "body_weight", "hrv"}, []),
])
def test_sample_imports_and_every_endpoint_works(name, indicators, notes):
    add_sample_indicators()
    r = import_sample(name)
    cid = r["member"]["id"]
    assert set(r["indicators"]) == indicators
    for note in notes:
        assert any(note in w for w in r["warnings"]), (note, r["warnings"])
    for path in CREW_GETS:
        assert client.get(f"/api/crew/{cid}/{path}").status_code == 200, path
    assert client.post(f"/api/crew/{cid}/briefing", json={}).status_code == 200
    assert client.post(f"/api/crew/{cid}/ask", json={"question": "How am I doing?"}).status_code == 200
    assert client.post(f"/api/crew/{cid}/checkins", json={"values": {"heart_rate": 70}}).status_code == 201
    for path in ["/api/ground", "/api/wellbeing", "/api/report", "/api/crew"]:
        assert client.get(path).status_code == 200, path
    # Mission changes keep working with the imported person in the crew.
    for step in ({"days": 30}, None, {"environment": "iss"}):  # shorter than the data, next day, new env
        rr = client.post("/api/mission/next-day") if step is None else client.post("/api/mission/reset", json=step)
        assert rr.status_code == 200
        for path in ["status", "telemetry", "forecast", "radiation", "alerts", "report"]:
            assert client.get(f"/api/crew/{cid}/{path}").status_code == 200, (step, path)
        assert client.get("/api/ground").status_code == 200


def test_analog_sample_values_arrive_unchanged_and_tell_the_story():
    add_sample_indicators()
    text = sample("analog_mission_60d.csv")
    cid = import_sample("analog_mission_60d.csv")["member"]["id"]
    rows = list(csv.DictReader(text.splitlines()))
    keys = [k for k in rows[0] if k != "day"]
    tel = client.get(f"/api/crew/{cid}/telemetry?indicators={','.join(keys)}").json()["series"]
    for key in keys:
        inflight = {p["day"]: p["value"] for p in tel[key]["points"]}
        assert all(p["source"] == "imported" for p in tel[key]["points"])
        assert inflight == {int(r["day"]): float(r[key]) for r in rows if int(r["day"]) >= 1}, key
        assert sorted(tel[key]["preflight"]) == sorted(float(r[key]) for r in rows if int(r["day"]) < 0), key
    # Exercise slips first, then weight and HRV, then heart rate: the alerts follow that order.
    alerts = client.get(f"/api/crew/{cid}/alerts").json()
    first = {}
    for a in alerts:
        first.setdefault(a["indicator"], a["day"])
    assert first["exercise_minutes"] < first["body_weight"] < first["hrv"] < first["heart_rate"]


def test_wearable_dates_map_to_mission_days():
    add_sample_indicators()
    cid = import_sample("wearable_export.csv")["member"]["id"]
    rows = list(csv.DictReader(sample("wearable_export.csv").splitlines()))
    launch_row = next(r for r in rows if r["Date"].startswith(LAUNCH))
    tel = client.get(f"/api/crew/{cid}/telemetry?indicators=sleep_hours,heart_rate").json()["series"]
    day1 = {k: next(p["value"] for p in s["points"] if p["day"] == 1) for k, s in tel.items()}
    assert day1["sleep_hours"] == round(int(launch_row["Sleep (min)"]) / 60, 1)
    assert day1["heart_rate"] == float(launch_row["Resting Heart Rate (bpm)"])
    assert len(tel["heart_rate"]["preflight"]) == 14


def test_date_files_say_how_dates_were_mapped():
    # Without a launch date the mission start (2026-11-14) is day 1: the note makes that visible.
    r = client.post("/api/crew/import", json={"name": "W", "csv": sample("wearable_export.csv")})
    assert r.status_code == 201
    assert "2026-11-14 as mission day 1: 58 preflight day(s) and 1 mission day(s)" in r.json()["warnings"][0]
    # Dates entirely before that window are refused with the fix spelled out.
    old = "date,heart_rate\n2025-03-01,60\n2025-03-02,61\n"
    r = client.post("/api/crew/import", json={"name": "W", "csv": old})
    assert r.status_code == 422 and "Set the launch date" in r.json()["detail"]
