const ENV_LABEL = {
  iss: 'ISS · low Earth orbit',
  lunar_surface: 'Lunar surface base',
  mars_transit: 'Mars transit',
}

export default function Header({ mission, onReset, onRestart, onTour, onHome, children }) {
  return (
    <>
    <aside className="side-nav">
      <a className="brand" href="#/home" onClick={(e) => { e.preventDefault(); onHome?.() }} aria-label="AURA home">
        <span className="logo-box" aria-hidden="true"><svg viewBox="0 0 40 40" className="logo">
          <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" />
          <ellipse cx="20" cy="20" rx="19" ry="6" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
          <circle cx="20" cy="20" r="5" fill="currentColor" />
        </svg></span>
        <div>
          <div className="brand-name">AURA</div>
          <div className="brand-sub">Autonomous Unified Risk Assessment</div>
          <div className="brand-tag">Your crew&apos;s health, even when Earth is 20 minutes away.</div>
        </div>
      </a>
      {children}
      <div className="side-note">
        <span className="side-note-title">Research prototype</span>
        <span>Not a certified medical device</span>
      </div>
    </aside>
    <header className="header topbar">
      <div className="topbar-text">
        <p className="eyebrow">Astronaut health · Autonomous risk assessment</p>
        <div className="topbar-mission"><span className="status-dot" aria-hidden="true" />{mission?.mission_name ?? 'AURA'}</div>
      </div>
      {mission && (
        <div className="mission-info">
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
    </>
  )
}
