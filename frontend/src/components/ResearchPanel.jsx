import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api.js'
import ResearchReview from './ResearchReview.jsx'

const CREW_COLORS = { C001: '#38bdf8', C002: '#a78bfa', C003: '#f472b6', C004: '#2dd4bf' }
// Crew in files a team adds to data/osdr/ (other IDs) take these in order.
const EXTRA_COLORS = ['#fbbf24', '#a3e635', '#fb923c', '#67e8f9', '#e879f9', '#94a3b8']
const DATASET_LABELS = { cmp: 'Metabolic panel', cbc: 'Blood count', immune: 'Immune cytokines', cardio: 'Cardio & inflammation' }

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
  const [problems, setProblems] = useState([]) // files in data/osdr/ AURA could not read
  const [dataset, setDataset] = useState('cmp')
  const [data, setData] = useState(null)
  const [key, setKey] = useState(null)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(null) // { name, tries }: marker to find in another panel
  const [pendingKey, setPendingKey] = useState(null) // marker key requested by the demo tour

  useEffect(() => {
    if (!focus) return
    setDataset(focus.dataset)
    setPendingKey(focus.key)
  }, [focus])

  useEffect(() => {
    api.research().then((list) => {
      setDatasets(list.filter((d) => d.loaded))
      setProblems(list.filter((d) => !d.loaded && d.user_added && d.problem))
    }).catch((e) => setError(e.message))
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
    const a = data.analytes.find((x) => x.name === pending.name)
    if (a) { setKey(a.key); setPending(null); return }
    if (pending.tries + 1 >= datasets.length) { setPending(null); return }
    const i = datasets.findIndex((d) => d.dataset === dataset)
    setPending({ name: pending.name, tries: pending.tries + 1 })
    setDataset(datasets[(i + 1) % datasets.length].dataset)
  }, [data, pending, datasets, dataset])

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
  const colors = useMemo(() => {
    const out = {}
    let extra = 0
    for (const c of data?.crew ?? []) out[c] = CREW_COLORS[c] ?? EXTRA_COLORS[extra++ % EXTRA_COLORS.length]
    return out
  }, [data])

  if (error) return <div className="panel research-panel"><h2>Real crew data</h2><p className="muted">{error}</p></div>
  if (!data || !analyte) return <div className="panel research-panel"><h2>Real crew data</h2><p className="muted">Loading…</p></div>

  const values = rows.flatMap((r) => data.crew.map((c) => r[c])).filter((v) => v != null)
  const rmin = analyte.typical_range.min
  const rmax = analyte.typical_range.max
  const lo = Math.min(...values, rmin ?? Infinity)
  const hi = Math.max(...values, rmax ?? -Infinity)
  const pad = (hi - lo) * 0.12 || 1
  const domain = [lo >= 0 ? Math.max(0, +(lo - pad).toPrecision(3)) : +(lo - pad).toPrecision(3), +(hi + pad).toPrecision(3)]
  const tick = (v) => (Math.abs(v) >= 10000 ? new Intl.NumberFormat('en', { notation: 'compact', maximumSignificantDigits: 3 }).format(v) : +v.toPrecision(3))
  const featured = data.analytes.filter((a) => a.featured)
  const others = data.analytes.filter((a) => !a.featured)

  return (
    <div className="panel research-panel" id="research">
      <div className="panel-head">
        <div>
          <h2>Real crew data · {data.user_added ? 'added by your team' : 'Inspiration4'}</h2>
          <div className="muted small">
            {data.user_added
              ? <>data/osdr/{data.file} · {data.crew.length} people, {data.analytes.length} markers</>
              : <>NASA OSDR <a href={data.url} target="_blank" rel="noreferrer">{data.osd}</a> ({data.lsds}) ·
                {' '}{data.title} · 4 civilian crew, 3-day orbital flight, Sept 2021</>}
          </div>
        </div>
        <span className="source-tag research">{data.user_added ? 'added data' : 'research data'}</span>
      </div>

      <div className="research-controls">
        <div className="seg">
          {datasets.map((d) => (
            <button key={d.dataset} className={d.dataset === dataset ? 'active' : ''} onClick={() => setDataset(d.dataset)}>
              {d.label ?? DATASET_LABELS[d.dataset] ?? d.dataset}
            </button>
          ))}
        </div>
        <select value={key} onChange={(e) => setKey(e.target.value)} className="env-select" aria-label="Marker">
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
          <YAxis domain={domain} stroke="var(--muted)" tick={{ fontSize: 11 }} allowDataOverflow tickFormatter={tick}
            label={{ value: analyte.unit, angle: -90, position: 'insideLeft', fill: 'var(--muted)', fontSize: 11 }} />
          {rows.some((r) => r.label === 'L-3') && rows.some((r) => r.label === 'R+1') && (
            <ReferenceArea x1="L-3" x2="R+1" fill="var(--accent)" fillOpacity={0.1}
              label={{ value: 'spaceflight', fill: 'var(--accent)', fontSize: 10, position: 'insideTop' }} />
          )}
          {(rmin != null || rmax != null) && (
            <ReferenceArea y1={rmin ?? domain[0]} y2={rmax ?? domain[1]} fill="var(--normal)" fillOpacity={0.08} ifOverflow="hidden" />
          )}
          <Tooltip content={<ChartTooltip unit={analyte.unit} />} />
          {data.crew.map((c) => (
            <Line key={c} type="linear" dataKey={c} stroke={colors[c]} strokeWidth={2}
              dot={<FlagDot />} connectNulls isAnimationActive={false} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      <div className="chart-legend">
        {data.crew.map((c) => <span key={c}><i className="sw" style={{ background: colors[c] }} /> {c}</span>)}
        {data.has_ranges ? (
          <>
            <span><i className="sw band" /> typical lab range (flags use each sample&apos;s own range)</span>
            <span><i className="sw ring" /> outside range</span>
          </>
        ) : <span className="muted">No clinical range for this assay: compare each line with its own preflight points</span>}
      </div>
      <p className="research-notice">
        {data.notice} Timepoints are days before launch (L−) and after return (R+).
        {!data.user_added && <> Crew IDs C001–C004 are the published de-identified codes, separate from AURA&apos;s synthetic demo crew.</>}
        {data.quality_issues.map((q) => (
          <span key={q.reason}> Excluded by AURA&apos;s quality check: {q.crew ? `${q.crew} at ${q.timepoint}. ` : ''}{q.reason}</span>
        ))}
      </p>
      {problems.length > 0 && (
        <p className="research-notice">
          {problems.map((p) => <span key={p.dataset}>Not shown: {p.problem} </span>)}
        </p>
      )}
      <ResearchReview
        crew={data.crew}
        colors={colors}
        focusCrew={focus?.crew}
        onSelectMarker={(name) => {
          const a = data.analytes.find((x) => x.name === name)
          if (a) setKey(a.key)
          else if (datasets.length > 1) {
            const i = datasets.findIndex((d) => d.dataset === dataset)
            setPending({ name, tries: 1 })
            setDataset(datasets[(i + 1) % datasets.length].dataset)
          }
          document.getElementById('research')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }}
      />
    </div>
  )
}
