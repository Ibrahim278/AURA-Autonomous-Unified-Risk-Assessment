import { useMemo, useState } from 'react'
import { LEVEL, SYSTEM_LABEL, fmt } from '../levels.js'

const KINDS = [
  ['all', 'All'],
  ['critical', 'Critical'],
  ['warning', 'Warning'],
  ['normal', 'Recovered'],
]

export default function AlertTimeline({ alerts, upToDay, onSelect, catalog = {} }) {
  const [kind, setKind] = useState('all')
  const [system, setSystem] = useState('')
  const [range, setRange] = useState('all')

  const upTo = alerts.filter((a) => a.day <= upToDay)
  const systems = useMemo(
    () => [...new Set(upTo.map((a) => catalog[a.indicator]?.body_system).filter(Boolean))],
    [upTo, catalog],
  )
  const shown = upTo
    .filter((a) => kind === 'all' || a.to === kind)
    .filter((a) => !system || catalog[a.indicator]?.body_system === system)
    .filter((a) => range === 'all' || a.day > upToDay - Number(range))
    .reverse()
  const count = (k) => upTo.filter((a) => k === 'all' || a.to === k).length

  return (
    <div className="timeline">
      <div className="panel-head">
        <h2>Alert timeline</h2>
        <span className="muted small">{shown.length} of {upTo.length}</span>
      </div>
      <div className="tl-filters">
        <div className="seg" role="group" aria-label="Alert level">
          {KINDS.map(([k, label]) => (
            <button key={k} className={kind === k ? 'active' : ''} onClick={() => setKind(k)}>
              {label} <span className="muted">{count(k)}</span>
            </button>
          ))}
        </div>
        <select aria-label="Body system" value={system} onChange={(e) => setSystem(e.target.value)}>
          <option value="">All body systems</option>
          {systems.map((s) => <option key={s} value={s}>{SYSTEM_LABEL[s] ?? s}</option>)}
        </select>
        <select aria-label="Time range" value={range} onChange={(e) => setRange(e.target.value)}>
          <option value="all">Whole mission</option>
          <option value="7">Last 7 days</option>
          <option value="14">Last 14 days</option>
          <option value="30">Last 30 days</option>
        </select>
      </div>
      {upTo.length === 0 && <p className="muted">No alerts so far this mission.</p>}
      {upTo.length > 0 && shown.length === 0 && <p className="muted">No alerts match these filters.</p>}
      <ol>
        {shown.map((e) => {
          const lvl = LEVEL[e.to]
          return (
            <li key={`${e.day}-${e.indicator}-${e.to}`}>
              <button className="timeline-item" onClick={() => onSelect(e.indicator, e.day)} title={e.reason}>
                <span className="t-day">Day {e.day}</span>
                <span className={`badge ${lvl.cls}`}>{lvl.icon} {lvl.label}</span>
                <span className="t-text">
                  <strong>{e.name}</strong> {fmt(e.value, e.unit)}
                  {e.to === 'normal' && <span className="muted"> (back to normal)</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
