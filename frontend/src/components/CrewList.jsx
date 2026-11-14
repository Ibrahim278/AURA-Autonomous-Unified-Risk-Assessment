import { LEVEL } from '../levels.js'

export default function CrewList({ crew, selectedId, onSelect, onEdit, onImport }) {
  return (
    <div className="crew-list">
      <div className="panel-head crew-head">
        <h2>Crew</h2>
        <span className="crew-actions">
          {onImport && <button className="link" onClick={onImport} title="Import your own data (CSV)">⬆ Import</button>}
          {onEdit && <button className="link" onClick={onEdit}>✎ Edit</button>}
        </span>
      </div>
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
              <span className="crew-role">{c.role}{c.data_source === 'imported' && ' · your data'}</span>
            </span>
            <span className={`badge ${lvl.cls}`}>{lvl.icon} {lvl.label}</span>
          </button>
        )
      })}
    </div>
  )
}
