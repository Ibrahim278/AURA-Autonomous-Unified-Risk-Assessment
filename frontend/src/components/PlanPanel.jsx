import { useEffect, useState } from 'react'
import { api } from '../api.js'

const KIND_ICON = { exercise: '🏋', sleep: '🌙', measure: '🩺', rest: '🛌', radiation: '☢', wellbeing: '💬' }

function mins(m) {
  if (!m) return ''
  return m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ''}` : `${m} min`
}

export default function PlanPanel({ crewId, day, live, catalog, onOpenIndicator, refreshKey }) {
  const [plan, setPlan] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    api.plan(crewId, live ? null : day).then((p) => alive && setPlan(p)).catch((e) => alive && setErr(e.message))
    return () => { alive = false }
  }, [crewId, day, live, refreshKey])

  if (err) return <div className="toast error">{err}</div>
  if (!plan) return null
  const toggle = async (id) => {
    try { setPlan(await api.togglePlan(crewId, id)) } catch (e) { setErr(e.message) }
  }
  return (
    <section className="panel plan" id="plan">
      <div className="panel-head">
        <h2>🗓 Today's countermeasure plan · day {plan.day}</h2>
        {plan.changes > 0 && <span className="badge lvl-warning">{plan.changes} adjusted</span>}
      </div>
      <p className="plan-summary">{plan.summary}</p>
      <ol className="plan-list">
        {plan.blocks.map((b) => (
          <li key={b.id} className={`plan-block ${b.changed ? 'changed' : ''} ${b.done ? 'done' : ''} kind-${b.kind}`}>
            <span className="plan-time">{b.time}</span>
            <label className="plan-body">
              <span className="plan-title">
                {live && <input type="checkbox" checked={b.done} onChange={() => toggle(b.id)} aria-label={`Done: ${b.title}`} />}
                {KIND_ICON[b.kind]} <strong>{b.title}</strong>
                {b.minutes > 0 && <span className="muted"> · {mins(b.minutes)}</span>}
                {b.changed && <span className="adj">adjusted</span>}
              </span>
              <span className="plan-detail">{b.detail}</span>
              {b.because && (
                <span className="plan-why">
                  Why: {b.because}
                  {b.indicator && catalog[b.indicator] && (
                    <button type="button" className="link" onClick={() => onOpenIndicator(b.indicator)}> {catalog[b.indicator].name} →</button>
                  )}
                </span>
              )}
            </label>
          </li>
        ))}
      </ol>
      <p className="hint">{plan.note}</p>
    </section>
  )
}
