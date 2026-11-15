import { fmt } from '../levels.js'

const LEVEL_CLS = { warning: 'lvl-warning', critical: 'lvl-critical' }

function rangeText([a, b]) {
  const d = (n) => `${n} day${n === 1 ? '' : 's'}`
  if (a == null) return 'not within 4 weeks'
  if (b == null) return `${d(a)} to more than 4 weeks`
  return a === b ? d(a) : `${a} to ${d(b)}`
}

export default function ForecastPanel({ forecast, onSelectIndicator }) {
  const risks = forecast?.risks ?? []
  return (
    <div className="forecast">
      <h3>📈 Early-warning forecast</h3>
      <p className="muted small">
        Where each trend is heading over the next {forecast?.horizon_days ?? 14} days if nothing changes.
      </p>
      {!forecast && <p className="muted">Loading…</p>}
      {forecast && risks.length === 0 && (
        <div className="forecast-clear">
          <span className="dot lvl-normal" /> No indicator is trending towards a new alert. Keep it up.
        </div>
      )}
      <ul className="forecast-list">
        {risks.map((r) => {
          const c = r.crossing
          const arrow = r.slope_per_day > 0 ? '↗' : '↘'
          return (
            <li key={r.indicator}>
              <button className={`forecast-item ${LEVEL_CLS[c.level]}`} onClick={() => onSelectIndicator(r.indicator)}>
                <span className="forecast-when">
                  <strong>~{c.in_days}</strong>
                  <span>day{c.in_days === 1 ? '' : 's'}</span>
                </span>
                <span className="forecast-body">
                  <span className="forecast-name">{arrow} {r.name}</span>
                  <span className="forecast-detail">
                    Reaches the {c.label} ({fmt(c.threshold, r.unit)})
                    {r.level_now !== 'normal' && <> · already {r.level_now}</>}
                  </span>
                  <span className="muted tiny">
                    {r.slope_per_day > 0 ? '+' : ''}{r.slope_per_day} {r.unit}/day · in 7 days ≈ {fmt(r.projected_7d, r.unit)}
                  </span>
                  {c.range && <span className="forecast-range">95% range: {rangeText(c.range)}</span>}
                  {r.related?.length > 0 && (
                    <span className="forecast-related">Moving with {r.related.map((x) => x.name.toLowerCase()).join(', ')}</span>
                  )}
                </span>
                <span className={`badge ${LEVEL_CLS[c.level]}`}>{c.level}</span>
              </button>
            </li>
          )
        })}
      </ul>
      <p className="muted tiny">{forecast?.method}</p>
    </div>
  )
}
