import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

function suggestionsFor(member, selectedName) {
  const s = []
  if (member) s.push(`How is ${member.name.split(' ').slice(-2, -1)[0] ?? member.name} doing today?`)
  if (selectedName) s.push(`What should I do about ${selectedName.toLowerCase()}?`)
  s.push('How do I import my own data?', 'What does a warning mean?', 'Show me the real NASA data')
  return s.slice(0, 4)
}

const CHAT_KEY = 'aura-chat-v1'

function loadChat() {
  try { return JSON.parse(localStorage.getItem(CHAT_KEY)) ?? [] } catch { return [] }
}

export default function AssistantWidget({ crewId, member, day, live, selected, selectedName, onAction, openSignal = 0, onOpenChange, highlight = false }) {
  const [open, setOpen] = useState(false)
  const [chat, setChat] = useState(loadChat)
  const [memory, setMemory] = useState([])
  const [showMemory, setShowMemory] = useState(false)
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const end = useRef(null)
  const input = useRef(null)

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [chat, busy])

  useEffect(() => {
    if (open) input.current?.focus()
  }, [open])

  // Keep the conversation across reloads (this browser only).
  useEffect(() => {
    try { localStorage.setItem(CHAT_KEY, JSON.stringify(chat.slice(-30))) } catch { /* storage unavailable */ }
  }, [chat])

  useEffect(() => {
    if (open) api.memory(crewId).then(setMemory).catch(() => {})
  }, [open, crewId])

  const act = async (a) => {
    if (a.type !== 'remember') { onAction(a); return }
    try {
      await api.addMemory({ text: a.target, crew_id: crewId ?? null })
      setMemory(await api.memory(crewId))
      setChat((c) => [...c, { role: 'note', content: `🧠 Saved to memory: “${a.target}”` }])
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    if (openSignal) setOpen(true)
  }, [openSignal])

  // While the chat is open the demo tour card steps aside; minimising brings it back.
  useEffect(() => {
    onOpenChange?.(open)
  }, [open, onOpenChange])

  const send = async (text) => {
    const q = (text ?? question).trim()
    if (!q || busy) return
    const history = chat.filter((m) => m.role !== 'note').slice(-20)
      .map((m) => ({ role: m.role, content: m.role === 'user' ? m.content : m.reply.answer }))
    setChat((c) => [...c, { role: 'user', content: q }])
    setQuestion('')
    setBusy(true)
    setError(null)
    try {
      const r = await api.assistant({ question: q, history, crew_id: crewId, day: live ? null : day, indicator: selected })
      setChat((c) => [...c, { role: 'assistant', reply: r.reply, mode: r.mode, note: r.note }])
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {!open && (
        <button className={`assistant-fab ${highlight ? 'pulse' : ''}`} onClick={() => setOpen(true)} aria-label="Ask AURA">
          <span className="fab-icon">✦</span> Ask AURA
        </button>
      )}
      {open && (
        <div className="aura-assistant" role="dialog" aria-label="Ask AURA">
          <div className="assistant-head">
            <div>
              <strong>✦ Ask AURA</strong>
              <div className="muted small">
                {member ? `Viewing ${member.name} · day ${day}${selectedName ? ` · ${selectedName}` : ''}` : 'Ask anything about AURA'}
              </div>
            </div>
            <span className="assistant-head-actions">
              <button className="link" onClick={() => setShowMemory((v) => !v)} title="Notes Ask AURA remembers">🧠 {memory.length}</button>
              {chat.length > 0 && <button className="link" onClick={() => setChat([])}>Clear</button>}
              <button className="link" onClick={() => setOpen(false)} aria-label="Minimise">—</button>
            </span>
          </div>

          {showMemory && (
            <div className="assistant-memory">
              <strong>Memory</strong>
              <span className="muted tiny"> Ask “remember that …” to add a note. AURA uses these in answers.</span>
              {memory.length === 0 && <p className="muted small">Nothing saved yet.</p>}
              <ul>
                {memory.map((n) => (
                  <li key={n.id}>
                    <span>{n.text}{n.crew_id ? '' : <em className="muted"> · everyone</em>}</span>
                    <button className="link" aria-label="Forget" onClick={async () => {
                      await api.deleteMemory(n.id)
                      setMemory(await api.memory(crewId))
                    }}>✕</button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="assistant-log" aria-live="polite">
            {chat.length === 0 && (
              <div className="assistant-welcome">
                <p>Hi! Ask me about crew health, what to do next, how to use AURA, or the real NASA data.</p>
                <div className="suggestions">
                  {suggestionsFor(member, selectedName).map((s) => (
                    <button key={s} className="chip" onClick={() => send(s)}>{s}</button>
                  ))}
                </div>
              </div>
            )}
            {chat.map((m, i) => m.role === 'note' ? (
              <div key={i} className="assistant-note">{m.content}</div>
            ) : m.role === 'user' ? (
              <div key={i} className="bubble user">{m.content}</div>
            ) : (
              <div key={i} className="bubble assistant rich">
                {m.reply.escalate && <div className="escalate">📡 Contact the flight surgeon now.</div>}
                <p>{m.reply.answer}</p>
                {m.reply.steps.length > 0 && (
                  <ol className="assistant-steps">{m.reply.steps.map((s, j) => <li key={j}>{s}</li>)}</ol>
                )}
                {m.reply.actions.length > 0 && (
                  <div className="assistant-actions">
                    {m.reply.actions.map((a, j) => (
                      <button key={j} className="chip action" onClick={() => act(a)}>{a.label} →</button>
                    ))}
                  </div>
                )}
                {m.mode !== 'ai' && <div className="muted tiny">{m.note}</div>}
              </div>
            ))}
            {busy && <div className="bubble assistant typing">…</div>}
            <div ref={end} />
          </div>

          {error && <div className="toast error">{error}</div>}
          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send() }}>
            <input ref={input} value={question} onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask anything…" maxLength={2000} aria-label="Your question" />
            <button className="primary" disabled={busy || !question.trim()}>Send</button>
          </form>
          <div className="muted tiny assistant-foot">Not a substitute for the flight surgeon. Alert levels come from AURA&apos;s rule engine.</div>
        </div>
      )}
    </>
  )
}
