import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { LEVEL } from '../levels.js'

function Lvl({ level, text }) {
  const l = LEVEL[level]
  return <span className={`badge ${l.cls}`}>{l.icon} {text ?? l.label}</span>
}

export default function GroundView({ day, live, onOpenCrew, refreshKey }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () => api.ground(live ? null : day).then((d) => alive && setData(d)).catch((e) => alive && setErr(e.message))
    load()
    const t = setInterval(load, 5000) // pick up crew messages as their signal arrives
    return () => { alive = false; clearInterval(t) }
  }, [day, live, refreshKey])

  if (err) return <div className="toast error">{err}</div>
  if (!data) return null
  return (
    <section className="ground" id="ground">
      <div className="panel ground-head">
        <div>
          <h2>🛰 Ground · flight surgeon console</h2>
          <p className="muted small">
            {data.environment} · mission day {data.day}{!live && ' (replay)'} · {data.note}
          </p>
        </div>
        <div className="ground-counts">
          <span className="count lvl-critical">{data.counts.critical} critical</span>
          <span className="count lvl-warning">{data.counts.warning} warning</span>
          <span className="count lvl-normal">{data.counts.normal} normal</span>
          <a className="primary small" href={api.reportUrl(null, live ? null : day)} target="_blank" rel="noreferrer">🖨 Crew report</a>
        </div>
      </div>
      <div className="ground-grid">
        {data.crew.map((r) => (
          <article key={r.crew_id} className={`panel ground-card ${LEVEL[r.priority].cls}`}>
            <header>
              <div>
                <h3>{r.name}</h3>
                <span className="muted small">{r.role}{r.data_source === 'imported' && ' · their data'}
                  {r.last_manual_day && ` · last manual check-in day ${r.last_manual_day}`}</span>
              </div>
              <Lvl level={r.priority} />
            </header>
            {r.escalate && <div className="escalate small">📡 Needs flight-surgeon review now</div>}
            <div className="g-row">
              <span className="g-label">Telemetry</span>
              <div>
                <Lvl level={r.overall} />
                {r.flagged.length === 0
                  ? <span className="muted small"> All within baseline</span>
                  : <ul className="g-list">{r.flagged.slice(0, 4).map((f) => (
                    <li key={f.indicator}><strong>{f.name}</strong> {f.value} {f.unit} <span className={`g-dot ${LEVEL[f.level].cls}`}>{f.level}</span></li>
                  ))}</ul>}
              </div>
            </div>
            <div className="g-row">
              <span className="g-label">Symptoms</span>
              <div>
                <Lvl level={r.symptoms.level} text={r.symptoms.level === 'normal' ? 'Self-care' : null} />
                <span className="small"> {r.symptoms.today.length ? r.symptoms.today.join(', ') : 'None today'}</span>
              </div>
            </div>
            <div className="g-row">
              <span className="g-label">Radiation</span>
              <div>
                <Lvl level={r.radiation.level} />
                <span className="small"> {r.radiation.career_used_pct}% of career limit · {r.radiation.rate_mSv_day} mSv/day</span>
              </div>
            </div>
            <div className="g-row">
              <span className="g-label">Trend</span>
              <div className="small">
                {r.forecast.length
                  ? r.forecast.map((f) => `${f.name} → ${f.label} in ~${f.in_days} d`).join(' · ')
                  : <span className="muted">No adverse trend</span>}
              </div>
            </div>
            <div className="g-row">
              <span className="g-label">Messages</span>
              <div className="small">
                {r.messages.last
                  ? <>
                    {r.messages.urgent > 0 && <span className="badge lvl-critical">{r.messages.urgent} urgent</span>}{' '}
                    “{r.messages.last.text.length > 110 ? `${r.messages.last.text.slice(0, 107)}…` : r.messages.last.text}”
                  </>
                  : <span className="muted">None received</span>}
                {r.messages.in_transit > 0 && <span className="muted"> · {r.messages.in_transit} still in transit</span>}
              </div>
            </div>
            <footer>
              <button className="chip" onClick={() => onOpenCrew(r.crew_id)}>Open dashboard →</button>
              <a className="chip" href={api.reportUrl(r.crew_id, live ? null : day)} target="_blank" rel="noreferrer">🖨 Report</a>
            </footer>
          </article>
        ))}
      </div>
    </section>
  )
}
