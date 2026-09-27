// Pure helpers for the watering / fertiliser control panel (Phase 11).

export const STATUS_STYLE = {
  awaiting_confirmation: 'bg-sky-100 text-sky-900',
  sent: 'bg-sky-100 text-sky-900',
  done: 'bg-emerald-100 text-emerald-900',
  blocked: 'bg-red-100 text-red-900',
  failed: 'bg-red-100 text-red-900',
  expired: 'bg-stone-200 text-stone-700',
  cancelled: 'bg-stone-200 text-stone-700',
}

export const LEVEL_STYLE = {
  block: 'bg-red-100 text-red-900',
  warn: 'bg-amber-50 text-amber-900',
  ok: 'bg-emerald-50 text-emerald-900',
}

const LEVEL_ORDER = { block: 0, warn: 1, ok: 2 }

export function sortChecks(checks = []) {
  return [...checks].sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level])
}

export function checkKey(check) {
  return `ctl_${check.code}`
}

export function checkVars(check) {
  const out = {}
  for (const [k, v] of Object.entries(check.vars ?? {})) {
    out[k] = typeof v === 'number' ? String(Math.round(v * 10) / 10) : (v ?? '–')
  }
  return out
}

export function isBlocked(checks = []) {
  return checks.some((c) => c.level === 'block')
}

export function daysLabel(days, t) {
  if (days === '0123456') return t('ctlEveryDay')
  return days
    .split('')
    .map((d) => t(`ctlDay${d}`))
    .join(', ')
}

export function toggleDay(days, d) {
  const set = new Set(days.split(''))
  if (set.has(d)) set.delete(d)
  else set.add(d)
  return [...set].sort().join('')
}

export function formatTime(iso, lang) {
  if (!iso) return '–'
  return new Date(iso).toLocaleString(lang === 'ms' ? 'ms-MY' : 'en-MY', {
    timeZone: 'Asia/Kuala_Lumpur',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
