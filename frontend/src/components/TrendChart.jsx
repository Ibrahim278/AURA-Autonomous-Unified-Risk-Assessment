import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

function Dot({ cx, cy, payload }) {
  if (cx == null || cy == null) return null
  if (payload.source === 'manual') {
    return <rect x={cx - 4} y={cy - 4} width={8} height={8} fill="var(--accent)" stroke="#fff" strokeWidth={1} />
  }
  return <circle cx={cx} cy={cy} r={2.2} fill={payload.phase === 'preflight' ? 'var(--muted)' : 'var(--line)'} />
}

export default function TrendChart({ series, day, projection = null }) {
  if (!series) return null
  const pre = series.preflight.map((value, i) => ({
    day: i - series.preflight.length, value, phase: 'preflight', source: 'synthetic',
  }))
  const data = [...pre, ...series.points.filter((p) => p.day <= day).map((p) => ({ ...p, phase: 'inflight' }))]
  // Dashed 7-day trend projection, starting from the fitted value on the current day.
  if (projection?.length) {
    const today = data.find((d) => d.day === projection[0].day)
    if (today) { today.projection = projection[0].value; today.band = [projection[0].lo, projection[0].hi] }
    for (const pt of projection.slice(1)) data.push({ day: pt.day, projection: pt.value, band: [pt.lo, pt.hi], phase: 'projection' })
  }
  const b = series.baseline
  const lim = series.limits
  const values = data.flatMap((d) => [d.value, d.projection, ...(d.band ?? [])]).filter((v) => v != null)
  const lo = Math.min(...values, b ? b.mean - 2 * b.sd : Infinity)
  const hi = Math.max(...values, b ? b.mean + 2 * b.sd : -Infinity)
  const pad = (hi - lo) * 0.15 || 1
  const domain = [Math.floor((lo - pad) * 10) / 10, Math.ceil((hi + pad) * 10) / 10]
  const inView = (v) => v != null && v >= domain[0] && v <= domain[1]

  return (
    <div className="trend">
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 10, right: 20, bottom: 0, left: -10 }}>
          <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
          <XAxis dataKey="day" type="number" domain={['dataMin', 'dataMax']} stroke="var(--muted)" tick={{ fontSize: 11 }} />
          <YAxis domain={domain} stroke="var(--muted)" tick={{ fontSize: 11 }} allowDataOverflow />
          <Tooltip
            contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8 }}
            labelFormatter={(d) => (d < 1 ? `Preflight day ${d}` : `Mission day ${d}`)}
            formatter={(v, n, item) => (n === 'band' ? [`${v[0]} to ${v[1]} ${series.unit}`, '95% range'] : [`${v} ${series.unit}`, n === 'projection' ? 'trend' : item.payload.source])}
          />
          {b && (
            <ReferenceArea y1={b.mean - 2 * b.sd} y2={b.mean + 2 * b.sd} fill="var(--normal)" fillOpacity={0.08} ifOverflow="hidden" />
          )}
          {b && <ReferenceLine y={b.mean} stroke="var(--normal)" strokeDasharray="2 4" label={{ value: 'baseline', fill: 'var(--muted)', fontSize: 10, position: 'insideTopLeft' }} />}
          {[lim.warning_low, lim.warning_high].filter(inView).map((v) => (
            <ReferenceLine key={`w${v}`} y={v} stroke="var(--warning)" strokeDasharray="6 4" />
          ))}
          {[lim.critical_low, lim.critical_high].filter(inView).map((v) => (
            <ReferenceLine key={`c${v}`} y={v} stroke="var(--critical)" strokeDasharray="6 4" />
          ))}
          <ReferenceLine x={0} stroke="var(--accent)" label={{ value: 'launch', fill: 'var(--accent)', fontSize: 10, position: 'insideTopRight' }} />
          <Line type="monotone" dataKey="value" stroke="var(--line)" strokeWidth={2} dot={<Dot />} isAnimationActive={false} />
          {projection?.length > 0 && projection[0].lo != null && (
            <Area type="linear" dataKey="band" stroke="none" fill="#7c3aed" fillOpacity={0.18} connectNulls isAnimationActive={false} />
          )}
          {projection?.length > 0 && (
            <Line type="linear" dataKey="projection" stroke="#7c3aed" strokeWidth={2} strokeDasharray="5 4" dot={false}
              connectNulls isAnimationActive={false} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="chart-legend">
        {b && <span><i className="sw band" /> personal baseline ±2 SD</span>}
        <span><i className="sw warn" /> warning limit</span>
        <span><i className="sw crit" /> critical limit</span>
        <span><i className="sw manual" /> manual entry</span>
        {projection?.length > 0 && <span><i className="sw proj" /> 7-day trend projection</span>}
        {projection?.length > 0 && <span><i className="sw pband" /> 95% range of the trend</span>}
      </div>
    </div>
  )
}
