import assert from 'node:assert/strict'
import { test } from 'node:test'
import { checkKey, checkVars, daysLabel, isBlocked, sortChecks, toggleDay } from './control.js'

test('blocking checks sort first and mark the command blocked', () => {
  const checks = [
    { level: 'ok', code: 'rain_ok' },
    { level: 'warn', code: 'evening_watering' },
    { level: 'block', code: 'moisture_high' },
  ]
  assert.deepEqual(
    sortChecks(checks).map((c) => c.level),
    ['block', 'warn', 'ok'],
  )
  assert.equal(isBlocked(checks), true)
  assert.equal(isBlocked(checks.slice(0, 2)), false)
})

test('check vars are rounded for display', () => {
  assert.equal(checkKey({ code: 'water_daily_limit' }), 'ctl_water_daily_limit')
  assert.deepEqual(checkVars({ vars: { used: 12.345, unit: 'L', limit: null } }), { used: '12.3', unit: 'L', limit: '–' })
})

test('weekday selection', () => {
  const t = (k) => ({ ctlEveryDay: 'Every day', ctlDay0: 'Mon', ctlDay2: 'Wed' })[k] ?? k
  assert.equal(daysLabel('0123456', t), 'Every day')
  assert.equal(daysLabel('02', t), 'Mon, Wed')
  assert.equal(toggleDay('012', '1'), '02')
  assert.equal(toggleDay('02', '1'), '012')
})
