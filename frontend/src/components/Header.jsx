const ENV_LABEL = {
  iss: 'ISS · low Earth orbit',
  lunar_surface: 'Lunar surface base',
  mars_transit: 'Mars transit',
}

export default function Header({ mission, onReset, onRestart, onTour, onHome }) {
  return (
    <header className="header">
      <a className="brand" href="#/home" onClick={(e) => { e.preventDefault(); onHome?.() }} aria-label="AURA home">
        <svg viewBox="0 0 40 40" className="logo" aria-hidden="true">
          <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" />
          <ellipse cx="20" cy="20" rx="19" ry="6" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
          <circle cx="20" cy="20" r="5" fill="currentColor" />
        </svg>
        <div>
          <div className="brand-name">AURA</div>
          <div className="brand-sub">Autonomous Unified Risk Assessment</div>
          <div className="brand-tag">Your crew&apos;s health, even when Earth is 20 minutes away.</div>
        </div>
      </a>
      {mission && (
        <div className="mission-info">
          <span className="pill">{mission.mission_name}</span>
          <label className="pill env-select">
            <span className="sr-only">Mission environment</span>
            <select value={mission.environment} onChange={(e) => onReset(e.target.value)}>
              {Object.entries(ENV_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <span className="pill">Mission day {mission.current_day}</span>
          <button className="pill tour-btn" onClick={onTour}>▶ Demo tour</button>
          <button className="pill" onClick={onRestart} title="Restart the demo: default crew, lunar base, day 60">↺ Reset</button>
          <span className="pill synthetic" title={mission.data_notice}>Synthetic data</span>
        </div>
      )}
    </header>
  )
}
