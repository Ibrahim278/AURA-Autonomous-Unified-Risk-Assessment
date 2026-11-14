import { useState } from 'react'
import { api } from '../api.js'

const FIELDS = [
  ['heart_rate', 1], ['systolic_bp', 1], ['diastolic_bp', 1], ['spo2', 1],
  ['glucose', 1], ['body_temp', 0.1], ['sleep_hours', 0.1], ['exercise_minutes', 5],
]

export default function CheckInForm({ crewId, catalog, disabled, onSaved, day, onNextDay }) {
  const [values, setValues] = useState({})
  const [mood, setMood] = useState(7)
  const [useMood, setUseMood] = useState(false)
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    const payload = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]),
    )
    if (useMood) payload.mood = mood
    if (!Object.keys(payload).length) {
      setMsg({ type: 'error', text: 'Enter at least one measurement.' })
      return
    }
    setBusy(true)
    try {
      const status = await api.checkin(crewId, { values: payload, note: note || undefined })
      setMsg({ type: 'ok', text: `Saved for day ${status.day}. Overall status: ${status.overall}.` })
      setValues({})
      setNote('')
      setUseMood(false)
      await onSaved()
    } catch (err) {
      setMsg({ type: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="checkin" onSubmit={submit}>
      <div className="panel-head">
        <h2>Daily check-in{day ? ` · day ${day}` : ''}</h2>
        {disabled
          ? <span className="muted">Return to live to log readings</span>
          : onNextDay && (
            <button type="button" className="chip next-day" disabled={busy} title="Advance the mission one day. Synthetic crew get new readings; log yours here."
              onClick={async () => {
                setBusy(true)
                try {
                  const m = await onNextDay()
                  setMsg({ type: 'ok', text: `Mission day ${m.current_day} has started. Log today's readings.` })
                } catch (err) {
                  setMsg({ type: 'error', text: err.message })
                } finally {
                  setBusy(false)
                }
              }}>▶ Next day</button>
          )}
      </div>
      <fieldset disabled={disabled || busy}>
        <div className="fields">
          {[...FIELDS, ...Object.values(catalog).filter((i) => i.custom).map((i) => [i.key, 10 ** -i.decimals])].map(([key, step]) => {
            const ind = catalog[key]
            if (!ind) return null
            return (
              <label key={key} title={ind.how_to_measure}>
                <span>{ind.name} <span className="muted">({ind.unit})</span></span>
                <input
                  type="number"
                  step={step}
                  value={values[key] ?? ''}
                  onChange={(e) => setValues({ ...values, [key]: e.target.value })}
                  placeholder="—"
                />
              </label>
            )
          })}
        </div>
        <label className="mood">
          <span>
            <input type="checkbox" checked={useMood} onChange={(e) => setUseMood(e.target.checked)} />
            {' '}Mood today: <strong>{mood}/10</strong>
          </span>
          <input type="range" min={1} max={10} value={mood} onChange={(e) => { setMood(Number(e.target.value)); setUseMood(true) }} />
        </label>
        <label className="note">
          <span>Notes or symptoms</span>
          <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="For example: mild headache after EVA" />
        </label>
        <button type="submit" className="primary">{busy ? 'Saving…' : 'Log check-in'}</button>
        {msg && <div className={`toast ${msg.type}`}>{msg.text}</div>}
        <p className="hint">Hover over a field to see how to take the measurement.</p>
      </fieldset>
    </form>
  )
}
