import { LEVEL, fmt } from '../levels.js'

export default function AlertTimeline({ alerts, upToDay, onSelect }) {
  const shown = alerts.filter((a) => a.day <= upToDay).reverse()
  return (
    <div className="timeline">
      <h2>Alert timeline</h2>
      {shown.length === 0 && <p className="muted">No alerts so far this mission.</p>}
      <ol>
        {shown.map((e) => {
          const lvl = LEVEL[e.to]
          return (
            <li key={`${e.day}-${e.indicator}-${e.to}`}>
              <button className="timeline-item" onClick={() => onSelect(e.indicator, e.day)}>
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
