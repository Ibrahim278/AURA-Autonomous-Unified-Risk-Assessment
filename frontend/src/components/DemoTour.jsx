// Guided walkthrough for judges: each step drives the dashboard to a moment in the mission.
export const TOUR_STEPS = [
  {
    title: 'Meet AURA',
    text: 'Astronauts on long missions have to spot health changes themselves: on Mars, the flight surgeon is minutes away. AURA turns daily measurements into a clear Normal / Warning / Critical status, compared with each astronaut’s own preflight baseline. Every feature is one click away from this home page.',
    crew: 'aura-1', day: null, indicator: null, target: '.hero', page: 'home',
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
    text: 'His heart rate is still “normal”, but the early-warning forecast projects each trend forward and flags it: it reaches the edge of his baseline in about a day. Each row gives a 95% range and the trends moving together (heart rate with mood). Click a row to see the projection and its shaded range on the chart.',
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
    title: 'His day, adjusted',
    text: 'The Daily plan page turns Kenji’s alerts into today’s schedule: 7 changes, each with its reason. Steady cycling instead of intervals for his heart rate, a short ride after lunch for glucose, morning bright light and a longer fixed sleep window, and a private call home for his mood. Tick each block off as he does it.',
    crew: 'aura-2', day: null, indicator: null, target: '#plan',
  },
  {
    title: 'Critical: escalate to ground',
    text: 'Mission Specialist Amara Diallo has a fever of 39.4 °C from viral reactivation. The body figure flags the immune system, and AURA tells her to contact the flight surgeon now.',
    crew: 'aura-3', day: null, indicator: 'body_temp', target: '.banner',
  },
  {
    title: 'Symptoms tell the rest',
    text: 'Numbers miss what she feels. Amara logged chills and growing tiredness in the symptom log. AURA triages it with fixed rules: chills need follow-up, and tiredness on 3 of the last 5 days is persistent. Red flags like chest pain always mean “contact the flight surgeon now”. Each symptom links to the readings worth checking. Readings can be logged by voice too: press 🎙 Speak and say “temperature 38.9, heart rate 80”, and AURA fills the form and checks the values are plausible.',
    crew: 'aura-3', day: null, indicator: null, target: '#symptoms',
  },
  {
    title: 'Message ground, mind the delay',
    text: '“Message ground now” drafts an urgent message with her status attached. On the Moon it reaches Earth in 1.3 s; in Mars transit the delay grows to about 12.5 minutes each way, so AURA’s guidance is the first line of support until the simulated flight surgeon’s reply arrives. Switch to Mars transit in the header to try it.',
    crew: 'aura-3', day: null, indicator: null, target: '#comms',
  },
  {
    title: 'Radiation budget: the long game',
    text: 'Commander Ortiz feels fine and every reading is normal, but she is a veteran with 410 mSv from earlier missions. This mission takes her to 85% of NASA’s 600 mSv career limit, so AURA warns and suggests limiting high-dose tasks. A daily dosimeter alone wouldn’t show that.',
    crew: 'aura-1', day: null, indicator: null, target: '#radiation',
  },
  {
    title: 'The flight surgeon’s view',
    text: 'This is the 🛰 Ground view page (in the menu bar): the whole crew on one screen, sorted by who needs attention first (the worst of telemetry, symptoms and radiation), with messages shown only once their signal has arrived. 🖨 Report opens a printable health report you can save as PDF.',
    crew: 'aura-3', day: null, indicator: null, target: '#ground',
  },
  {
    title: 'Is the team OK?',
    text: 'Team wellbeing scores each person and the crew from mood, sleep, symptoms and exercise, all against their own baselines. The crew is at 54 (“support”): Kenji is lowest because mood and sleep are far below his normal. AURA suggests team actions, and the ground sees the same score.',
    crew: 'aura-2', day: null, indicator: null, target: '#team',
  },
  {
    title: 'Daily routine, gamified',
    text: 'Tasks, streaks, points and badges reward measuring regularly and following up on warnings. Weekly challenges and the 👥 crew board turn it into a team effort. Log a check-in to tick tasks off, and watch the status update live.',
    crew: 'aura-2', day: null, indicator: null, target: '.routine',
  },
  {
    title: 'Real astronaut data from NASA',
    text: 'The Real NASA data page shows real bloodwork from the four Inspiration4 crew (NASA OSDR), from 92 days before launch to 194 days after return. All four had higher glucose the day after landing than just before launch. Out-of-range points are circled, and the lab’s range is shaded.',
    crew: 'aura-2', day: null, indicator: null, target: '#research', research: { dataset: 'cmp', key: 'glucose' },
  },
  {
    title: 'Immune signals from real flight',
    text: 'The immune and cardiac panels add 80 cytokines and proteins from the same crew. Here IL-6, an inflammation signal, was higher the day after landing than 3 days before launch for all four. These research assays have no clinical range, so AURA compares each person with their own preflight values, and its quality check excludes readings stuck at the assay’s limit (here, 4 IFN-α2 values of exactly 120.88).',
    crew: 'aura-2', day: null, indicator: null, target: '#research', research: { dataset: 'immune', key: 'il_6' },
  },
  {
    title: 'AI review of real bloodwork',
    text: 'White cells fell from launch to landing for all four. Pick a crew member and click Review: Claude compares their markers with their own preflight average and the lab ranges, then suggests what to monitor next flight. AURA’s quality check also caught a misaligned row in the published file and left it out.',
    crew: 'aura-2', day: null, indicator: null, target: '#research-review', research: { dataset: 'cbc', key: 'white_blood_cell_count', crew: 'C003' },
  },
  {
    title: 'Ask AURA anything',
    text: 'The ✦ Ask AURA button below is on every screen. Ask about anyone’s health, what to do next, or how to use AURA, and get an answer, numbered steps and one-click buttons that take you there. Say “take me to radiation” or “show me Amara” and it moves you between pages. Opening it pauses this tour; minimise it to come back.',
    crew: 'aura-2', day: null, indicator: null, target: '.banner', highlight: 'assistant',
  },
  {
    title: 'Built on NASA research',
    text: 'Indicators map to NASA’s five hazards of human spaceflight, and every threshold cites its source. Demo telemetry is synthetic and clearly labelled. Switch to ISS or Mars transit in the header, and use ✎ Edit or ⬆ Import on the home page to try your own crew and readings.',
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
