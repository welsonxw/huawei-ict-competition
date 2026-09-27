export const METRICS = [
  { key: 'soil_moisture_pct', label: 'mSoilMoisture', digits: 1 },
  { key: 'soil_temp_c', label: 'mSoilTemp', digits: 1 },
  { key: 'air_temp_c', label: 'mAirTemp', digits: 1 },
  { key: 'air_rh_pct', label: 'mAirRh', digits: 0 },
  { key: 'leaf_wet', label: 'mLeafWet', bool: true },
  { key: 'soil_ec_ds_m', label: 'mSoilEc', digits: 2 },
  { key: 'light_lux', label: 'mLight', digits: 0 },
  { key: 'battery_pct', label: 'mBattery', digits: 0 },
]

export function formatValue(metric, value, unit = '') {
  if (value === null || value === undefined) return '–'
  if (metric.bool) return value
  const n = Number(value).toFixed(metric.digits ?? 1)
  return unit ? `${n} ${unit}`.replace(' %', '%') : n
}

export function formatBand(band, unit = '') {
  if (!band) return ''
  const [lo, hi] = band
  if (lo === null || lo === undefined) return `≤ ${hi}${unit === '%' ? '%' : ` ${unit}`}`
  if (hi === null || hi === undefined) return `≥ ${lo}${unit === '%' ? '%' : ` ${unit}`}`
  return `${lo}–${hi}${unit === '%' ? '%' : ` ${unit}`}`
}

export function minutesAgo(iso, now = Date.now()) {
  if (!iso) return null
  return Math.max(0, Math.round((now - Date.parse(iso)) / 60000))
}

export function alertKey(alert) {
  return `alert_${alert.code}`
}

export function alertVars(alert, units = {}) {
  return {
    value: alert.value ?? '',
    unit: units[alert.metric] ?? '',
    band: alert.band ? formatBand(alert.band, units[alert.metric] ?? '') : '',
    hours: alert.hours ?? '',
    device: alert.device ?? '',
  }
}

export function chartRows(history, lang = 'en') {
  const locale = lang === 'ms' ? 'ms-MY' : 'en-MY'
  return history.map((r) => ({
    t: new Date(r.ts).toLocaleString(locale, { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' }),
    soil: r.soil_moisture_pct,
    air: r.air_temp_c,
    rh: r.air_rh_pct,
    wet: r.leaf_wet ? 100 : 0,
  }))
}
