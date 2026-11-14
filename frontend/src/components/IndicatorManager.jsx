import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { HAZARD_LABEL, SYSTEM_LABEL } from '../levels.js'

// One-click starting points; every field stays editable.
const PRESETS = [
  { name: 'Body weight', unit: 'kg', body_system: 'musculoskeletal', hazards: ['gravity_fields'], adverse_direction: 'low',
    typical_low: 65, typical_high: 75, warning_low: 62, critical_low: 58, decimals: 1,
    why_it_matters: 'Weight loss in flight usually means eating too little, and it speeds up muscle and bone loss.',
    how_to_measure: 'Mass-measurement device (or scale on a surface), same time each morning after the bathroom.' },
  { name: 'Heart rate variability', unit: 'ms', body_system: 'heart', hazards: ['isolation_confinement', 'gravity_fields'], adverse_direction: 'low',
    typical_low: 45, typical_high: 75, warning_low: 30, critical_low: 18, decimals: 0,
    why_it_matters: 'HRV (RMSSD) falls with stress, fatigue, poor sleep and illness, often before you notice symptoms.',
    how_to_measure: 'Morning reading from the wearable, lying still for 2 minutes after waking.' },
  { name: 'Daily steps', unit: 'steps', body_system: 'musculoskeletal', hazards: ['gravity_fields'], adverse_direction: 'low',
    typical_low: 6000, typical_high: 10000, warning_low: 3000, critical_low: 1000, decimals: 0,
    why_it_matters: 'On a planetary surface, daily movement protects bone, muscle and mood.',
    how_to_measure: 'Total from the wearable at the end of the day.' },
  { name: 'Water intake', unit: 'L', body_system: 'metabolic', hazards: ['gravity_fields', 'hostile_closed_environment'], adverse_direction: 'low',
    typical_low: 2, typical_high: 3, warning_low: 1.5, critical_low: 1, decimals: 1,
    why_it_matters: 'Fluid shifts blunt thirst in microgravity; low intake raises kidney-stone and fainting risk.',
    how_to_measure: 'Sum of drink-bag volumes logged through the day.' },
]

const EMPTY = { name: '', unit: '', body_system: 'whole_body', hazards: [], adverse_direction: 'both', typical_low: '', typical_high: '',
  warning_low: '', warning_high: '', critical_low: '', critical_high: '', decimals: 1, use_baseline: true, why_it_matters: '', how_to_measure: '' }

const num = (v) => (v === '' || v === null || v === undefined ? null : Number(v))

export default function IndicatorManager({ catalog, onClose, onChanged }) {
  const [opts, setOpts] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    api.indicatorOptions().then(setOpts).catch((e) => setError(e.message))
  }, [])

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  const custom = Object.values(catalog).filter((i) => i.custom)

  const save = async () => {
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      const body = { ...form, decimals: Number(form.decimals) }
      for (const k of ['typical_low', 'typical_high', 'warning_low', 'warning_high', 'critical_low', 'critical_high']) body[k] = num(form[k])
      const ind = await api.addIndicator(body)
      await onChanged(ind.key)
      setMsg(`Added ${ind.name}. Every crew member now tracks it; log it in the check-in or include a "${ind.key}" column in a CSV import.`)
      setForm(EMPTY)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (key) => {
    setError(null)
    try {
      await api.deleteIndicator(key)
      await onChanged(null)
    } catch (e) {
      setError(e.message)
    }
  }

  const field = (k, label, props = {}) => (
    <label>
      <span>{label}</span>
      <input value={form[k] ?? ''} onChange={(e) => set({ [k]: e.target.value })} {...props} />
    </label>
  )
  const numField = (k, label) => field(k, label, { type: 'number', step: 'any' })
  const valid = form.name.trim().length >= 2 && form.unit.trim() && form.typical_low !== '' && form.typical_high !== ''

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal indicator-manager" role="dialog" aria-label="Custom indicators" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <h2>Add an indicator</h2>
          <button className="link" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <p className="muted small">
          Track any measurement alongside the built-in ten. AURA learns each person&apos;s baseline from their
          preflight days and applies your warning and critical limits. Synthetic crew get synthetic readings for
          it; your own data comes from check-ins or a CSV import. Your limits are not clinically validated.
        </p>

        {custom.length > 0 && (
          <div className="custom-list">
            <h4>Your indicators</h4>
            {custom.map((i) => (
              <span key={i.key} className="tag">
                {i.name} ({i.unit})
                <button className="link danger" onClick={() => remove(i.key)} aria-label={`Remove ${i.name}`}>✕</button>
              </span>
            ))}
          </div>
        )}

        <div className="presets">
          <span className="muted small">Start from:</span>
          {PRESETS.map((p) => (
            <button key={p.name} className="chip" disabled={!!catalog[p.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')]}
              onClick={() => setForm({ ...EMPTY, ...p })}>{p.name}</button>
          ))}
        </div>

        <div className="ind-form">
          {field('name', 'Name', { placeholder: 'e.g. Body weight', maxLength: 40 })}
          {field('unit', 'Unit', { placeholder: 'kg', maxLength: 16 })}
          <label>
            <span>Body system</span>
            <select value={form.body_system} onChange={(e) => set({ body_system: e.target.value })}>
              {(opts?.body_systems ?? []).map((b) => <option key={b} value={b}>{SYSTEM_LABEL[b] ?? b}</option>)}
            </select>
          </label>
          <label>
            <span>Worse when it goes</span>
            <select value={form.adverse_direction} onChange={(e) => set({ adverse_direction: e.target.value })}>
              <option value="low">Down</option><option value="high">Up</option><option value="both">Either way</option>
            </select>
          </label>
          {numField('typical_low', 'Typical range: low')}
          {numField('typical_high', 'Typical range: high')}
          {numField('warning_low', 'Warning below')}
          {numField('warning_high', 'Warning above')}
          {numField('critical_low', 'Critical below')}
          {numField('critical_high', 'Critical above')}
          <label>
            <span>Decimals</span>
            <select value={form.decimals} onChange={(e) => set({ decimals: e.target.value })}>
              {[0, 1, 2, 3].map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
          <label className="check">
            <span>Personal baseline</span>
            <span><input type="checkbox" checked={form.use_baseline} onChange={(e) => set({ use_baseline: e.target.checked })} /> Compare with each person&apos;s preflight baseline</span>
          </label>
          <fieldset className="hazard-pick">
            <legend>NASA hazards it relates to</legend>
            {(opts?.hazards ?? []).map((h) => (
              <label key={h}>
                <input type="checkbox" checked={form.hazards.includes(h)}
                  onChange={(e) => set({ hazards: e.target.checked ? [...form.hazards, h] : form.hazards.filter((x) => x !== h) })} />
                {' '}{HAZARD_LABEL[h] ?? h}
              </label>
            ))}
          </fieldset>
          <label className="wide"><span>Why it matters</span>
            <textarea rows={2} maxLength={600} value={form.why_it_matters} onChange={(e) => set({ why_it_matters: e.target.value })} /></label>
          <label className="wide"><span>How to measure</span>
            <textarea rows={2} maxLength={400} value={form.how_to_measure} onChange={(e) => set({ how_to_measure: e.target.value })} /></label>
        </div>

        {error && <div className="toast error">{error}</div>}
        {msg && <div className="toast ok">{msg}</div>}
        <div className="modal-foot">
          <span className="muted small">Leave any limit blank for no limit on that side.</span>
          <span style={{ flex: 1 }} />
          <button onClick={onClose}>Done</button>
          <button className="primary" disabled={busy || !valid} onClick={save}>{busy ? 'Adding…' : 'Add indicator'}</button>
        </div>
      </div>
    </div>
  )
}
