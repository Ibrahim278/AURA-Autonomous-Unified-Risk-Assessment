import {
  CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

function Dot({ cx, cy, payload }) {
  if (cx == null || cy == null) return null
  if (payload.source === 'manual') {
    return <rect x={cx - 4} y={cy - 4} width={8} height={8} fill="var(--accent)" stroke="#fff" strokeWidth={1} />
  }
  return <circle cx={cx} cy={cy} r={2.2} fill={payload.phase === 'preflight' ? 'var(--muted)' : 'var(--line)'} />
}

export default function TrendChart({ series, day }) {
  if (!series) return null
  const pre = series.preflight.map((value, i) => ({
    day: i - series.preflight.length, value, phase: 'preflight', source: 'synthetic',
  }))
  const data = [...pre, ...series.points.filter((p) => p.day <= day).map((p) => ({ ...p, phase: 'inflight' }))]
  const b = series.baseline
  const lim = series.limits
  const values = data.map((d) => d.value)
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
            formatter={(v, _n, item) => [`${v} ${series.unit}`, item.payload.source]}
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
        </ComposedChart>
      </ResponsiveContainer>
      <div className="chart-legend">
        {b && <span><i className="sw band" /> personal baseline ±2 SD</span>}
        <span><i className="sw warn" /> warning limit</span>
        <span><i className="sw crit" /> critical limit</span>
        <span><i className="sw manual" /> manual entry</span>
      </div>
    </div>
  )
}
