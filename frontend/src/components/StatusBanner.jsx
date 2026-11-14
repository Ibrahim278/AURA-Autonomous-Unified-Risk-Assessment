import { LEVEL } from '../levels.js'

const MESSAGE = {
  normal: 'All indicators are within your personal baseline. Keep up your routine.',
  warning: 'Some indicators need your attention. Review the guidance below.',
  critical: 'A critical condition has been detected. Follow the actions and contact the flight surgeon now.',
}

export default function StatusBanner({ member, status, live }) {
  const lvl = LEVEL[status.overall]
  return (
    <section className={`banner ${lvl.cls}`} role={status.escalate ? 'alert' : 'status'}>
      <div className="banner-main">
        <div className="banner-level">{lvl.icon} {lvl.label}</div>
        <div>
          <div className="banner-name">
            {member.name} <span className="muted">· {member.role} · Day {status.day}{!live && ' (replay)'}</span>
          </div>
          <div>{MESSAGE[status.overall]}</div>
        </div>
      </div>
      <div className="banner-counts">
        <span className="count lvl-normal">{status.counts.normal} normal</span>
        <span className="count lvl-warning">{status.counts.warning} warning</span>
        <span className="count lvl-critical">{status.counts.critical} critical</span>
      </div>
      {status.escalate && (
        <div className="escalate">📡 Escalate to flight surgeon: critical readings need ground review.</div>
      )}
    </section>
  )
}
