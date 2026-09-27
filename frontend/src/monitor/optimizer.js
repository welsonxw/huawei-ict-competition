// Pure helpers for the routine optimiser panel (Phase 13).

export function reasonKey(reason) {
  return `opt_${reason.code}`
}

export function reasonVars(reason) {
  const out = {}
  for (const [k, v] of Object.entries(reason)) {
    if (k !== 'code') out[k] = typeof v === 'number' ? String(Math.round(v * 10) / 10) : v
  }
  return out
}

// 'now' when the best slot is the current hour, 'schedule' for a later slot, null when skipping is best.
export function applyMode(best) {
  if (!best || best.kind === 'skip' || !best.litres) return null
  return best.in_hours === 0 ? 'now' : 'schedule'
}

export function scoreDelta(candidate, best) {
  return Math.round((candidate.score - best.score) * 100) / 100
}
