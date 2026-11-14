import { LEVEL, SYSTEM_LABEL } from '../levels.js'

// Simple schematic body. Each region is clickable and coloured by its worst indicator level.
const REGIONS = {
  brain: <circle cx="100" cy="42" r="26" />,
  lungs: (
    <>
      <ellipse cx="83" cy="132" rx="15" ry="27" />
      <ellipse cx="117" cy="132" rx="15" ry="27" />
    </>
  ),
  heart: (
    <path d="M104 132 c-6 -9 -19 -4 -15 6 c3 7 15 15 15 15 s12 -8 15 -15 c4 -10 -9 -15 -15 -6z" />
  ),
  metabolic: <ellipse cx="100" cy="190" rx="27" ry="20" />,
  immune: (
    <>
      <circle cx="88" cy="84" r="5" />
      <circle cx="112" cy="84" r="5" />
      <circle cx="66" cy="120" r="5" />
      <circle cx="134" cy="120" r="5" />
      <circle cx="86" cy="226" r="5" />
      <circle cx="114" cy="226" r="5" />
    </>
  ),
  musculoskeletal: (
    <>
      <rect x="78" y="248" width="9" height="76" rx="4.5" />
      <rect x="113" y="248" width="9" height="76" rx="4.5" />
      <rect x="79" y="336" width="8" height="60" rx="4" />
      <rect x="113" y="336" width="8" height="60" rx="4" />
      <rect x="47" y="110" width="7" height="84" rx="3.5" transform="rotate(4 50 110)" />
      <rect x="146" y="110" width="7" height="84" rx="3.5" transform="rotate(-4 150 110)" />
    </>
  ),
}

// Right half of the outline (x >= 100); the left half is mirrored so the figure is symmetric.
const RIGHT_HALF = [
  [108, 64], [108, 76], [128, 82], [142, 90], [149, 104], [156, 150], [163, 198], [167, 214],
  [159, 220], [150, 202], [142, 152], [137, 122], [134, 170], [131, 208], [135, 232],
  [133, 300], [129, 332], [127, 398], [130, 410], [110, 413], [107, 400], [106, 332],
  [104, 252], [100, 238],
]
const SILHOUETTE = (() => {
  const left = [...RIGHT_HALF].reverse().slice(1).map(([x, y]) => [200 - x, y])
  const pts = [...RIGHT_HALF, ...left]
  return `M${pts.map(([x, y]) => `${x} ${y}`).join(' L')} Z`
})()

export default function BodyFigure({ systems, selected, onSelect }) {
  const cls = (s) => {
    const lvl = systems[s]?.level ?? 'normal'
    const empty = !systems[s]?.indicators?.length
    return `region ${LEVEL[lvl].cls} ${selected === s ? 'selected' : ''} ${empty ? 'empty' : ''}`
  }
  const handlers = (s) => ({
    onClick: () => onSelect(s),
    onKeyDown: (e) => (e.key === 'Enter' || e.key === ' ') && onSelect(s),
    tabIndex: 0,
    role: 'button',
    'aria-label': `${SYSTEM_LABEL[s]}: ${systems[s]?.level}`,
  })

  return (
    <div className="body-figure">
      <svg viewBox="0 0 200 420" className="body-svg">
        <defs>
          <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="5" />
          </filter>
        </defs>
        <g className={cls('whole_body')} {...handlers('whole_body')}>
          <path d={SILHOUETTE} className="aura-glow" filter="url(#glow)" />
          <path d={SILHOUETTE} className="silhouette" />
          <title>{SYSTEM_LABEL.whole_body}</title>
        </g>
        {Object.entries(REGIONS).map(([s, shape]) => (
          <g key={s} className={cls(s)} {...handlers(s)}>
            {shape}
            <title>{SYSTEM_LABEL[s]}</title>
          </g>
        ))}
      </svg>
      <ul className="system-legend">
        {Object.keys(SYSTEM_LABEL).map((s) => {
          const lvl = LEVEL[systems[s]?.level ?? 'normal']
          return (
            <li key={s}>
              <button className={`legend-btn ${selected === s ? 'active' : ''}`} onClick={() => onSelect(s)}>
                <span className={`dot ${lvl.cls}`} aria-hidden="true" />
                {SYSTEM_LABEL[s]}
                <span className={`legend-level ${lvl.cls}`}>{lvl.icon}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
