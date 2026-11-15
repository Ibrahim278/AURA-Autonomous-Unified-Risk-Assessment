"""New research data: the Alamar 200-plex panels (serum OSD-575, urine OSD-656) and files a team
drops into data/osdr/ themselves."""

import csv
import os

import pytest
from fastapi.testclient import TestClient

from aura import research
from aura.main import app

client = TestClient(app)


def rows_of(dataset):
    with (research.DATA_DIR / research.registry()[dataset]["file"]).open(encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def test_alamar_serum_reads_sample_id_column_and_gene_names():
    d = research.load("alamar")
    assert d["crew"] == ["C001", "C002", "C003", "C004"] and d["has_ranges"] is False
    header = rows_of("alamar")[0]
    n_markers = sum("_concentration_" in h for h in header)
    assert len(d["analytes"]) == n_markers == 203  # percent-normalised columns are not markers
    il6 = next(a for a in d["analytes"] if a["key"] == "il6")
    assert il6["name"] == "IL-6" and il6["featured"] and il6["unit"] == "NPQ (log2)"
    raw = {r[0]: r[header.index("il6_concentration_npq")] for r in rows_of("alamar")[1:]}
    c002 = {p["timepoint"]: p["value"] for p in il6["series"]["C002"]}
    assert c002["R+1"] == float(raw["C002_serum_R+1"])  # value exactly as published
    names = {a["key"]: a["name"] for a in d["analytes"]}
    assert names["cxcl10"] == "IP-10 (CXCL10)" and names["tnfsf11"] == "RANKL" and names["bdnf"] == "BDNF"


def test_urine_panel_excludes_below_detection_zeros():
    d = research.load("urine")
    zeros = [p for a in d["analytes"] for ps in a["series"].values() for p in ps if p["value"] == 0]
    assert len(zeros) == 131 and all(p["suspect"] for p in zeros)
    assert any("131 readings" in q["reason"] and "detection limit" in q["reason"] for q in d["quality_issues"])
    assert [t["label"] for t in d["timepoints"]][-1] == "R+82"  # no R+194 urine samples


def test_new_panels_feed_the_ai_review():
    prof = research.crew_profile("C002")
    assert {"alamar", "urine"} <= {m["panel"] for m in prof["markers"]}
    assert "OSD-656 (LSDS-64)" in prof["source"]
    for m in prof["markers"]:
        assert 0 not in m["values"].values() or m["panel"] not in ("alamar", "urine")


def test_research_listing_has_labels():
    listing = {x["dataset"]: x for x in client.get("/api/research").json()}
    assert listing["urine"]["label"] == "Urine proteins (200-plex)" and listing["urine"]["loaded"]
    assert client.get("/api/research/urine").json()["osd"] == "OSD-656"


# ------------------------------------------------------------------ files a team adds itself
OWN_LAB = (
    "Sample Name,ferritin_value_nanogram_per_milliliter,ferritin_range_min_nanogram_per_milliliter,"
    "ferritin_range_max_nanogram_per_milliliter,vitamin_d_value_nanogram_per_milliliter\n"
    "P01_plasma_L-30,110,30,400,32\nP01_plasma_L-5,118,30,400,30\nP01_plasma_R+2,450,30,400,24\n"
    "P02_plasma_L-30,85,30,400,41\nP02_plasma_L-5,80,30,400,NA\nP02_plasma_R+2,92,30,400,38\n"
)


@pytest.fixture
def osdr_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "DATA_DIR", tmp_path)
    return tmp_path


def test_dropped_in_file_appears_without_code_changes(osdr_dir):
    (osdr_dir / "Team_Lab_Ferritin_TRANSFORMED.csv").write_text(OWN_LAB, encoding="utf-8")
    listing = {x["dataset"]: x for x in client.get("/api/research").json()}
    own = listing["team_lab_ferritin"]
    assert own["loaded"] and own["user_added"] and own["problem"] is None
    assert not listing["cmp"]["loaded"]  # built-ins are missing from this temporary folder
    d = client.get("/api/research/team_lab_ferritin").json()
    assert d["crew"] == ["P01", "P02"] and d["user_added"] and d["has_ranges"]
    assert "Added by your team" in d["notice"]
    fer = next(a for a in d["analytes"] if a["key"] == "ferritin")
    assert fer["unit"] == "ng/mL" and fer["series"]["P01"][-1]["flag"] == "high"
    vit = next(a for a in d["analytes"] if a["key"] == "vitamin_d")
    assert vit["series"]["P02"][1]["value"] is None
    prof = research.crew_profile("P01")
    assert prof is not None and "added file Team_Lab_Ferritin_TRANSFORMED.csv" in prof["source"]
    assert client.post("/api/research/crew/P01/review").status_code == 200


def test_unreadable_file_is_reported_not_hidden(osdr_dir):
    (osdr_dir / "notes.csv").write_text("name,comment\nAlice,hello\n", encoding="utf-8")
    entry = next(x for x in client.get("/api/research").json() if x["dataset"] == "notes")
    assert not entry["loaded"] and "no samples recognised" in entry["problem"]
    r = client.get("/api/research/notes")
    assert r.status_code == 422 and "Sample Name" in r.json()["detail"]


def test_edited_file_is_read_again(osdr_dir):
    f = osdr_dir / "lab_TRANSFORMED.csv"
    f.write_text(OWN_LAB, encoding="utf-8")
    assert research.load("lab")["crew"] == ["P01", "P02"]
    f.write_text(OWN_LAB.replace("P02", "P03"), encoding="utf-8")
    st = f.stat()
    os.utime(f, (st.st_atime, st.st_mtime + 5))
    assert research.load("lab")["crew"] == ["P01", "P03"]


def test_blank_headers_never_become_reference_ranges():
    # The urine file has unnamed columns; a marker without range columns must not read them as a range.
    d = research.load("urine")
    assert d["has_ranges"] is False
    assert all(a["out_of_range"] == 0 and a["typical_range"] == {"min": None, "max": None} for a in d["analytes"])
