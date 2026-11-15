// The app's pages. Each one is a URL hash route (#/plan), a menu entry and a card on Home.
// `related` links pages to each other so every page leads somewhere useful next.
export const PAGES = {
  home: { title: 'Home', icon: '🏠', group: null, crew: false },
  status: {
    title: 'Health status', short: 'Status', icon: '🩺', group: 'Monitor', crew: true,
    desc: 'Overall level, AI briefing, early-warning forecast, body map and every indicator with its chart.',
    related: ['checkin', 'plan', 'timeline'],
  },
  timeline: {
    title: 'Alert history', short: 'Alerts', icon: '📜', group: 'Monitor', crew: true,
    desc: 'Every day an indicator changed level, filtered by level, body system and time.',
    related: ['status', 'plan'],
  },
  checkin: {
    title: 'Check-in & symptoms', short: 'Check-in', icon: '📝', group: 'Act', crew: true,
    desc: 'Log today’s readings by typing or voice, with plausibility checks, and triage how you feel.',
    related: ['status', 'plan', 'comms'],
  },
  plan: {
    title: 'Daily plan', short: 'Plan', icon: '🗓', group: 'Act', crew: true,
    desc: 'Today’s exercise, sleep and care schedule, adjusted to your alerts, with the reason for each change.',
    related: ['status', 'radiation', 'routine'],
  },
  radiation: {
    title: 'Radiation', icon: '☢', group: 'Act', crew: true,
    desc: 'Career and 30-day dose against NASA limits, with a projection to the end of the mission.',
    related: ['plan', 'status'],
  },
  comms: {
    title: 'Message ground', short: 'Ground msg', icon: '📡', group: 'Act', crew: true,
    desc: 'Message the flight surgeon with the real signal delay: 1.3 s from the Moon, minutes from Mars.',
    related: ['ground', 'checkin'],
  },
  routine: {
    title: 'Routine & rewards', short: 'Routine', icon: '🏅', group: 'Crew', crew: true,
    desc: 'Daily tasks, streaks, weekly challenges, the crew board and badges.',
    related: ['checkin', 'plan', 'team'],
  },
  team: {
    title: 'Team wellbeing', short: 'Team', icon: '👥', group: 'Crew', crew: false,
    desc: 'A wellbeing score for each person and the crew, with mood and sleep trends and team suggestions.',
    related: ['ground', 'routine'],
  },
  ground: {
    title: 'Ground view', short: 'Ground view', icon: '🛰', group: 'Crew', crew: false,
    desc: 'The flight surgeon’s console: the whole crew sorted by priority, messages and printable reports.',
    related: ['team', 'comms'],
  },
  console: {
    title: 'Flight surgeon console', short: 'Console', icon: '⌨', group: 'Crew', crew: false,
    desc: 'Play the ground side live: read crew messages as their signal reaches Earth and type a real reply. It reaches the crew after the same delay.',
    related: ['ground', 'comms'],
  },
  research: {
    title: 'Real NASA data', short: 'NASA data', icon: '🧪', group: 'Research', crew: false,
    desc: 'Real Inspiration4 bloodwork, cytokines and proteins from NASA OSDR, with an AI review per astronaut.',
    related: ['status'],
  },
}

export const GROUPS = [
  { id: 'Monitor', blurb: 'See how each astronaut is doing and where it’s heading.' },
  { id: 'Act', blurb: 'Log, plan and get help.' },
  { id: 'Crew', blurb: 'The team, the rewards and the view from Earth.' },
  { id: 'Research', blurb: 'Real astronaut data behind AURA.' },
]

// Which page holds each element the demo tour or Ask AURA points to.
export const PAGE_OF_TARGET = {
  '.banner': 'status', '.detail': 'status', '.forecast': 'status', '.ai-panel': 'status', '.overview': 'status',
  '#symptoms': 'checkin', '#checkin': 'checkin', '#plan': 'plan', '#radiation': 'radiation', '#comms': 'comms',
  '.timeline': 'timeline', '.routine': 'routine', '#team': 'team', '#ground': 'ground', '#console': 'console', '#research': 'research',
  '#research-review': 'research', '.crew-list': 'status', '.landing': 'home', '.hero': 'home',
}

export function pageFromHash() {
  const id = (window.location.hash || '').replace(/^#\/?/, '').split(/[?/]/)[0]
  return PAGES[id] ? id : 'home'
}
