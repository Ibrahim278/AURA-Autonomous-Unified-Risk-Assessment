import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const secs = (iso) => (new Date(iso).getTime() - Date.now()) / 1000
const AUTHOR_KEY = 'aura-console-author'

// The ground side of the link, played by a person. Open it on a second laptop or phone:
// crew messages appear only once their signal has reached Earth, and replies typed here
// travel back to the crew with the same one-way delay.
export default function GroundConsole({ refreshKey }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [author, setAuthor] = useState(() => {
    try { return localStorage.getItem(AUTHOR_KEY) || 'Flight surgeon' } catch { return 'Flight surgeon' }
  })
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState(null)
  const [, tick] = useState(0)
  const seen = useRef(new Set())

  const load = async () => {
    try { setData(await api.groundInbox()); setErr(null) } catch (e) { setErr(e.message) }
  }

  useEffect(() => {
    load()
    const t = setInterval(() => { tick((n) => n + 1); load() }, 2000)
    return () => clearInterval(t)
  }, [refreshKey])

  // Opening the console counts as reading: the crew sees "Seen by flight surgeon".
  useEffect(() => {
    if (data?.mode !== 'live') return
    for (const m of data.messages) {
      if (!m.seen_at && !seen.current.has(m.id)) {
        seen.current.add(m.id)
        api.groundSeen(m.id).catch(() => seen.current.delete(m.id))
      }
    }
  }, [data])

  useEffect(() => { try { localStorage.setItem(AUTHOR_KEY, author) } catch { /* storage blocked */ } }, [author])

  const setMode = async (mode) => {
    try { await api.setCommsMode(mode); await load() } catch (e) { setErr(e.message) }
  }

  const reply = async (m) => {
    const text = (drafts[m.id] ?? '').trim()
    if (!text) return
    setBusy(m.id)
    try {
      await api.groundReply(m.id, { text, author: author.trim() || 'Flight surgeon' })
      setDrafts((d) => ({ ...d, [m.id]: '' }))
      await load()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(null)
    }
  }

  const live = data?.mode === 'live'
  const link = data?.link
  const open = data?.messages.filter((m) => m.replies.length === 0).length ?? 0

  return (
    <div className="console" id="console">
      <div className="panel console-head">
        <div className="console-mode" role="group" aria-label="Who answers crew messages">
          <button className={`chip ${!live ? 'on' : ''}`} aria-pressed={!live} onClick={() => setMode('simulated')}>Simulated ground</button>
          <button className={`chip ${live ? 'on' : ''}`} aria-pressed={live} onClick={() => setMode('live')}>● Live operator</button>
        </div>
        <p className="muted small">
          {live
            ? 'You are the ground. New crew messages show up here when their signal reaches Earth. Your reply travels back with the same delay.'
            : 'AURA answers crew messages with a simulated flight surgeon. Switch to Live operator to answer them yourself.'}
        </p>
        <div className="console-stats">
          {link && <span><strong>{link.one_way}</strong> <span className="muted">one way</span></span>}
          <span><strong>{data?.in_transit ?? 0}</strong> <span className="muted">on the way to Earth</span></span>
          <span><strong>{open}</strong> <span className="muted">waiting for a reply</span></span>
          <label className="console-author">
            <span className="muted">Sign replies as</span>
            <input value={author} onChange={(e) => setAuthor(e.target.value)} maxLength={80} aria-label="Sign replies as" />
          </label>
        </div>
        <p className="hint">Two devices: open AURA on a second laptop or phone at the same address and pick Console. One person is the crew, the other is ground.</p>
      </div>

      {err && <div className="toast error">{err}</div>}
      {data && data.messages.length === 0 && (
        <div className="panel muted">No crew messages have reached Earth yet{data.in_transit ? `. ${data.in_transit} on the way.` : '. Send one from Message ground.'}</div>
      )}

      <ol className="console-list">
        {data?.messages.map((m) => (
          <li key={m.id} className={`panel console-msg ${m.priority === 'urgent' ? 'urgent' : ''}`}>
            <div className="msg-head">
              <strong>{m.crew_name}</strong>
              {m.priority === 'urgent' && <span className="badge lvl-critical">Urgent</span>}
              <span className="muted"> · day {m.day} · reached Earth {Math.max(0, -secs(m.arrives_at)).toFixed(0)} s ago</span>
            </div>
            <div className="msg-text">{m.text}</div>
            {m.status_packet && (
              <div className="packet">
                <span className={`badge lvl-${m.status_packet.overall}`}>{m.status_packet.overall}</span>
                {m.status_packet.flagged.length > 0
                  ? <span className="muted small"> {m.status_packet.flagged.join(' · ')}</span>
                  : <span className="muted small"> Nothing flagged</span>}
              </div>
            )}
            {m.replies.map((r) => (
              <div key={r.id} className="console-reply">
                <span className="muted small">{r.author}{r.simulated ? ' (simulated)' : ''}:</span> {r.text}
                <div className="muted tiny">
                  {secs(r.arrives_at) > 0 ? `Travelling to the crew, arrives in ${secs(r.arrives_at).toFixed(0)} s on the demo clock` : 'Delivered to the crew'}
                </div>
              </div>
            ))}
            {live && m.replies.length === 0 && (
              <form className="console-form" onSubmit={(e) => { e.preventDefault(); reply(m) }}>
                <textarea rows={2} value={drafts[m.id] ?? ''} aria-label={`Reply to ${m.crew_name}`}
                  onChange={(e) => setDrafts((d) => ({ ...d, [m.id]: e.target.value }))}
                  placeholder={`Reply to ${m.crew_name.split(' ')[0]}. It arrives after ${link?.one_way ?? 'the signal delay'}.`} />
                <button className="primary small" disabled={busy === m.id || !(drafts[m.id] ?? '').trim()}>
                  {busy === m.id ? 'Sending…' : 'Send reply'}
                </button>
              </form>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
