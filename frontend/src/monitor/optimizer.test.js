import assert from 'node:assert/strict'
import { test } from 'node:test'
import { applyMode, reasonKey, reasonVars, scoreDelta } from './optimizer.js'

test('reason keys and vars', () => {
  assert.equal(reasonKey({ code: 'vs_time' }), 'opt_vs_time')
  assert.deepEqual(reasonVars({ code: 'vs_time', time: '19:00', hours: 11.96 }), { time: '19:00', hours: '12' })
  const t = (k) => (k === 'lrnTiming_morning' ? 'Pagi (05–10)' : k)
  assert.deepEqual(reasonVars({ code: 'learned', timing: 'morning', rate: 10 }, t), { timing: 'Pagi (05–10)', rate: '10' })
})

test('apply mode', () => {
  assert.equal(applyMode(null), null)
  assert.equal(applyMode({ kind: 'skip', litres: 0 }), null)
  assert.equal(applyMode({ kind: 'option', litres: 200, in_hours: 0 }), 'now')
  assert.equal(applyMode({ kind: 'option', litres: 200, in_hours: 5 }), 'schedule')
})

test('score delta', () => {
  assert.equal(scoreDelta({ score: 7.456 }, { score: 6.1 }), 1.36)
})
