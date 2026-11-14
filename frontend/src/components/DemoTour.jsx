// Guided walkthrough for judges: each step drives the dashboard to a moment in the mission.
export const TOUR_STEPS = [
  {
    title: 'Meet AURA',
    text: 'Astronauts on long missions have to spot health changes themselves. AURA turns daily measurements into a clear Normal / Warning / Critical status, compared with each astronaut’s own preflight baseline.',
    crew: 'aura-1', day: null, indicator: null, target: '.banner',
  },
  {
    title: 'Day 30: all clear',
    text: 'Dr. Kenji Sato, flight engineer on a lunar base. A month in, every indicator sits within his personal baseline band.',
    crew: 'aura-2', day: 30, indicator: null, target: '.banner',
  },
  {
    title: 'Day 42: sleep slips first',
    text: 'Sleep drops to 5.7 h, down from his 7.2 h baseline. AURA raises a warning for the sustained drop and suggests sleep-hygiene actions.',
    crew: 'aura-2', day: 42, indicator: 'sleep_hours', target: '.detail',
  },
  {
    title: 'Day 48: AURA sees it coming',
    text: 'His heart rate is still “normal”, but the early-warning forecast projects each trend forward and flags it: it reaches the edge of his baseline in about a day. Click a forecast row to see the dashed projection on the chart.',
    crew: 'aura-2', day: 48, indicator: 'heart_rate', target: '.forecast',
  },
  {
    title: 'Day 50: the heart follows',
    text: 'Resting heart rate is 71 bpm. That is normal on Earth, but it has sat well above his 64 bpm baseline for 3 days running. A one-size-fits-all threshold would miss this.',
    crew: 'aura-2', day: 50, indicator: 'heart_rate', target: '.detail',
  },
  {
    title: 'Day 60: connecting the dots',
    text: 'Blood pressure and glucose now warn too. The AI flight surgeon links the chain (sleep → mood → heart → blood pressure) and gives one action per priority. Try “Generate daily briefing”.',
    crew: 'aura-2', day: null, indicator: null, target: '.ai-panel',
  },
  {
    title: 'Critical: escalate to ground',
    text: 'Mission Specialist Amara Diallo has a fever of 39.4 °C from viral reactivation. The body figure flags the immune system, and AURA tells her to contact the flight surgeon now.',
    crew: 'aura-3', day: null, indicator: 'body_temp', target: '.banner',
  },
  {
    title: 'Daily routine, gamified',
    text: 'Tasks, streaks, points and badges reward measuring regularly and following up on warnings. Log a check-in to tick tasks off, and watch the status update live.',
    crew: 'aura-2', day: null, indicator: null, target: '.routine',
  },
  {
    title: 'Real astronaut data from NASA',
    text: 'Below the synthetic mission is real bloodwork from the four Inspiration4 crew (NASA OSDR), from 92 days before launch to 194 days after return. All four had higher glucose the day after landing than just before launch. Out-of-range points are circled, and the lab’s range is shaded.',
    crew: 'aura-2', day: null, indicator: null, target: '#research', research: { dataset: 'cmp', key: 'glucose' },
  },
  {
    title: 'AI review of real bloodwork',
    text: 'White cells fell from launch to landing for all four. Pick a crew member and click Review: Claude compares their markers with their own preflight average and the lab ranges, then suggests what to monitor next flight. AURA’s quality check also caught a misaligned row in the published file and left it out.',
    crew: 'aura-2', day: null, indicator: null, target: '#research-review', research: { dataset: 'cbc', key: 'white_blood_cell_count', crew: 'C003' },
  },
  {
    title: 'Your crew, your data',
    text: 'Use ✎ Edit to add or change crew members, their baselines and a health scenario; the AI isn’t told the scenario, so it has to find the pattern. Use ⬆ Import to upload your own CSV and see AURA assess you.',
    crew: 'aura-2', day: null, indicator: null, target: '.crew-list',
  },
  {
    title: 'Built on NASA research',
    text: 'Indicators map to NASA’s five hazards of human spaceflight, and every threshold cites its source. Demo telemetry is synthetic and clearly labelled. Switch to ISS or Mars transit in the header.',
    crew: 'aura-2', day: null, indicator: 'radiation_dose', target: '.detail',
  },
]

export default function DemoTour({ step, onStep, onClose }) {
  const s = TOUR_STEPS[step]
  const last = step === TOUR_STEPS.length - 1
  return (
    <div className="tour" role="dialog" aria-label="Demo tour">
      <div className="tour-head">
        <span className="tour-count">Demo tour · {step + 1}/{TOUR_STEPS.length}</span>
        <button className="link" onClick={onClose} aria-label="End tour">✕</button>
      </div>
      <h3>{s.title}</h3>
      <p>{s.text}</p>
      <div className="tour-dots">
        {TOUR_STEPS.map((_, i) => (
          <button key={i} className={`tour-dot ${i === step ? 'on' : ''}`} onClick={() => onStep(i)} aria-label={`Step ${i + 1}`} />
        ))}
      </div>
      <div className="tour-actions">
        <button className="chip" onClick={() => onStep(step - 1)} disabled={step === 0}>← Back</button>
        {last
          ? <button className="primary" onClick={onClose}>Explore AURA</button>
          : <button className="primary" onClick={() => onStep(step + 1)}>Next →</button>}
      </div>
    </div>
  )
}
