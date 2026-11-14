export const LEVEL = {
  normal: { label: 'Normal', icon: '●', cls: 'lvl-normal' },
  warning: { label: 'Warning', icon: '▲', cls: 'lvl-warning' },
  critical: { label: 'Critical', icon: '■', cls: 'lvl-critical' },
}

export const SYSTEM_LABEL = {
  brain: 'Brain and behaviour',
  heart: 'Heart and circulation',
  lungs: 'Lungs and oxygen',
  metabolic: 'Metabolism and nutrition',
  immune: 'Immune system',
  musculoskeletal: 'Bones and muscles',
  whole_body: 'Radiation exposure',
}

export const HAZARD_LABEL = {
  space_radiation: 'Space radiation',
  isolation_confinement: 'Isolation and confinement',
  distance_from_earth: 'Distance from Earth',
  gravity_fields: 'Altered gravity',
  hostile_closed_environment: 'Hostile closed environment',
}

export const TREND_LABEL = {
  rising: '↗ rising',
  falling: '↘ falling',
  stable: '→ stable',
  insufficient_data: '· not enough data',
}

export function fmt(value, unit) {
  if (value === null || value === undefined) return '—'
  if (unit === '%' || unit === '/10') return `${value}${unit}`
  return `${value} ${unit}`
}
