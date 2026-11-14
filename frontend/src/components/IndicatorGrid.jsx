import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts'
import { LEVEL, SYSTEM_LABEL, TREND_LABEL, fmt } from '../levels.js'

function Sparkline({ points, level }) {
  if (!points?.length) return null
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={points} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
        <YAxis hide domain={['dataMin', 'dataMax']} />
        <Line
          type="monotone"
          dataKey="value"
          dot={false}
          strokeWidth={1.8}
          stroke={`var(--${level})`}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default function IndicatorGrid({
  indicators, telemetry, filterSystem, onClearFilter, selected, onSelect, day,
}) {
  const shown = filterSystem ? indicators.filter((i) => i.body_system === filterSystem) : indicators
  const order = { critical: 0, warning: 1, normal: 2 }
  const sorted = [...shown].sort((a, b) => order[a.level] - order[b.level])

  return (
    <>
      <div className="panel-head">
        <h2>{filterSystem ? SYSTEM_LABEL[filterSystem] : 'Health indicators'}</h2>
        {filterSystem && <button className="link" onClick={onClearFilter}>Show all</button>}
      </div>
      {sorted.length === 0 && <p className="muted">No indicators tracked for this region yet.</p>}
      <div className="grid">
        {sorted.map((a) => {
          const lvl = LEVEL[a.level]
          const points = telemetry?.series[a.indicator]?.points.filter((p) => p.day <= day).slice(-14)
          return (
            <button
              key={a.indicator}
              className={`card ${lvl.cls} ${selected === a.indicator ? 'selected' : ''}`}
              onClick={() => onSelect(a.indicator)}
            >
              <div className="card-top">
                <span className="card-name">{a.name}</span>
                <span className={`badge ${lvl.cls}`}>{lvl.icon} {lvl.label}</span>
              </div>
              <div className="card-value">{fmt(a.value, a.unit)}</div>
              <div className="card-meta">
                <span>{TREND_LABEL[a.trend]}</span>
                {a.baseline && <span>baseline {fmt(a.baseline.mean, a.unit)}</span>}
                {a.source === 'manual' && <span className="tag">manual</span>}
              </div>
              <Sparkline points={points} level={a.level} />
            </button>
          )
        })}
      </div>
    </>
  )
}
