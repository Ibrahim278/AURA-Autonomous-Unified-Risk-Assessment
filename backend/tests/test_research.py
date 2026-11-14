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
    assert {x["dataset"] for x in listing} == {"cmp", "cbc"}
    r = client.get("/api/research/cmp")
    assert r.status_code == 200 and r.json()["source"] == "research"
    assert client.get("/api/research/nope").status_code == 404
