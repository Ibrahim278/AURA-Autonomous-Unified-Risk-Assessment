from pathlib import Path

from fastapi.testclient import TestClient

from aura import research
from aura.main import app

client = TestClient(app)


def test_parses_cmp_exactly_as_published():
    d = research.load("cmp")
    assert d["crew"] == ["C001", "C002", "C003", "C004"]
    assert [t["label"] for t in d["timepoints"]] == ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
    glucose = next(a for a in d["analytes"] if a["key"] == "glucose")
    assert glucose["unit"] == "mg/dL"
    c003 = {p["timepoint"]: p for p in glucose["series"]["C003"]}
    assert c003["R+45"]["value"] == 36.0 and c003["R+45"]["flag"] == "low"
    assert c003["L-92"]["flag"] == "normal"


def test_alt_ast_max_column_variant_is_read():
    alt = next(a for a in research.load("cmp")["analytes"] if a["key"] == "alt")
    assert alt["typical_range"] == {"min": 9.0, "max": 46.0}


def test_parses_cbc_sample_names_and_unit_fix():
    d = research.load("cbc")
    assert d["crew"] == ["C001", "C002", "C003", "C004"]
    hgb = next(a for a in d["analytes"] if a["key"] == "hemoglobin")
    assert hgb["unit"] == "g/dL"
    assert hgb["series"]["C001"][0]["timepoint"] == "L-92"


def test_missing_values_become_none(tmp_path: Path):
    f = tmp_path / "x.csv"
    f.write_text("Sample Name,foo_value_percent,foo_range_min_percent,foo_range_max_percent\n"
                 "C001_serum_L-3,NA,1,2\nC001_serum_R+1,3,1,2\n")
    pts = research.parse_transformed_csv(f)["foo"].series["C001"]
    assert pts[0].value is None and pts[0].flag is None
    assert pts[1].flag == "high" and pts[1].day == 4


def test_research_endpoints():
    listing = client.get("/api/research").json()
    assert {x["dataset"] for x in listing} == {"cmp", "cbc", "immune", "cardio", "alamar", "urine"}
    assert all(x["loaded"] for x in listing)
    r = client.get("/api/research/cmp")
    assert r.status_code == 200 and r.json()["source"] == "research"
    assert client.get("/api/research/nope").status_code == 404


def test_quality_check_excludes_misaligned_cbc_row():
    d = research.load("cbc")
    assert [(q["crew"], q["timepoint"]) for q in d["quality_issues"]] == [("C003", "L-92")]
    wbc = next(a for a in d["analytes"] if a["key"] == "white_blood_cell_count")
    assert wbc["series"]["C003"][0]["flag"] == "suspect"
    prof = research.crew_profile("C003")
    plt = next(m for m in prof["markers"] if m["key"] == "platelet_count")
    assert "L-92" not in plt["values"]


def test_offline_review(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", "/nonexistent-aura-test")
    r = client.post("/api/research/crew/C003/review").json()
    assert r["mode"] == "offline"
    assert 1 <= len(r["review"]["findings"]) <= 3
    assert client.post("/api/research/crew/C999/review").status_code == 404


def test_parses_multiplex_cytokines_exactly_as_published():
    import csv
    d = research.load("immune")
    assert d["crew"] == ["C001", "C002", "C003", "C004"] and d["has_ranges"] is False
    assert d["analytes"][0]["key"] == "il_6" and d["analytes"][0]["unit"] == "pg/mL"
    with (research.DATA_DIR / research.registry()["immune"]["file"]).open(encoding="utf-8-sig") as f:
        row = next(r for r in csv.DictReader(f) if r["Sample Name"] == "C002_serum_R+1")
    il6 = {p["timepoint"]: p for p in d["analytes"][0]["series"]["C002"]}
    assert il6["R+1"]["value"] == float(row["il_6_concentration_picogram_per_milliliter"])
    assert il6["R+1"]["flag"] == "normal" and il6["R+1"]["range_min"] is None  # no clinical range
    assert not any(a["key"].endswith("percent") for a in d["analytes"])
    names = {a["key"]: a["name"] for a in d["analytes"]}
    assert names["il_17e_per_il_25"] == "IL-17E/IL-25" and names["mip_1α"] == "MIP-1α"


def test_assay_limit_values_are_excluded():
    d = research.load("cardio")
    hp = next(a for a in d["analytes"] if a["key"] == "haptoglobin")
    capped = [p for pts in hp["series"].values() for p in pts if p["value"] == 17907000]
    assert len(capped) == 7 and all(p["suspect"] for p in capped)
    assert any("Haptoglobin" in q["reason"] and "17,907,000" in q["reason"] for q in d["quality_issues"])
    crp = next(a for a in d["analytes"] if a["key"] == "crp")
    assert not any(p["suspect"] for pts in crp["series"].values() for p in pts)


def test_crew_profile_includes_cytokine_panels():
    prof = research.crew_profile("C001")
    panels = {m["panel"] for m in prof["markers"]}
    assert {"cmp", "cbc", "immune", "cardio"} <= panels
    hp = next(m for m in prof["markers"] if m["key"] == "haptoglobin")
    assert 17907000 not in hp["values"].values()
