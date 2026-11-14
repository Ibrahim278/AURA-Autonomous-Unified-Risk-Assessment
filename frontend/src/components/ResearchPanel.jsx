import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api.js'
import ResearchReview from './ResearchReview.jsx'

const CREW_COLORS = { C001: '#a5c8ff', C002: '#c084fc', C003: '#f472b6', C004: '#2dd4bf' }
const DATASET_LABELS = { cmp: 'Metabolic panel', cbc: 'Blood count' }

function FlagDot({ cx, cy, payload, dataKey, stroke }) {
  if (cx == null || cy == null) return null
  const flag = payload[`${dataKey}_flag`]
  if (flag === 'low' || flag === 'high') {
    return (
      <g>
        <circle cx={cx} cy={cy} r={6} fill="none" stroke="var(--warning)" strokeWidth={1.5} />
        <circle cx={cx} cy={cy} r={3} fill={stroke} />
      </g>
    )
  }
  return <circle cx={cx} cy={cy} r={3} fill={stroke} />
}

function ChartTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null
  return (
    <div className="research-tip">
      <strong>{label}</strong>
      {payload.map((p) => {
        const flag = p.payload[`${p.dataKey}_flag`]
        return (
          <div key={p.dataKey} style={{ color: p.stroke }}>
            {p.dataKey}: {p.value} {unit}
            {flag && flag !== 'normal' && <span className="tip-flag"> {flag}</span>}
          </div>
        )
      })}
    </div>
  )
}

export default function ResearchPanel({ focus = null }) {
  const [datasets, setDatasets] = useState([])
  const [dataset, setDataset] = useState('cmp')
  const [data, setData] = useState(null)
  const [key, setKey] = useState(null)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(null) // marker name to show once the other panel loads
  const [pendingKey, setPendingKey] = useState(null) // marker key requested by the demo tour

  useEffect(() => {
    if (!focus) return
    setDataset(focus.dataset)
    setPendingKey(focus.key)
  }, [focus])

  useEffect(() => {
    api.research().then((list) => setDatasets(list.filter((d) => d.loaded))).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    setData(null)
    api.researchDataset(dataset)
      .then((d) => {
        setData(d)
        setKey((k) => (d.analytes.some((a) => a.key === k) ? k : d.analytes[0]?.key ?? null))
        setError(null)
      })
      .catch((e) => setError(e.message))
  }, [dataset])

  useEffect(() => {
    if (!data || !pendingKey || data.dataset !== focus?.dataset) return
    if (data.analytes.some((a) => a.key === pendingKey)) setKey(pendingKey)
    setPendingKey(null)
  }, [data, pendingKey, focus])

  useEffect(() => {
    if (!data || !pending) return
    const a = data.analytes.find((x) => x.name === pending)
    if (a) setKey(a.key)
    setPending(null)
  }, [data, pending])

  const analyte = data?.analytes.find((a) => a.key === key)
  const rows = useMemo(() => {
    if (!data || !analyte) return []
    return data.timepoints.map((tp) => {
      const row = { label: tp.label, phase: tp.phase }
      for (const crew of data.crew) {
        const p = analyte.series[crew]?.find((x) => x.timepoint === tp.label)
        row[crew] = p && !p.suspect ? p.value : null
        row[`${crew}_flag`] = p?.flag ?? null
      }
      return row
    })
  }, [data, analyte])

  if (error) return <div className="panel research-panel"><h2>Real crew data</h2><p className="muted">{error}</p></div>
  if (!data || !analyte) return <div className="panel research-panel"><h2>Real crew data</h2><p className="muted">Loading…</p></div>

  const values = rows.flatMap((r) => data.crew.map((c) => r[c])).filter((v) => v != null)
  const rmin = analyte.typical_range.min
  const rmax = analyte.typical_range.max
  const lo = Math.min(...values, rmin ?? Infinity)
  const hi = Math.max(...values, rmax ?? -Infinity)
  const pad = (hi - lo) * 0.12 || 1
  const domain = [+(lo - pad).toPrecision(3), +(hi + pad).toPrecision(3)]
  const featured = data.analytes.filter((a) => a.featured)
  const others = data.analytes.filter((a) => !a.featured)

  return (
    <div className="panel research-panel" id="research">
      <div className="panel-head">
        <div>
          <h2>Real crew data · Inspiration4</h2>
          <div className="muted small">
            NASA OSDR <a href={data.url} target="_blank" rel="noreferrer">{data.osd}</a> ({data.lsds}) ·
            {' '}{data.title} · 4 civilian crew, 3-day orbital flight, Sept 2021
          </div>
        </div>
        <span className="source-tag research">research data</span>
      </div>

      <div className="research-controls">
        <div className="seg">
          {datasets.map((d) => (
            <button key={d.dataset} className={d.dataset === dataset ? 'active' : ''} onClick={() => setDataset(d.dataset)}>
              {DATASET_LABELS[d.dataset] ?? d.dataset}
            </button>
          ))}
        </div>
        <select value={key} onChange={(e) => setKey(e.target.value)} className="env-select">
          <optgroup label="Space-relevant">
            {featured.map((a) => <option key={a.key} value={a.key}>{a.name}{a.out_of_range ? ` (${a.out_of_range} out of range)` : ''}</option>)}
          </optgroup>
          {others.length > 0 && (
            <optgroup label="More from this panel">
              {others.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
            </optgroup>
          )}
        </select>
      </div>

      {analyte.why && <p className="research-why">{analyte.why}</p>}

      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={rows} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
          <XAxis dataKey="label" stroke="var(--muted)" tick={{ fontSize: 11 }} />
          <YAxis domain={domain} stroke="var(--muted)" tick={{ fontSize: 11 }} allowDataOverflow tickFormatter={(v) => +v.toPrecision(3)}
            label={{ value: analyte.unit, angle: -90, position: 'insideLeft', fill: 'var(--muted)', fontSize: 11 }} />
          <ReferenceArea x1="L-3" x2="R+1" fill="var(--accent)" fillOpacity={0.1}
            label={{ value: 'spaceflight', fill: 'var(--accent)', fontSize: 10, position: 'insideTop' }} />
          {(rmin != null || rmax != null) && (
            <ReferenceArea y1={rmin ?? domain[0]} y2={rmax ?? domain[1]} fill="var(--normal)" fillOpacity={0.08} ifOverflow="hidden" />
          )}
          <Tooltip content={<ChartTooltip unit={analyte.unit} />} />
          {data.crew.map((c) => (
            <Line key={c} type="linear" dataKey={c} stroke={CREW_COLORS[c] ?? 'var(--line)'} strokeWidth={2}
              dot={<FlagDot />} connectNulls isAnimationActive={false} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      <div className="chart-legend">
        {data.crew.map((c) => <span key={c}><i className="sw" style={{ background: CREW_COLORS[c] }} /> {c}</span>)}
        <span><i className="sw band" /> typical lab range (flags use each sample's own range)</span>
        <span><i className="sw ring" /> outside range</span>
      </div>
      <p className="research-notice">
        {data.notice} Timepoints are days before launch (L−) and after return (R+). Crew IDs C001–C004 are
        the published de-identified codes, separate from AURA&apos;s synthetic demo crew.
        {data.quality_issues.map((q) => (
          <span key={q.crew + q.timepoint}> Excluded by AURA&apos;s quality check: {q.crew} at {q.timepoint}. {q.reason}</span>
        ))}
      </p>
      <ResearchReview
        crew={data.crew}
        colors={CREW_COLORS}
        focusCrew={focus?.crew}
        onSelectMarker={(name) => {
          const a = data.analytes.find((x) => x.name === name)
          if (a) setKey(a.key)
          else {
            setPending(name)
            setDataset(dataset === 'cmp' ? 'cbc' : 'cmp')
          }
          document.getElementById('research')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }}
      />
    </div>
  )
}
