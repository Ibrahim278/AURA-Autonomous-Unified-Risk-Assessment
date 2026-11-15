import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'
import { LEVEL } from '../levels.js'

function Gauge({ b }) {
  const pct = (v) => `${Math.min(100, (100 * v) / b.career_limit_mSv)}%`
  return (
    <div className="dose-gauge" aria-label={`${b.career_used_pct}% of the career limit used`}>
      <div className="dose-bar">
        <span className="prior" style={{ width: pct(b.prior_mSv) }} title={`Earlier missions: ${b.prior_mSv} mSv`} />
        <span className="mission" style={{ width: pct(b.mission_mSv) }} title={`This mission: ${b.mission_mSv} mSv`} />
        <i className="warn-mark" style={{ left: '80%' }} />
        {b.projected_end_mSv > b.career_mSv && (
          <i className="proj-mark" style={{ left: pct(b.projected_end_mSv) }} title={`Projected at day ${b.planned_end_day}`} />
        )}
      </div>
      <div className="dose-legend">
        <span><b className="sw prior" /> Earlier missions {b.prior_mSv} mSv</span>
        <span><b className="sw mission" /> This mission {b.mission_mSv} mSv</span>
        {b.projected_end_mSv > b.career_mSv
          ? <span><b className="sw proj" /> Projected by day {b.planned_end_day}: {b.projected_end_mSv} mSv</span>
          : <span>Warning at 80% (480 mSv)</span>}
      </div>
    </div>
  )
}

export default function RadiationPanel({ budget: b, onOpenIndicator }) {
  if (!b) return null
  const lvl = LEVEL[b.level]
  const proj = [...b.cumulative]
  const last = proj[proj.length - 1]
  if (last && b.planned_end_day > last.day) {
    last.projection = last.mSv
    proj.push({ day: b.planned_end_day, projection: b.projected_end_mSv })
  }
  const top = Math.max(b.career_limit_mSv, b.projected_end_mSv) * 1.05
  return (
    <section className="panel radiation" id="radiation">
      <div className="panel-head">
        <h2>☢ Radiation dose budget</h2>
        <span className={`badge ${lvl.cls}`}>{lvl.icon} {lvl.label}</span>
      </div>
      <div className="rad-grid">
        <div>
          <div className="rad-big"><strong>{b.career_used_pct}%</strong> <span className="muted">of the 600 mSv career limit</span></div>
          <Gauge b={b} />
          <div className="rad-stats">
            <div><strong>{b.remaining_mSv}</strong><span>mSv left</span></div>
            <div><strong>{b.rate_mSv_day}</strong><span>mSv/day now</span></div>
            <div><strong>{b.days_to_limit ?? '—'}</strong><span>days to limit at this rate</span></div>
            <div><strong>{b.window_30d_mSv}<small>/{b.limit_30d_mSv}</small></strong><span>last 30 days</span></div>
          </div>
          <ul className="rad-reasons">
            {b.reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
          <ul className="rad-actions">
            {b.actions.map((a) => <li key={a}>{a}</li>)}
          </ul>
          {b.spe_days.length > 0 && (
            <p className="hint">Solar particle event on day {b.spe_days.join(', ')}.{' '}
              <button className="link" onClick={() => onOpenIndicator('radiation_dose')}>Open daily dose →</button></p>
          )}
        </div>
        <div className="rad-chart">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={proj} margin={{ top: 10, right: 16, bottom: 0, left: -6 }}>
              <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
              <XAxis dataKey="day" type="number" domain={['dataMin', 'dataMax']} stroke="var(--muted)" tick={{ fontSize: 11 }} />
              <YAxis domain={[Math.max(0, Math.floor((b.prior_mSv - 40) / 50) * 50), Math.ceil(top / 50) * 50]} stroke="var(--muted)" tick={{ fontSize: 11 }} unit="" />
              <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)' }}
                formatter={(v, n) => [`${v} mSv`, n === 'mSv' ? 'Career dose' : 'Projection']} labelFormatter={(d) => `Day ${d}`} />
              <ReferenceLine y={b.career_limit_mSv} stroke="var(--critical)" strokeDasharray="4 3"
                label={{ value: 'Career limit 600', fill: 'var(--critical)', fontSize: 11, position: 'insideTopLeft' }} />
              <ReferenceLine y={0.8 * b.career_limit_mSv} stroke="var(--warning)" strokeDasharray="2 4"
                label={{ value: '80%', fill: 'var(--warning)', fontSize: 10, position: 'insideBottomRight' }} />
              {b.prior_mSv > 0 && <ReferenceLine y={b.prior_mSv} stroke="var(--muted)" strokeDasharray="1 3" />}
              <Area dataKey="mSv" stroke="#a78bfa" fill="#a78bfa" fillOpacity={0.18} isAnimationActive={false} />
              <Line dataKey="projection" stroke="#a78bfa" strokeDasharray="6 4" dot={false} isAnimationActive={false} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
          <p className="hint">{b.note}</p>
        </div>
      </div>
    </section>
  )
}
