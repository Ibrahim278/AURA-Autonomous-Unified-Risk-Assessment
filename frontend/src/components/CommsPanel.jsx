import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const secs = (iso) => (new Date(iso).getTime() - Date.now()) / 1000

function fmtTrue(s) {
  return s < 60 ? `${s.toFixed(1)} s` : `${(s / 60).toFixed(1)} min`
}

function Transit({ m, label, from }) {
  const total = (new Date(m.arrives_at) - new Date(from ?? m.sent_at)) / 1000
  const left = Math.max(0, secs(m.arrives_at))
  const pct = total > 0 ? Math.min(100, 100 * (1 - left / total)) : 100
  return (
    <div className="transit">
      <div className="transit-bar"><span style={{ width: `${pct}%` }} /></div>
      <span className="muted">{label} · {left.toFixed(0)} s on the demo clock</span>
    </div>
  )
}

export default function CommsPanel({ crewId, member, live, prefill }) {
  const [data, setData] = useState(null)
  const [text, setText] = useState('')
  const [urgent, setUrgent] = useState(false)
  const [attach, setAttach] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [, tick] = useState(0)
  const boxRef = useRef(null)

  useEffect(() => {
    let alive = true
    api.messages(crewId).then((d) => alive && setData(d)).catch((e) => alive && setErr(e.message))
    return () => { alive = false }
  }, [crewId])

  useEffect(() => {
    if (!prefill) return
    setUrgent(prefill.urgent)
    setText(prefill.text)
    setAttach(true)
    boxRef.current?.focus()
  }, [prefill])

  // While anything is in flight, refresh the countdown every second and pull arrived replies.
  const waiting = data?.messages.some((m) => m.pending || (m.direction === 'to_ground' && secs(m.arrives_at) > 0))
  useEffect(() => {
    if (!waiting) return
    const t = setInterval(async () => {
      tick((n) => n + 1)
      const due = data.messages.some((m) => m.pending && secs(m.arrives_at) <= 0)
      if (due) setData(await api.messages(crewId))
    }, 1000)
    return () => clearInterval(t)
  }, [waiting, data, crewId])

  const send = async (e) => {
    e.preventDefault()
    if (!text.trim()) return
    setBusy(true)
    setErr(null)
    try {
      setData(await api.sendMessage(crewId, { text, priority: urgent ? 'urgent' : 'routine', attach_status: attach }))
      setText('')
      setUrgent(false)
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  const link = data?.link
  return (
    <div className="comms" id="comms">
      <div className="panel-head">
        <h2>📡 Message ground</h2>
        {link && <span className={`pill ${link.mode === 'autonomous' ? 'pill-warn' : 'pill-ok'}`}>
          {link.mode === 'autonomous' ? 'Delayed' : 'Live'}
        </span>}
      </div>
      {link && (
        <div className="link-delay" title={link.source}>
          <div><strong>{link.one_way}</strong> <span className="muted">one way</span></div>
          <div><strong>{link.round_trip}</strong> <span className="muted">round trip</span></div>
          <p className="muted">{link.explanation}</p>
        </div>
      )}
      <ol className="msg-log">
        {data?.messages.map((m) => m.pending ? (
          <li key={m.id} className="msg from-ground pending">
            <div className="msg-head">Flight surgeon</div>
            <Transit m={m} from={data.messages.find((o) => o.id === m.in_reply_to)?.sent_at}
              label={secs(m.sent_at) > 0 ? 'Waiting for ground to receive and answer' : 'Reply travelling back to you'} />
          </li>
        ) : (
          <li key={m.id} className={`msg ${m.direction === 'to_ground' ? 'to-ground' : 'from-ground'}`}>
            <div className="msg-head">
              {m.direction === 'to_ground' ? 'You' : m.author}
              {m.priority === 'urgent' && m.direction === 'to_ground' && <span className="badge lvl-critical">Urgent</span>}
              <span className="muted"> · day {m.day}</span>
            </div>
            <div className="msg-text">{m.text}</div>
            {m.status_packet && (
              <div className="muted packet">Status packet: {m.status_packet.overall}
                {m.status_packet.flagged.length > 0 && ` · ${m.status_packet.flagged.length} flagged`}</div>
            )}
            {m.direction === 'to_ground' && secs(m.arrives_at) > 0
              ? <Transit m={m} label={`Travelling to Earth (${fmtTrue(m.delay_s)} real delay)`} />
              : m.direction === 'to_ground' && <div className="muted delivered">✓ Delivered to Earth</div>}
            {m.simulated && <div className="muted sim">Simulated ground response (demo)</div>}
          </li>
        ))}
      </ol>
      <form onSubmit={send}>
        <fieldset disabled={busy || !live}>
          <textarea ref={boxRef} rows={2} value={text} onChange={(e) => setText(e.target.value)}
            placeholder={live ? `Message the flight surgeon as ${member?.name ?? 'crew'}` : 'Return to live to send'} />
          <div className="comms-opts">
            <label><input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} /> Urgent</label>
            <label title="Sends today's levels and flagged readings with the message">
              <input type="checkbox" checked={attach} onChange={(e) => setAttach(e.target.checked)} /> Attach status
            </label>
            <button type="submit" className="primary small">{busy ? 'Sending…' : 'Send'}</button>
          </div>
        </fieldset>
        {err && <div className="toast error">{err}</div>}
      </form>
      {link?.mode === 'autonomous' && (
        <p className="hint">The demo clock runs {link.demo_speed}× faster: each minute of signal delay takes one second here.</p>
      )}
    </div>
  )
}
