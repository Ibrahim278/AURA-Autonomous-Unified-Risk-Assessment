"""Ground flight-surgeon view: the whole crew on one screen, plus a printable health report.

The crew view helps one astronaut look after themselves. The flight surgeon on the ground needs
the opposite: every crew member at once, sorted by who needs attention first, and a report they
can file or forward. Ground sees crew messages only once their signal has actually arrived.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from . import forecast as fc
from . import radiation, symptoms
from .alerts import Level

RANK = {"critical": 2, "warning": 1, "normal": 0}


def _messages(outbox, crew_id: str) -> dict:
    now = datetime.now(timezone.utc)
    arrived = [m for m in outbox.messages if m["crew_id"] == crew_id and m["direction"] == "to_ground"
               and datetime.fromisoformat(m["arrives_at"]) <= now]
    in_transit = sum(1 for m in outbox.messages if m["crew_id"] == crew_id and m["direction"] == "to_ground"
                     and datetime.fromisoformat(m["arrives_at"]) > now)
    last = arrived[-1] if arrived else None
    return {"received": len(arrived), "urgent": sum(m["priority"] == "urgent" for m in arrived),
            "in_transit": in_transit,
            "last": None if last is None else {"day": last["day"], "text": last["text"], "priority": last["priority"]}}


def crew_row(store, outbox, crew_id: str, day: int) -> dict:
    member = store.crew[crew_id]
    st = store.status(crew_id, day)
    flagged = sorted((i for i in st["indicators"] if i["level"] != "normal"),
                     key=lambda i: -RANK[i["level"]])
    sym = symptoms.report(store.symptoms[crew_id], day)
    rad = radiation.budget(store, crew_id, day)
    risks = fc.forecast(store, crew_id, day)["risks"]
    manual_days = [r.day for k in st["indicators"] for r in store.readings(crew_id, k["indicator"], day)
                   if r.source == "manual"]
    # Ground's priority: the worst of telemetry, symptom triage and radiation.
    levels = [st["overall"], sym["triage"]["level"], rad["level"]]
    priority = max(levels, key=lambda lvl: RANK[lvl])
    return {
        "crew_id": crew_id,
        "name": member.name,
        "role": member.role,
        "data_source": "imported" if member.imported is not None else "synthetic",
        "day": day,
        "priority": priority,
        "overall": st["overall"],
        "escalate": st["escalate"] or sym["triage"]["escalate"],
        "flagged": [{"indicator": i["indicator"], "name": i["name"], "level": i["level"], "value": i["value"],
                     "unit": i["unit"], "reason": i["reasons"][0] if i["reasons"] else ""} for i in flagged],
        "symptoms": {"level": sym["triage"]["level"], "reasons": sym["triage"]["reasons"],
                     "today": [f'{x["name"]} {x["severity"]}/10' for e in sym["log"] if e["day"] == day
                               for x in e["symptoms"]]},
        "radiation": {k: rad[k] for k in ("level", "career_used_pct", "career_mSv", "rate_mSv_day", "days_to_limit")},
        "forecast": [{"indicator": r["indicator"], "name": r["name"], "in_days": r["crossing"]["in_days"],
                      "level": r["crossing"]["level"], "label": r["crossing"]["label"]} for r in risks[:3]],
        "messages": _messages(outbox, crew_id),
        "last_manual_day": max(manual_days) if manual_days else None,
    }


def overview(store, outbox, day: int | None = None) -> dict:
    day = store.current_day if day is None else day
    rows = [crew_row(store, outbox, cid, day) for cid in store.crew]
    rows.sort(key=lambda r: (-RANK[r["priority"]], -len(r["flagged"]), r["name"]))
    return {
        "day": day,
        "environment": store.dataset.environment_info["name"],
        "counts": {lvl.label: sum(r["priority"] == lvl.label for r in rows) for lvl in Level},
        "crew": rows,
        "note": "Priority is the worst of telemetry alerts, symptom triage and radiation budget.",
    }


# ---------------------------------------------------------------- printable report
CSS = """
body{font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;color:#111;max-width:860px;margin:24px auto;padding:0 16px}
h1{font-size:22px;margin:0}h2{font-size:16px;margin:22px 0 6px;border-bottom:2px solid #222;padding-bottom:3px}
.meta{color:#555;font-size:12px}.lvl{display:inline-block;padding:1px 8px;border-radius:10px;font-weight:700;
font-size:11px;text-transform:uppercase}.critical{background:#fde2e2;color:#991b1b}.warning{background:#fef3c7;
color:#92400e}.normal{background:#dcfce7;color:#166534}table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{border-bottom:1px solid #ddd;padding:5px 6px;text-align:left;vertical-align:top}th{background:#f4f4f5}
.box{border:1px solid #ccc;border-radius:6px;padding:8px 12px;margin:8px 0}.foot{margin-top:28px;font-size:11px;color:#666}
.print{position:fixed;top:12px;right:12px;padding:8px 14px;border-radius:8px;border:0;background:#2563eb;color:#fff;
font-weight:700;cursor:pointer}@media print{.print{display:none}body{margin:0}}
"""


def _lvl(level: str) -> str:
    return f'<span class="lvl {escape(level)}">{escape(level)}</span>'


def report_html(store, outbox, crew_ids: list[str], day: int | None = None) -> str:
    day = store.current_day if day is None else day
    ds = store.dataset
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>AURA health report · day {day}</title>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head><body>",
             "<button class='print' onclick='window.print()'>Print / Save as PDF</button>",
             f"<h1>AURA crew health report</h1><div class='meta'>{escape(ds.mission_name)} · "
             f"{escape(ds.environment_info['name'])} · mission day {day} of {ds.days} · generated {generated}</div>"]
    for cid in crew_ids:
        r = crew_row(store, outbox, cid, day)
        st = store.status(cid, day)
        rad = radiation.budget(store, cid, day)
        sym = symptoms.report(store.symptoms[cid], day)
        parts.append(f"<h2>{escape(r['name'])} · {escape(r['role'])} {_lvl(r['priority'])}</h2>")
        parts.append(f"<div class='meta'>Telemetry {_lvl(r['overall'])} · symptoms {_lvl(r['symptoms']['level'])} · "
                     f"radiation {_lvl(rad['level'])} · data: {r['data_source']}"
                     f"{' · ESCALATE TO FLIGHT SURGEON' if r['escalate'] else ''}</div>")
        if r["flagged"]:
            rows = "".join(f"<tr><td>{escape(f['name'])}</td><td>{f['value']} {escape(f['unit'])}</td>"
                           f"<td>{_lvl(f['level'])}</td><td>{escape(f['reason'])}</td></tr>" for f in r["flagged"])
            parts.append(f"<table><tr><th>Flagged indicator</th><th>Value</th><th>Level</th><th>Why</th></tr>{rows}</table>")
        else:
            parts.append("<p>All indicators within the personal baseline.</p>")
        allrows = "".join(
            f"<tr><td>{escape(i['name'])}</td><td>{'' if i['value'] is None else i['value']} {escape(i['unit'])}</td>"
            f"<td>{'' if not i['baseline'] else str(i['baseline']['mean']) + ' ± ' + str(i['baseline']['sd'])}</td>"
            f"<td>{escape(i['trend'] or '')}</td><td>{_lvl(i['level'])}</td></tr>" for i in st["indicators"])
        parts.append(f"<details open><summary>All indicators</summary><table><tr><th>Indicator</th><th>Value</th>"
                     f"<th>Baseline (mean ± SD)</th><th>Trend</th><th>Level</th></tr>{allrows}</table></details>")
        if r["forecast"]:
            parts.append("<div class='box'><strong>Early warning (trend, not a prediction):</strong> " + "; ".join(
                f"{escape(f['name'])} reaches the {escape(f['label'])} in ~{f['in_days']} day(s)" for f in r["forecast"]) + "</div>")
        log = [e for e in sym["log"] if e["day"] > day - 7]
        parts.append("<div class='box'><strong>Symptoms (last 7 days):</strong> " + (
            "; ".join(f"day {e['day']}: " + ", ".join(f"{escape(x['name'])} {x['severity']}/10" for x in e["symptoms"])
                      for e in log) or "none logged") + "<br><em>Triage:</em> " + escape(" ".join(sym["triage"]["reasons"])) + "</div>")
        parts.append(f"<div class='box'><strong>Radiation:</strong> {rad['career_mSv']} mSv career "
                     f"({rad['career_used_pct']}% of 600 mSv; {rad['prior_mSv']} before this mission), "
                     f"{rad['rate_mSv_day']} mSv/day, {rad['window_30d_mSv']} mSv in 30 days. "
                     f"{escape(' '.join(rad['reasons']))}</div>")
        m = r["messages"]
        if m["last"]:
            parts.append(f"<div class='box'><strong>Last message received</strong> (day {m['last']['day']}, "
                         f"{escape(m['last']['priority'])}): “{escape(m['last']['text'])}”</div>")
    parts.append("<div class='foot'>Prototype. Thresholds are research-informed prototype rules, not clinically "
                 "validated flight-medicine limits. Demo telemetry and symptom logs are SYNTHETIC unless marked "
                 "as imported or manual. Generated by AURA (Autonomous Unified Risk Assessment).</div></body></html>")
    return "".join(parts)
