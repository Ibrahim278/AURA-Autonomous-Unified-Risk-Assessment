import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { LEVEL } from '../levels.js'
import { GROUPS, PAGES } from '../pages.js'

const ORDER = { critical: 0, warning: 1, normal: 2 }

export default function Landing({ mission, crew, onNavigate, onOpenCrew, onTour, onAsk, onEditCrew, onImport, onAddIndicator }) {
  const [link, setLink] = useState(null)
  useEffect(() => {
    let alive = true
    api.comms().then((c) => alive && setLink(c)).catch(() => {})
    return () => { alive = false }
  }, [mission?.environment, mission?.current_day])

  const sorted = [...crew].sort((a, b) => ORDER[a.overall] - ORDER[b.overall])
  const counts = crew.reduce((acc, c) => ({ ...acc, [c.overall]: (acc[c.overall] ?? 0) + 1 }), {})

  return (
    <div className="landing">
      <section className="hero panel">
        <div className="hero-text">
          <p className="eyebrow">NASA Space Apps 2026 · Astronaut health monitoring</p>
          <h1>AURA</h1>
          <p className="hero-tag">Your crew’s health, even when Earth is 20 minutes away.</p>
          <p className="hero-lede">
            On a Mars mission, a message to the flight surgeon takes minutes to arrive. AURA lets astronauts
            assess their own health: it compares every reading with <strong>their own</strong> preflight baseline,
            gives a clear <span className="lvl-text normal">Normal</span>, <span className="lvl-text warning">Warning</span> or{' '}
            <span className="lvl-text critical">Critical</span> status with the reason, warns days ahead, and says exactly what to do next.
          </p>
          <div className="hero-cta">
            <button className="primary big" onClick={onTour}>▶ Start the demo tour</button>
            <button className="chip big" onClick={() => onNavigate('status')}>Open the dashboard →</button>
            <button className="chip big" onClick={onAsk}>✦ Ask AURA</button>
          </div>
        </div>
        <div className="hero-status">
          <h2>Mission at a glance</h2>
          {mission && (
            <ul className="glance">
              <li><span>Mission</span><strong>{mission.mission_name}</strong></li>
              <li><span>Where</span><strong>{mission.environment_info?.name ?? mission.environment}</strong></li>
              <li><span>Day</span><strong>{mission.current_day} of {mission.days}</strong></li>
              {link && <li><span>Signal to Earth</span><strong>{link.one_way} each way</strong></li>}
              <li><span>Crew</span><strong>
                {['critical', 'warning', 'normal'].filter((l) => counts[l]).map((l) => `${counts[l]} ${LEVEL[l].label.toLowerCase()}`).join(' · ')}
              </strong></li>
            </ul>
          )}
          <div className="glance-crew">
            {sorted.map((c) => {
              const lvl = LEVEL[c.overall]
              return (
                <button key={c.id} className={`glance-member ${lvl.cls}`} onClick={() => onOpenCrew(c.id)}>
                  <span className="crew-text">
                    <span className="crew-name">{c.name}</span>
                    <span className="crew-role">{c.role}</span>
                  </span>
                  <span className={`badge ${lvl.cls}`}>{lvl.icon} {lvl.label}</span>
                </button>
              )
            })}
          </div>
          <p className="hint">Click a crew member to open their health status.</p>
        </div>
      </section>

      {GROUPS.map((g) => (
        <section key={g.id} className="feature-group">
          <div className="group-head">
            <h2>{g.id}</h2>
            <span className="muted">{g.blurb}</span>
          </div>
          <div className="feature-grid">
            {Object.entries(PAGES).filter(([, p]) => p.group === g.id).map(([id, p]) => (
              <a key={id} href={`#/${id}`} className="feature-card" onClick={(e) => { e.preventDefault(); onNavigate(id) }}>
                <span className="feature-icon" aria-hidden="true">{p.icon}</span>
                <span className="feature-title">{p.title}</span>
                <span className="feature-desc">{p.desc}</span>
                <span className="feature-go">Open →</span>
              </a>
            ))}
          </div>
        </section>
      ))}

      <section className="feature-group">
        <div className="group-head">
          <h2>Your data</h2>
          <span className="muted">Make the mission your own.</span>
        </div>
        <div className="feature-grid">
          <button className="feature-card" onClick={onEditCrew}>
            <span className="feature-icon" aria-hidden="true">✎</span>
            <span className="feature-title">Edit the crew</span>
            <span className="feature-desc">Names, baselines, earlier radiation dose and a health scenario for up to 6 people.</span>
            <span className="feature-go">Open →</span>
          </button>
          <button className="feature-card" onClick={onImport}>
            <span className="feature-icon" aria-hidden="true">⬆</span>
            <span className="feature-title">Import your readings</span>
            <span className="feature-desc">Upload a CSV from a wearable, a clinic or a lab and see AURA assess you.</span>
            <span className="feature-go">Open →</span>
          </button>
          <button className="feature-card" onClick={onAddIndicator}>
            <span className="feature-icon" aria-hidden="true">➕</span>
            <span className="feature-title">Add an indicator</span>
            <span className="feature-desc">Track body weight, HRV, water or anything else, with its own limits and alerts.</span>
            <span className="feature-go">Open →</span>
          </button>
        </div>
      </section>

      <section className="panel how">
        <h2>How AURA decides</h2>
        <div className="how-grid">
          <div><strong>1. Personal baseline</strong><p>7 days before launch set each astronaut’s own normal for every indicator.</p></div>
          <div><strong>2. Transparent rules</strong><p>Fixed, cited rules set every level: limits, sustained shifts, unusual readings.</p></div>
          <div><strong>3. Early warning</strong><p>Trends are projected 14 days ahead with a 95% range, before an alert fires.</p></div>
          <div><strong>4. AI explains, never decides</strong><p>Claude writes briefings and answers questions; it never sets a level and always escalates a critical.</p></div>
        </div>
      </section>
    </div>
  )
}
