import { useEffect, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api.js'

const BAND = {
  thriving: { label: 'Thriving', cls: 'lvl-normal' },
  watch: { label: 'Watch', cls: 'lvl-warning' },
  support: { label: 'Needs support', cls: 'lvl-critical' },
}
const COLORS = ['#38bdf8', '#f472b6', '#a3e635', '#fbbf24', '#c084fc', '#2dd4bf', '#fb923c', '#e879f9', '#67e8f9', '#facc15', '#94a3b8', '#f87171']

function TrendChart({ data, names, unit, title }) {
  const ids = Object.keys(names)
  return (
    <div className="team-chart">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
          <XAxis dataKey="day" stroke="var(--muted)" tick={{ fontSize: 11 }} />
          <YAxis stroke="var(--muted)" tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
          <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)' }}
            labelFormatter={(d) => `Day ${d}`} formatter={(v, n) => [`${v} ${unit}`, n]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {ids.map((id, i) => (
            <Line key={id} dataKey={id} name={names[id]} stroke={COLORS[i % COLORS.length]} dot={false}
              strokeWidth={1.5} isAnimationActive={false} connectNulls />
          ))}
          <Line dataKey="crew" name="Crew average" stroke="#e5e7eb" strokeDasharray="5 4" dot={false} strokeWidth={2.2} isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function TeamView({ day, live, onOpenCrew, refreshKey }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    let alive = true
    api.wellbeing(live ? null : day).then((d) => alive && setData(d)).catch((e) => alive && setErr(e.message))
    return () => { alive = false }
  }, [day, live, refreshKey])

  if (err) return <div className="toast error">{err}</div>
  if (!data) return null
  const band = BAND[data.crew_band]
  return (
    <section className="team" id="team">
      <div className="panel team-head">
        <div className="team-score">
          <span className={`score-ring ${band.cls}`}><strong>{data.crew_score}</strong><small>/100</small></span>
          <div>
            <h2>👥 Crew wellbeing · day {data.day}</h2>
            <span className={`badge ${band.cls}`}>{band.label}</span>
            <span className="muted small"> Crew mood {data.mood_trend_per_day < -0.02 ? 'trending down' : data.mood_trend_per_day > 0.02 ? 'trending up' : 'steady'} over 14 days</span>
          </div>
        </div>
        <ul className="team-tips">
          {data.suggestions.map((t) => <li key={t}>{t}</li>)}
        </ul>
      </div>
      <div className="team-grid">
        {data.members.map((m) => {
          const b = BAND[m.band]
          return (
            <article key={m.crew_id} className={`panel team-card ${b.cls}`}>
              <header>
                <div><h3>{m.name}</h3><span className="muted small">{m.role}</span></div>
                <span className={`badge ${b.cls}`}>{b.label}</span>
              </header>
              <div className="score-bar"><span style={{ width: `${m.score}%` }} /></div>
              <div className="score-num"><strong>{m.score}</strong> / 100</div>
              {m.drivers.length
                ? <ul className="g-list">{m.drivers.map((d) => <li key={d}>{d}</li>)}</ul>
                : <p className="muted small">Mood, sleep and exercise on track.</p>}
              <button className="chip" onClick={() => onOpenCrew(m.crew_id)}>Open dashboard →</button>
            </article>
          )
        })}
      </div>
      <div className="panel team-charts">
        <TrendChart data={data.series.mood} names={data.names} unit="/10" title="Mood, last 30 days" />
        <TrendChart data={data.series.sleep_hours} names={data.names} unit="h" title="Sleep, last 30 days" />
      </div>
      <p className="hint">{data.note} Score = 100 minus penalties for mood and sleep below baseline, behavioural symptoms and missed exercise over the last 7 days.</p>
    </section>
  )
}
