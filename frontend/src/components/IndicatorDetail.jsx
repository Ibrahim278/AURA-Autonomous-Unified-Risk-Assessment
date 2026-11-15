import { HAZARD_LABEL, LEVEL, TREND_LABEL, fmt } from '../levels.js'
import TrendChart from './TrendChart.jsx'

export default function IndicatorDetail({ assessment: a, info, series, day, onClose, projection, related = [], onSelect }) {
  const lvl = LEVEL[a.level]
  return (
    <section className={`panel detail ${lvl.cls}`}>
      <div className="panel-head">
        <h2>
          {a.name} <span className={`badge ${lvl.cls}`}>{lvl.icon} {lvl.label}</span>
        </h2>
        <button className="link" onClick={onClose} aria-label="Close details">✕ Close</button>
      </div>
      <div className="detail-grid">
        <div>
          <div className="detail-stats">
            <div><span className="muted">Latest</span><strong>{fmt(a.value, a.unit)}</strong></div>
            {a.baseline && <div><span className="muted">{a.baseline.kind === 'adaptive' ? 'In-flight baseline' : 'Your baseline'}</span><strong>{fmt(a.baseline.mean, a.unit)}</strong></div>}
            <div><span className="muted">Trend (7 days)</span><strong>{TREND_LABEL[a.trend]}</strong></div>
            {a.z_score != null && <div><span className="muted">Deviation</span><strong>{a.z_score > 0 ? '+' : ''}{a.z_score} SD</strong></div>}
          </div>
          <TrendChart series={series} day={day} projection={projection} />
          {related.length > 0 && (
            <div className="related">
              <h3>Moving together</h3>
              <p className="muted small">Over the last 14 days these trends moved with {a.name.toLowerCase()}. It's a pattern to check, not proof one causes the other.</p>
              <ul>
                {related.map((r) => (
                  <li key={r.indicator}>
                    <button className="chip" onClick={() => onSelect(r.indicator)}>{r.name} →</button>
                    <span className="muted">{r.together} · r = {r.r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="detail-text">
          <h3>Why this status?</h3>
          <ul>{a.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          {a.actions.length > 0 && (
            <>
              <h3>What to do now</h3>
              <ol className="actions">{a.actions.map((x) => <li key={x}>{x}</li>)}</ol>
            </>
          )}
          {a.escalate && <div className="escalate">📡 Contact the flight surgeon.</div>}
          {info && (
            <>
              <h3>Why it matters in space</h3>
              <p>{info.why_it_matters}</p>
              <div className="hazards">
                {info.hazards.map((h) => <span key={h} className="tag">{HAZARD_LABEL[h]}</span>)}
              </div>
              <h3>How to measure</h3>
              <p>{info.how_to_measure}</p>
              <details>
                <summary>Sources for these thresholds</summary>
                <ul className="refs">{info.references.map((r) => <li key={r}>{r}</li>)}</ul>
                <p className="muted">Prototype rules, not clinically validated limits.</p>
              </details>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
