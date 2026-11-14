import { LEVEL } from '../levels.js'

export default function CrewList({ crew, selectedId, onSelect }) {
  return (
    <div className="crew-list">
      <h2>Crew</h2>
      {crew.map((c) => {
        const lvl = LEVEL[c.overall]
        return (
          <button
            key={c.id}
            className={`crew-item ${c.id === selectedId ? 'active' : ''}`}
            onClick={() => onSelect(c.id)}
          >
            <span className={`dot ${lvl.cls}`} aria-hidden="true" />
            <span className="crew-text">
              <span className="crew-name">{c.name}</span>
              <span className="crew-role">{c.role}</span>
            </span>
            <span className={`badge ${lvl.cls}`}>{lvl.icon} {lvl.label}</span>
          </button>
        )
      })}
    </div>
  )
}
