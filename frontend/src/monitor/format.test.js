import { test } from 'node:test'
import assert from 'node:assert/strict'
import { strings } from '../i18n/strings.js'
import { METRICS, alertKey, alertVars, chartRows, formatBand, formatValue, minutesAgo } from './format.js'

const soil = METRICS.find((m) => m.key === 'soil_moisture_pct')
const ec = METRICS.find((m) => m.key === 'soil_ec_ds_m')

test('formatValue uses units and digits', () => {
  assert.equal(formatValue(soil, 31.26, '%'), '31.3%')
  assert.equal(formatValue(ec, 1.2, 'dS/m'), '1.20 dS/m')
  assert.equal(formatValue(soil, null, '%'), '–')
})

test('formatBand handles open bounds', () => {
  assert.equal(formatBand([25, 40], '%'), '25–40%')
  assert.equal(formatBand([null, 90], '%'), '≤ 90%')
  assert.equal(formatBand([18, 33], '°C'), '18–33 °C')
})

test('minutesAgo', () => {
  const now = Date.parse('2026-01-01T08:30:00Z')
  assert.equal(minutesAgo('2026-01-01T08:00:00Z', now), 30)
  assert.equal(minutesAgo(null, now), null)
})

test('alert text is filled from backend alert fields', () => {
  const alert = { code: 'soil_moisture_pct_low', metric: 'soil_moisture_pct', value: 15, band: [25, 40] }
  assert.equal(alertKey(alert), 'alert_soil_moisture_pct_low')
  const vars = alertVars(alert, { soil_moisture_pct: '%' })
  const msg = strings.en[alertKey(alert)].replace(/\{(\w+)\}/g, (_, k) => vars[k])
  assert.equal(msg, 'Soil is dry: 15% (target 25–40%). Consider watering.')
  for (const lang of ['en', 'ms']) {
    for (const code of ['offline', 'soil_moisture_pct_low', 'soil_moisture_pct_high', 'soil_ec_ds_m_low', 'soil_ec_ds_m_high',
      'air_temp_c_low', 'air_temp_c_high', 'air_rh_pct_high', 'leaf_wet_long', 'battery_low']) {
      assert.ok(strings[lang][`alert_${code}`], `${lang} alert_${code}`)
    }
  }
})

test('chartRows maps history to chart series', () => {
  const rows = chartRows([{ ts: '2026-01-01T00:00:00Z', soil_moisture_pct: 30, air_temp_c: 26, air_rh_pct: 91, leaf_wet: true }])
  assert.equal(rows[0].soil, 30)
  assert.equal(rows[0].wet, 100)
})
