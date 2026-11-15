import { useState } from 'react'
import { api } from '../api.js'

const FIELDS = [
  ['heart_rate', 1], ['systolic_bp', 1], ['diastolic_bp', 1], ['spo2', 1],
  ['glucose', 1], ['body_temp', 0.1], ['sleep_hours', 0.1], ['exercise_minutes', 5],
]

export default function CheckInForm({ crewId, catalog, disabled, onSaved, day, onNextDay, onSymptoms }) {
  const [values, setValues] = useState({})
  const [mood, setMood] = useState(7)
  const [useMood, setUseMood] = useState(false)
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [review, setReview] = useState(null) // plausibility check result awaiting the astronaut
  const [voiceText, setVoiceText] = useState('')
  const [heard, setHeard] = useState(null)
  const [listening, setListening] = useState(false)
  const Recognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

  const fillFrom = async (text) => {
    if (!text.trim()) return
    try {
      const r = await api.parseVoice(text)
      setHeard(r)
      const { mood: m, ...rest } = r.values
      setValues((v) => ({ ...v, ...Object.fromEntries(Object.entries(rest).map(([k, x]) => [k, String(x)])) }))
      if (m != null) { setMood(Math.round(m)); setUseMood(true) }
    } catch (err) {
      setMsg({ type: 'error', text: err.message })
    }
  }

  const listen = () => {
    if (!Recognition) return
    const rec = new Recognition()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.onresult = (e) => {
      const text = Array.from(e.results).map((x) => x[0].transcript).join(' ')
      setVoiceText(text)
      fillFrom(text)
    }
    rec.onerror = (e) => setMsg({ type: 'error', text: `Voice input: ${e.error}. You can type the sentence instead.` })
    rec.onend = () => setListening(false)
    setListening(true)
    setHeard(null)
    rec.start()
  }

  const save = async (payload) => {
    setBusy(true)
    try {
      const status = await api.checkin(crewId, { values: payload, note: note || undefined })
      setMsg({ type: 'ok', text: `Saved for day ${status.day}. Overall status: ${status.overall}.` })
      setValues({})
      setNote('')
      setUseMood(false)
      setReview(null)
      await onSaved()
    } catch (err) {
      setMsg({ type: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setReview(null)
    setMsg(null)
    const payload = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]),
    )
    if (useMood) payload.mood = mood
    if (!Object.keys(payload).length) {
      setMsg({ type: 'error', text: 'Enter at least one measurement.' })
      return
    }
    // Catch typos and unit mix-ups before they turn into false alerts.
    try {
      const check = await api.checkCheckin(crewId, { values: payload })
      if (!check.ok) { setReview({ ...check, payload }); return }
    } catch { /* if the check fails, the save still validates */ }
    await save(payload)
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
        <div className="voice">
          {Recognition && (
            <button type="button" className={`chip mic ${listening ? 'on' : ''}`} onClick={listen} disabled={listening}
              title="Speak your readings, e.g. 'heart rate 62, blood pressure 118 over 76, slept 7 hours'">
              {listening ? '● Listening…' : '🎙 Speak'}
            </button>
          )}
          <input value={voiceText} onChange={(e) => setVoiceText(e.target.value)} aria-label="Say or type your readings"
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); fillFrom(voiceText) } }}
            placeholder={Recognition ? 'or type: heart rate 62, BP 118 over 76, slept 7 h, mood 8' : 'Type: heart rate 62, BP 118 over 76, slept 7 h, mood 8'} />
          <button type="button" className="chip" onClick={() => fillFrom(voiceText)} disabled={!voiceText.trim()}>Fill form</button>
        </div>
        {heard && (
          <div className="heard">
            {heard.understood
              ? <>Filled {Object.keys(heard.values).length} reading(s) below. Check them, then Log check-in.</>
              : <>I couldn't find readings in that. Try “heart rate 62, blood pressure 118 over 76”.</>}
            {heard.symptoms.length > 0 && (
              <span> Symptoms mentioned: {heard.symptoms.map((x) => x.name).join(', ')}.{' '}
                <button type="button" className="link" onClick={() => onSymptoms?.(heard.symptoms.map((x) => x.key))}>Add to symptom log →</button>
              </span>
            )}
          </div>
        )}
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
        {review && (
          <div className={`plaus ${review.errors.length ? 'err' : 'warn'}`} role="alert">
            <strong>{review.errors.length ? 'Please fix before saving' : 'Please double-check'}</strong>
            <ul>
              {[...review.errors, ...review.warnings].map((x) => (
                <li key={x.message}>
                  {x.message}
                  {x.suggested != null && (
                    <button type="button" className="chip" onClick={() => {
                      setValues({ ...values, [x.indicator]: String(x.suggested) })
                      setReview(null)
                    }}>Use {x.suggested}</button>
                  )}
                </li>
              ))}
            </ul>
            {review.errors.length === 0 && (
              <div className="plaus-actions">
                <button type="button" className="chip" onClick={() => setReview(null)}>Edit values</button>
                <button type="button" className="primary small" onClick={() => save(review.payload)}>It's correct, save</button>
              </div>
            )}
          </div>
        )}
        {msg && <div className={`toast ${msg.type}`}>{msg.text}</div>}
        <p className="hint">Hover over a field to see how to take the measurement.</p>
      </fieldset>
    </form>
  )
}
