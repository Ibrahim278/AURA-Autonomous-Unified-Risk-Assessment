import { PAGES } from '../pages.js'

// Monochrome glyphs for the sidebar (U+FE0E keeps them as text, not colour emoji).
const GLYPH = { home: '⌂', status: '♡', checkin: '✎', plan: '☷', radiation: '☢', comms: '⇄', timeline: '≡', routine: '★', team: '⚇', ground: '◎', console: '⌨', research: '⚗' }

const MENU = ['home', 'status', 'checkin', 'plan', 'radiation', 'comms', 'timeline', 'routine', 'team', 'ground', 'console', 'research']

export default function NavBar({ page, onNavigate }) {
  return (
    <nav className="navbar" aria-label="Pages">
      {MENU.map((id) => (
        <a key={id} href={`#/${id}`} title={PAGES[id].title} className={page === id ? 'active' : ''} aria-current={page === id ? 'page' : undefined}
          onClick={(e) => { e.preventDefault(); onNavigate(id) }}>
          <span className="nav-glyph" aria-hidden="true">{GLYPH[id] + '\uFE0E'}</span><span className="nav-label">{PAGES[id].short ?? PAGES[id].title}</span>
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
