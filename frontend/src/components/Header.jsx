import { useEffect, useState } from 'react'

// Theme: dark (space) by default; a Light choice is remembered per browser.
function initialTheme() {
  try {
    const saved = localStorage.getItem('aura-theme-v2')
    if (saved === 'dark' || saved === 'light') return saved
  } catch { /* storage blocked */ }
  return 'dark'
}

const ENV_LABEL = {
  iss: 'ISS · low Earth orbit',
  lunar_surface: 'Lunar surface base',
  mars_transit: 'Mars transit',
}

export default function Header({ mission, onReset, onRestart, onTour, onHome, children }) {
  const [theme, setTheme] = useState(initialTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('aura-theme-v2', theme) } catch { /* storage blocked */ }
  }, [theme])
  const dark = theme === 'dark'
  return (
    <>
    <header className="site-header">
      <div className="site-bar">
        <a className="brand" href="#/home" onClick={(e) => { e.preventDefault(); onHome?.() }} aria-label="AURA home">
          <span className="logo-box" aria-hidden="true"><svg viewBox="0 0 40 40" className="logo">
            <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" />
            <ellipse cx="20" cy="20" rx="19" ry="6" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
            <circle cx="20" cy="20" r="5" fill="currentColor" />
          </svg></span>
          <span className="brand-text">
            <span className="brand-name">AURA</span>
            <span className="brand-sub">Autonomous Unified Risk Assessment</span>
          </span>
        </a>
        {mission && (
          <div className="mission-info">
            <span className="pill status-pill mission-name"><span className="status-dot" aria-hidden="true" />{mission.mission_name}</span>
            <label className="pill env-select">
              <span className="sr-only">Mission environment</span>
              <select value={mission.environment} onChange={(e) => onReset(e.target.value)}>
                {Object.entries(ENV_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
            <span className="pill">Day {mission.current_day}</span>
            <button className="pill tour-btn" onClick={onTour}>▶ Demo tour</button>
            <button className="pill" onClick={onRestart} title="Restart the demo: default crew, lunar base, day 60">↺ Reset</button>
            <button className="pill theme-btn" onClick={() => setTheme(dark ? 'light' : 'dark')}
              title={dark ? 'Switch to light mode' : 'Switch to dark mode'}>{dark ? '☀ Light' : '☾ Dark'}</button>
            <span className="pill synthetic" title={mission.data_notice}>Synthetic data</span>
          </div>
        )}
      </div>
      <div className="site-nav">{children}</div>
    </header>
    </>
  )
}
