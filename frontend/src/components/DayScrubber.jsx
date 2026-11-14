export default function DayScrubber({ currentDay, day, live, onChange }) {
  return (
    <div className="scrubber">
      <h2>Mission replay</h2>
      <input
        type="range"
        min={1}
        max={currentDay}
        value={day}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="Mission day"
      />
      <div className="scrubber-row">
        <span>Day {day}</span>
        {live ? (
          <span className="live">● Live</span>
        ) : (
          <button className="link" onClick={() => onChange(currentDay)}>Back to live</button>
        )}
      </div>
      <p className="hint">Drag to see what AURA showed on any day of the mission.</p>
    </div>
  )
}
