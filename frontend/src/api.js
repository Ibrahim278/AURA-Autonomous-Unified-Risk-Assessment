// Thin wrapper around the AURA FastAPI back end.
const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json()
}

export const api = {
  mission: () => request('/api/mission'),
  indicators: () => request('/api/indicators'),
  crew: () => request('/api/crew'),
  status: (id, day) => request(`/api/crew/${id}/status${day ? `?day=${day}` : ''}`),
  telemetry: (id) => request(`/api/crew/${id}/telemetry`),
  alerts: (id) => request(`/api/crew/${id}/alerts`),
  checkin: (id, body) =>
    request(`/api/crew/${id}/checkins`, { method: 'POST', body: JSON.stringify(body) }),
  tasks: (id) => request(`/api/crew/${id}/tasks`),
  completeTask: (id, taskId) =>
    request(`/api/crew/${id}/tasks/${taskId}/complete`, { method: 'POST' }),
  aiStatus: () => request('/api/ai/status'),
  briefing: (id, day) =>
    request(`/api/crew/${id}/briefing`, { method: 'POST', body: JSON.stringify({ day: day ?? null }) }),
  ask: (id, body) =>
    request(`/api/crew/${id}/ask`, { method: 'POST', body: JSON.stringify(body) }),
  reset: (body) => request('/api/mission/reset', { method: 'POST', body: JSON.stringify(body) }),
}
