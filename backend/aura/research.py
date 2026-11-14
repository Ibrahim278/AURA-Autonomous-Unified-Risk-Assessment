"""Real astronaut research data from NASA's Open Science Data Repository (OSDR).

Loads the Inspiration4 (SpaceX, Sept 2021, 3-day orbital flight, 4 civilian crew) clinical lab
files exactly as published in ALSDA's "TRANSFORMED" format. Values are never altered: each one
is returned with the lab's own reference range for that sample, plus a low/normal/high flag.

Files live in ``data/osdr/`` at the repo root:
    LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv   (OSD-575, blood serum)
    LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv            (OSD-569, whole blood; optional)

Column convention: ``<analyte>_value_<unit>``, ``<analyte>_range_min_<unit>`` and
``<analyte>_range_max_<unit>`` (a few files write ``<analyte>_max_<unit>``). Sample names look
like ``C001_serum_L-92``: crew C001, launch minus 92 days.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "osdr"
MISSING = {"", "NA", "N/A", "na", "n/a", "nan"}
# e.g. C001_serum_L-92 (CMP) or C001_whole-blood_L-3_cbc (CBC)
SAMPLE_RE = re.compile(r"^(?P<crew>C\d{3})_(?P<tissue>[a-z_-]+?)_(?P<tp>[LR][+-]\d+)(?:_\w+)?$", re.I)
FLIGHT_DAYS = 3  # Inspiration4 launched 15 Sep 2021 and splashed down 18 Sep 2021

DATASETS = {
    "cmp": {
        "file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
        "osd": "OSD-575",
        "lsds": "LSDS-8",
        "title": "Comprehensive metabolic panel (blood serum)",
        "url": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-575",
    },
    "cbc": {
        "file": "LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv",
        "osd": "OSD-569",
        "lsds": "LSDS-7",
        "title": "Complete blood count (whole blood)",
        "url": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-569",
    },
}

# Curated analytes with plain-language context. Others in the file are still served, unlabelled.
ANALYTE_INFO: dict[str, dict] = {
    "glucose": {"name": "Glucose", "system": "metabolic", "aura_indicator": "glucose",
                "why": "Energy supply. Inactivity and altered gravity can reduce insulin sensitivity. "
                       "AURA tracks this daily as fasting glucose."},
    "calcium": {"name": "Calcium", "system": "musculoskeletal",
                "why": "Bone releases calcium in weightlessness, raising blood and urine calcium and "
                       "kidney-stone risk on long missions."},
    "alkaline_phosphatase": {"name": "Alkaline phosphatase", "system": "musculoskeletal",
                             "why": "An enzyme from liver and bone. Shifts can reflect bone remodelling."},
    "creatinine": {"name": "Creatinine", "system": "metabolic",
                   "why": "Kidney filtration and muscle mass. Fluid shifts and muscle loss affect it."},
    "urea_nitrogen_bun": {"name": "Blood urea nitrogen (BUN)", "system": "metabolic",
                          "why": "Kidney function and hydration. It rises with dehydration or a high protein turnover."},
    "egfr_non_african_american": {"name": "eGFR", "system": "metabolic",
                                  "why": "Estimated kidney filtration rate (the lab's race-specific "
                                         "formula, shown as published)."},
    "sodium": {"name": "Sodium", "system": "heart",
               "why": "Fluid balance. Microgravity shifts fluid towards the head and the body sheds plasma volume."},
    "potassium": {"name": "Potassium", "system": "heart",
                  "why": "Heart rhythm and muscle function. Sample handling (haemolysis) can raise it artificially."},
    "chloride": {"name": "Chloride", "system": "heart", "why": "Electrolyte and acid-base balance."},
    "carbon_dioxide": {"name": "Bicarbonate (CO2)", "system": "lungs",
                       "why": "Acid-base balance. Relevant to CO2 build-up in closed cabins."},
    "albumin": {"name": "Albumin", "system": "metabolic",
                "why": "Nutrition and fluid status. Inadequate nutrition is a known spaceflight risk."},
    "total_protein": {"name": "Total protein", "system": "metabolic", "why": "Nutrition and hydration status."},
    "alt": {"name": "ALT (liver enzyme)", "system": "metabolic", "why": "Liver cell health."},
    "ast": {"name": "AST (liver/muscle enzyme)", "system": "metabolic", "why": "Liver and muscle cell health."},
    "total_bilirubin": {"name": "Total bilirubin", "system": "metabolic", "why": "Liver function and red cell turnover."},
    "globulin": {"name": "Globulin", "system": "immune", "why": "Includes antibodies. Immune changes are a known spaceflight risk."},
    # --- Complete blood count (LSDS-7)
    "white_blood_cell_count": {"name": "White blood cells", "system": "immune",
                               "why": "Immune defence. Spaceflight stress shifts white cell counts, "
                                      "and AURA watches for infection with body temperature."},
    "absolute_neutrophils": {"name": "Neutrophils (absolute)", "system": "immune",
                             "why": "First-responder immune cells. They often rise with launch and landing stress."},
    "absolute_lymphocytes": {"name": "Lymphocytes (absolute)", "system": "immune",
                             "why": "T and B cells. Reduced function in flight is linked to latent virus reactivation."},
    "red_blood_cell_count": {"name": "Red blood cells", "system": "lungs",
                             "why": "Oxygen carriers. 'Space anaemia': the body destroys more red cells in weightlessness."},
    "hemoglobin": {"name": "Haemoglobin", "system": "lungs", "unit": "g/dL",
                   "why": "Oxygen-carrying protein, a key marker of space anaemia. (The file labels the unit "
                          "'percent', but the values and ranges are g/dL.)"},
    "hematocrit": {"name": "Haematocrit", "system": "lungs",
                   "why": "Share of blood volume that is red cells. It reflects both red cell loss and plasma volume shifts."},
    "platelet_count": {"name": "Platelets", "system": "heart", "why": "Clotting. Fluid shifts and stress can change counts."},
    "mcv": {"name": "Mean red cell volume (MCV)", "system": "lungs", "why": "Average red cell size."},
    "rdw": {"name": "Red cell size variation (RDW)", "system": "lungs",
            "why": "Rises when new red cells are being made to replace lost ones."},
}


@dataclass
class Point:
    timepoint: str
    day: int  # relative to launch day; R+n maps to FLIGHT_DAYS + n
    value: float | None
    range_min: float | None
    range_max: float | None

    @property
    def flag(self) -> str | None:
        if self.value is None:
            return None
        if self.range_min is not None and self.value < self.range_min:
            return "low"
        if self.range_max is not None and self.value > self.range_max:
            return "high"
        return "normal"

    def to_dict(self) -> dict:
        return {"timepoint": self.timepoint, "day": self.day, "value": self.value,
                "range_min": self.range_min, "range_max": self.range_max, "flag": self.flag}


@dataclass
class Analyte:
    key: str
    unit: str
    series: dict[str, list[Point]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        info = ANALYTE_INFO.get(self.key, {})
        ranges = [(p.range_min, p.range_max) for pts in self.series.values() for p in pts
                  if p.value is not None]
        common = max(set(ranges), key=ranges.count) if ranges else (None, None)
        return {
            "key": self.key,
            "name": info.get("name", self.key.replace("_", " ").capitalize()),
            "unit": info.get("unit", self.unit),
            "system": info.get("system"),
            "aura_indicator": info.get("aura_indicator"),
            "why": info.get("why"),
            "featured": self.key in ANALYTE_INFO,
            "typical_range": {"min": common[0], "max": common[1]},
            "out_of_range": sum(p.flag in ("low", "high") for pts in self.series.values() for p in pts),
            "series": {crew: [p.to_dict() for p in pts] for crew, pts in sorted(self.series.items())},
        }


def _num(raw: str | None) -> float | None:
    if raw is None or raw.strip() in MISSING:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def timepoint_day(tp: str) -> int:
    sign_day = int(tp[1:])
    return sign_day if tp[0].upper() == "L" else FLIGHT_DAYS + sign_day


def _humanize_unit(unit: str) -> str:
    return (unit.replace("milliliter_per_minute_per_1.73_meter_squared", "mL/min/1.73m²")
            .replace("milligram_per_deciliter", "mg/dL").replace("grams_per_deciliter", "g/dL")
            .replace("gram_per_deciliter", "g/dL").replace("cells_per_microliter", "cells/µL")
            .replace("millimol_per_liter", "mmol/L").replace("units_per_liter", "U/L")
            .replace("thousand_per_microliter", "×10³/µL").replace("million_per_microliter", "×10⁶/µL")
            .replace("femtoliter", "fL").replace("picogram", "pg").replace("percent", "%"))


def parse_transformed_csv(path: Path) -> dict[str, Analyte]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    # Map analyte -> (value col, min col, max col, unit)
    columns: dict[str, dict] = {}
    for h in headers:
        m = re.match(r"^(?P<a>.+?)_value(?:_(?P<u>.+))?$", h)
        if m:
            columns.setdefault(m["a"], {})["value"] = h
            columns[m["a"]]["unit"] = m["u"] or ""
    for h in headers:
        for a, cols in columns.items():
            if h.startswith(f"{a}_range_min") or h.startswith(f"{a}_min_"):
                cols["min"] = h
            elif h.startswith(f"{a}_range_max") or h.startswith(f"{a}_max_"):
                cols["max"] = h

    analytes: dict[str, Analyte] = {}
    for row in rows:
        m = SAMPLE_RE.match((row.get("Sample Name") or "").strip())
        if not m:
            continue
        crew, tp = m["crew"].upper(), m["tp"].upper()
        for a, cols in columns.items():
            an = analytes.setdefault(a, Analyte(key=a, unit=_humanize_unit(cols["unit"])))
            an.series.setdefault(crew, []).append(Point(
                timepoint=tp, day=timepoint_day(tp), value=_num(row.get(cols["value"])),
                range_min=_num(row.get(cols.get("min", ""))), range_max=_num(row.get(cols.get("max", "")))))
    for an in analytes.values():
        for pts in an.series.values():
            pts.sort(key=lambda p: p.day)
    return analytes


@lru_cache(maxsize=None)
def load(dataset: str) -> dict | None:
    meta = DATASETS[dataset]
    path = DATA_DIR / meta["file"]
    if not path.exists():
        return None
    analytes = parse_transformed_csv(path)
    ordered = sorted(analytes.values(), key=lambda a: (a.key not in ANALYTE_INFO,
                                                       list(ANALYTE_INFO).index(a.key) if a.key in ANALYTE_INFO else 0,
                                                       a.key))
    crews = sorted({c for a in analytes.values() for c in a.series})
    tps = sorted({p.timepoint for a in analytes.values() for pts in a.series.values() for p in pts},
                 key=timepoint_day)
    return {
        "dataset": dataset,
        **{k: meta[k] for k in ("osd", "lsds", "title", "url", "file")},
        "mission": {"name": "Inspiration4", "launch": "2021-09-15", "return": "2021-09-18",
                    "flight_days": FLIGHT_DAYS, "crew_size": len(crews)},
        "source": "research",
        "notice": ("Real, de-identified crew data from NASA OSDR, shown exactly as published. "
                   "Reference ranges are the clinical lab's, per sample. An out-of-range value "
                   "alone is not a diagnosis, and it can reflect sample handling."),
        "crew": crews,
        "timepoints": [{"label": t, "day": timepoint_day(t),
                        "phase": "preflight" if t.startswith("L") else "postflight"} for t in tps],
        "analytes": [a.to_dict() for a in ordered],
    }


def all_datasets() -> list[dict]:
    """Every dataset whose file is present, CMP first."""
    return [d for d in (load(k) for k in DATASETS) if d is not None]


def available() -> list[dict]:
    return [{"dataset": k, "osd": v["osd"], "title": v["title"], "url": v["url"],
             "loaded": (DATA_DIR / v["file"]).exists()} for k, v in DATASETS.items()]
