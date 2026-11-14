import { useState } from 'react'
import { api } from '../api.js'

const KIND_LABEL = { routine: 'Routine', follow_up: 'Follow-up', wellness: 'Wellness' }

export default function MissionRoutine({ crewId, data, onChange, onGoToCheckin }) {
  const [busy, setBusy] = useState(null)
  const [showBadges, setShowBadges] = useState(false)
  if (!data) return null

  const { level, streaks, progress, tasks, badges } = data
  const span = level.next_at ? level.next_at - level.floor : 1
  const pct = level.next_at ? Math.min(100, ((level.points - level.floor) / span) * 100) : 100
  const earned = badges.filter((b) => b.earned)

  const act = async (t) => {
    if (t.done) return
    if (t.kind === 'wellness') {
      setBusy(t.id)
      try {
        onChange(await api.completeTask(crewId, t.id))
      } finally {
        setBusy(null)
      }
    } else if (!t.auto) {
      onGoToCheckin()
    }
  }

  return (
    <div className="routine">
      <h2>Mission routine · Day {data.day}</h2>

      <div className="level">
        <div className="level-row">
          <span className="level-title">🚀 {level.title}</span>
          <span className="muted">{level.points.toLocaleString()} pts</span>
        </div>
        <div className="bar"><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
        {level.next_title && (
          <div className="hint">{(level.next_at - level.points).toLocaleString()} pts to {level.next_title}</div>
        )}
      </div>

      <div className="streaks">
        <span className="streak" title="Days in a row with the full routine logged">🔥 {streaks.checkin}<small>check-in</small></span>
        <span className="streak" title="Days in a row at 90+ min of exercise">🏋️ {streaks.exercise}<small>exercise</small></span>
        <span className="streak" title="Nights in a row with 6.5+ h of sleep">🌙 {streaks.sleep}<small>sleep</small></span>
      </div>

      <div className="task-head">
        <span>Today&apos;s tasks</span>
        <span className="muted">{progress.done}/{progress.total} · +{progress.points_today} pts</span>
      </div>
      <div className="bar thin"><div className="bar-fill" style={{ width: `${(progress.done / progress.total) * 100}%` }} /></div>

      <ul className="tasks">
        {tasks.map((t) => (
          <li key={t.id}>
            <button
              className={`task ${t.done ? 'done' : ''} kind-${t.kind} ${t.level ? `lvl-${t.level}` : ''}`}
              onClick={() => act(t)}
              disabled={busy === t.id}
              title={t.description}
            >
              <span className="check" aria-hidden="true">{t.done ? '✓' : ''}</span>
              <span className="task-text">
                <span className="task-title">{t.title}</span>
                <span className="task-meta">
                  {KIND_LABEL[t.kind]}
                  {t.auto && ' · auto-synced'}
                  {!t.done && t.kind !== 'wellness' && !t.auto && ' · log in check-in'}
                  {!t.done && t.kind === 'wellness' && ' · tap when done'}
                </span>
              </span>
              <span className="task-pts">+{t.points}</span>
            </button>
          </li>
        ))}
      </ul>

      <button className="link" onClick={() => setShowBadges(!showBadges)}>
        🏅 Badges {earned.length}/{badges.length} {showBadges ? '▴' : '▾'}
      </button>
      {showBadges && (
        <ul className="badges">
          {badges.map((b) => (
            <li key={b.id} className={b.earned ? 'earned' : 'locked'} title={b.description}>
              <span className="badge-icon">{b.earned ? b.icon : '🔒'}</span>
              <span>
                <strong>{b.name}</strong>
                <small>{b.description}</small>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
