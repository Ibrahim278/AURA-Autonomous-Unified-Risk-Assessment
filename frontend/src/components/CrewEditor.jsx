import { useEffect, useState } from 'react'
import { api } from '../api.js'

const blank = (scenario = 'nominal') => ({ name: '', role: 'Mission Specialist', age: 35, scenario, baseline: {} })

function ImportForm({ roles, full, onImported, onCancel }) {
  const [name, setName] = useState('')
  const [role, setRole] = useState('Mission Specialist')
  const [age, setAge] = useState(35)
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const csv = await file.text()
      const r = await api.importCrew({ name: name.trim(), role, age: Number(age), csv })
      await onImported(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="crew-row import-form">
      <h3>⬆ Import your own data</h3>
      <p className="muted small">
        A CSV with a <code>day</code> column and one column per indicator (heart_rate, systolic_bp, diastolic_bp,
        spo2, glucose, body_temp, sleep_hours, mood, exercise_minutes, radiation_dose). Days −7 to −1 are
        preflight and build your personal baseline; days 1, 2, 3… are mission days. Blank cells are fine.{' '}
        <a href={api.importTemplateUrl} download>Download the template</a>.
      </p>
      <div className="crew-row-main">
        <input aria-label="Import name" placeholder="Your name" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
        <select aria-label="Import role" value={role} onChange={(e) => setRole(e.target.value)}>
          {roles.map((x) => <option key={x}>{x}</option>)}
        </select>
        <input aria-label="Import age" type="number" min={18} max={80} value={age} className="age" onChange={(e) => setAge(e.target.value)} />
        <input aria-label="CSV file" type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>
      {full && <p className="muted small">The crew is full (6). Remove someone and save first.</p>}
      {error && <div className="toast error">{error}</div>}
      <div className="modal-foot">
        <span style={{ flex: 1 }} />
        <button onClick={onCancel}>Back</button>
        <button className="primary" disabled={busy || !file || !name.trim() || full} onClick={submit}>
          {busy ? 'Importing…' : 'Import and add to crew'}
        </button>
      </div>
    </div>
  )
}

export default function CrewEditor({ crew, onClose, onSaved, startImport = false }) {
  const [importing, setImporting] = useState(startImport)
  const [notice, setNotice] = useState(null)
  const [opts, setOpts] = useState(null)
  const [rows, setRows] = useState(() =>
    crew.map(({ id, name, role, age, scenario, baseline, data_source, scenario_description }) =>
      ({ id, name, role, age, scenario, baseline: { ...baseline }, imported: data_source === 'imported', note: scenario_description })))
  const [open, setOpen] = useState(null) // index whose baselines are expanded
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.crewOptions().then(setOpts).catch((e) => setError(e.message))
  }, [])

  const update = (i, patch) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const setBase = (i, key, raw) =>
    setRows((rs) => rs.map((r, j) => {
      if (j !== i) return r
      const baseline = { ...r.baseline }
      if (raw === '') delete baseline[key]
      else baseline[key] = Number(raw)
      return { ...r, baseline }
    }))

  const save = async (list) => {
    setSaving(true)
    setError(null)
    try {
      const saved = await api.setCrew({
        crew: list.map(({ imported, note, ...r }) => ({ ...r, age: Number(r.age), scenario: imported ? 'nominal' : r.scenario })),
      })
      await onSaved(saved)
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const scen = (k) => opts?.scenarios.find((s) => s.key === k)
  const invalid = rows.some((r) => !r.name.trim())

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal crew-editor" role="dialog" aria-label="Edit crew" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <h2>Edit crew</h2>
          <button className="link" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <p className="muted small">
          Each member gets synthetic telemetry from their personal baselines and the health scenario you
          pick. Saving regenerates the mission (manual check-ins are cleared), and the AI briefing reads the
          new data. The AI never sees the scenario name, so it has to find the pattern itself.
        </p>

        {!opts && !error && <p className="muted">Loading…</p>}
        {notice && <div className="toast ok">{notice}</div>}
        {opts && importing && (
          <ImportForm
            roles={opts.roles}
            full={crew.length >= 6}
            onCancel={() => setImporting(false)}
            onImported={async (r) => {
              await onSaved([...crew, r.member], r.member.id)
              const w = r.warnings.length ? ` Note: ${r.warnings.join(' ')}` : ''
              setNotice(`Added ${r.member.name}: ${r.readings} readings up to mission day ${r.last_day}.${w}`)
              const m = r.member
              setRows((rs) => [...rs, { id: m.id, name: m.name, role: m.role, age: m.age, scenario: m.scenario,
                baseline: {}, imported: true, note: m.scenario_description }])
              setImporting(false)
              if (!r.warnings.length) onClose()
            }}
          />
        )}
        {opts && !importing && rows.map((r, i) => (
          <div className="crew-row" key={r.id ?? `new-${i}`}>
            <div className="crew-row-main">
              <input aria-label="Name" placeholder="Name" value={r.name} maxLength={60}
                onChange={(e) => update(i, { name: e.target.value })} />
              <select aria-label="Role" value={r.role} onChange={(e) => update(i, { role: e.target.value })}>
                {[...new Set([...opts.roles, r.role])].map((x) => <option key={x}>{x}</option>)}
              </select>
              <input aria-label="Age" type="number" min={18} max={80} value={r.age} className="age"
                onChange={(e) => update(i, { age: e.target.value })} />
              {r.imported ? (
                <span className="source-tag imported">your data</span>
              ) : (
                <>
                  <select aria-label="Health scenario" value={r.scenario} onChange={(e) => update(i, { scenario: e.target.value })}>
                    {opts.scenarios.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                  </select>
                  <button className="link" onClick={() => setOpen(open === i ? null : i)}>
                    Baselines{Object.keys(r.baseline).length ? ` (${Object.keys(r.baseline).length})` : ''}
                  </button>
                </>
              )}
              <button className="link danger" disabled={rows.length <= 1} onClick={() => setRows(rows.filter((_, j) => j !== i))}
                aria-label={`Remove ${r.name || 'member'}`}>Remove</button>
            </div>
            <p className="muted small scen-desc">{r.imported ? r.note : scen(r.scenario)?.description}</p>
            {open === i && !r.imported && (
              <div className="baseline-grid">
                {opts.baselines.map((b) => (
                  <label key={b.key}>
                    <span>{b.name} <em>{b.unit}</em></span>
                    <input type="number" step="any" min={b.min} max={b.max} placeholder={String(b.default)}
                      value={r.baseline[b.key] ?? ''} onChange={(e) => setBase(i, b.key, e.target.value)} />
                  </label>
                ))}
                <p className="muted small">Leave blank for the typical value shown.</p>
              </div>
            )}
          </div>
        ))}

        {error && <div className="toast error">{error}</div>}
        {!importing && <div className="modal-foot">
          <button className="link" disabled={rows.length >= 6} onClick={() => setRows([...rows, blank()])}>+ Add member</button>
          <button className="link" disabled={crew.length >= 6} onClick={() => setImporting(true)}>⬆ Import your data</button>
          <button className="link" disabled={!opts || saving} onClick={() => save(opts.default_crew)}>Restore demo crew</button>
          <span style={{ flex: 1 }} />
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={saving || invalid || !opts} onClick={() => save(rows)}>
            {saving ? 'Generating mission…' : 'Save and regenerate'}
          </button>
        </div>}
      </div>
    </div>
  )
}
