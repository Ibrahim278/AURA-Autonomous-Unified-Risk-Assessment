import { PAGES } from '../pages.js'

const MENU = ['home', 'status', 'checkin', 'plan', 'radiation', 'comms', 'timeline', 'routine', 'team', 'ground', 'research']

export default function NavBar({ page, onNavigate }) {
  return (
    <nav className="navbar" aria-label="Pages">
      {MENU.map((id) => (
        <a key={id} href={`#/${id}`} title={PAGES[id].title} className={page === id ? 'active' : ''} aria-current={page === id ? 'page' : undefined}
          onClick={(e) => { e.preventDefault(); onNavigate(id) }}>
          <span aria-hidden="true">{PAGES[id].icon}</span> {PAGES[id].short ?? PAGES[id].title}
        </a>
      ))}
    </nav>
  )
}

export function RelatedLinks({ page, onNavigate }) {
  const rel = PAGES[page]?.related ?? []
  if (!rel.length) return null
  return (
    <nav className="related" aria-label="Related pages">
      <span className="muted small">Related:</span>
      {rel.map((id) => (
        <button key={id} className="chip" onClick={() => onNavigate(id)}>
          {PAGES[id].icon} {PAGES[id].title} →
        </button>
      ))}
      <button className="chip ghost" onClick={() => onNavigate('home')}>🏠 All features</button>
    </nav>
  )
}
