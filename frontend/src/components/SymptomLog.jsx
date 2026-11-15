import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { LEVEL } from '../levels.js'

export default function SymptomLog({ crewId, day, live, catalog, onOpenIndicator, onMessageGround, onLogged, prefill }) {
  const [options, setOptions] = useState([])
  const [data, setData] = useState(null)
  const [picked, setPicked] = useState({})
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => { api.symptomCatalog().then(setOptions).catch((e) => setErr(e.message)) }, [])
  useEffect(() => {
    let alive = true
    api.symptoms(crewId, live ? null : day).then((d) => alive && setData(d)).catch((e) => alive && setErr(e.message))
    return () => { alive = false }
  }, [crewId, day, live])

  const groups = useMemo(() => {
    const g = {}
    for (const o of options) (g[o.group] ??= []).push(o)
    return Object.entries(g)
  }, [options])
  const names = useMemo(() => Object.fromEntries(options.map((o) => [o.key, o.name])), [options])

  useEffect(() => {
    if (prefill?.key) setPicked((p) => ({ ...p, [prefill.key]: p[prefill.key] ?? 4 }))
  }, [prefill])

  const toggle = (k) => setPicked(({ [k]: had, ...rest }) => (had ? rest : { ...rest, [k]: 4 }))

  const submit = async (e) => {
    e.preventDefault()
    const items = Object.entries(picked).map(([key, severity]) => ({ key, severity }))
    if (!items.length) { setErr('Pick at least one symptom.'); return }
    setBusy(true)
    setErr(null)
    try {
      setData(await api.logSymptoms(crewId, { symptoms: items, note: note || undefined }))
      setPicked({})
      setNote('')
      onLogged?.()
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  const t = data?.triage
  const lvl = t ? LEVEL[t.level] : null
  return (
    <section className="panel symptoms" id="symptoms">
      <div className="panel-head">
        <h2>🩺 Symptom log · day {data?.day ?? day}</h2>
        {lvl && <span className={`badge ${lvl.cls}`}>{lvl.icon} {t.level === 'normal' ? 'Self-care' : lvl.label}</span>}
      </div>
      <div className="sym-grid">
        <form onSubmit={submit}>
          <fieldset disabled={!live || busy}>
            <p className="muted small">{live ? 'How do you feel today? Pick any symptoms and rate them 1 (mild) to 10 (worst).' : 'Return to live to log symptoms.'}</p>
            {groups.map(([g, list]) => (
              <div key={g} className="sym-group">
                <span className="sym-group-name">{g}</span>
                <div className="sym-chips">
                  {list.map((o) => (
                    <button type="button" key={o.key} title={o.why}
                      className={`sym-chip ${picked[o.key] ? 'on' : ''} ${o.red_flag ? 'red' : ''}`}
                      onClick={() => toggle(o.key)}>{o.red_flag && <i className="dot" />}{o.name}</button>
                  ))}
                </div>
              </div>
            ))}
            {Object.keys(picked).length > 0 && (
              <div className="sym-sev">
                {Object.entries(picked).map(([k, v]) => (
                  <label key={k}>
                    <span>{names[k]} <strong>{v}/10</strong></span>
                    <input type="range" min={1} max={10} value={v} onChange={(e) => setPicked({ ...picked, [k]: Number(e.target.value) })} />
                  </label>
                ))}
                <input className="sym-note" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} placeholder="Anything else? (optional)" />
                <button type="submit" className="primary">{busy ? 'Triaging…' : 'Log and triage'}</button>
              </div>
            )}
            <p className="hint"><i className="dot" /> Red-flag symptoms always mean: contact the flight surgeon now.</p>
          </fieldset>
          {err && <div className="toast error">{err}</div>}
        </form>

        <div className="sym-result">
          {t && (
            <div className={`triage ${lvl.cls}`}>
              <h3>Triage</h3>
              <ul>{t.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              {t.actions.length > 0 && <ol className="sym-actions">{t.actions.map((a) => <li key={a}>{a}</li>)}</ol>}
              {t.related_indicators.length > 0 && (
                <div className="sym-related">
                  <span className="muted small">Check:</span>
                  {t.related_indicators.map((k) => (
                    <button key={k} className="chip" onClick={() => onOpenIndicator(k)}>{catalog[k]?.name ?? k}</button>
                  ))}
                </div>
              )}
              {t.escalate && live && (
                <button className="chip urgent" onClick={() => onMessageGround(t)}>📡 Message ground now →</button>
              )}
            </div>
          )}
          <h3 className="sym-hist-title">Recent log</h3>
          <ol className="sym-hist">
            {data?.log.slice(0, 6).map((e, i) => (
              <li key={`${e.day}-${i}`}>
                <span className="t-day">Day {e.day}</span>
                <span>{e.symptoms.map((x) => `${x.name} ${x.severity}/10`).join(', ')}
                  {e.note && <em className="muted"> · “{e.note}”</em>}
                  {e.source === 'synthetic' && <span className="source-tag"> demo</span>}
                </span>
              </li>
            ))}
            {data && data.log.length === 0 && <li className="muted">Nothing logged yet.</li>}
          </ol>
        </div>
      </div>
    </section>
  )
}
