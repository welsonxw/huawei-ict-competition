import assert from 'node:assert/strict'
import { test } from 'node:test'
import { clockMinutes, isRaining, openCommand, sceneFromFarm, slotAt, slotXY, tileInfo } from './myfarm.js'

const farm = (over = {}) => ({
  plot: { crop: 'tomato' },
  plants: 12,
  soil: 'dry',
  local_time: '07:30',
  rain_mm_next: 0,
  sick: [{ disease: 'early_blight' }, { disease: 'late_blight' }],
  control: { actuators: [], commands: [] },
  ...over,
})

test('slots map to field tiles and back', () => {
  for (const i of [0, 9, 10, 49]) {
    const { x, y } = slotXY(i)
    assert.equal(slotAt(x, y), i)
  }
  assert.equal(slotAt(0, 0), null)
})

test('scene mirrors the real plot', () => {
  const s = sceneFromFarm(farm(), { x: 1, y: 3, dir: 'down' })
  assert.equal(Object.keys(s.tiles).length, 12)
  const first = s.tiles[`${slotXY(0).x},${slotXY(0).y}`]
  assert.equal(first.crop.kind, 'tomato')
  assert.equal(first.crop.disease, 'early_blight')
  assert.equal(first.watered, false)
  assert.equal(s.tiles[`${slotXY(2).x},${slotXY(2).y}`].crop.disease, null)
  assert.equal(s.minutes, 7 * 60 + 30)
  assert.equal(sceneFromFarm(farm({ soil: 'wet' }), {}).tiles[`${slotXY(0).x},${slotXY(0).y}`].watered, true)
})

test('tile info, rain and open commands', () => {
  const { x, y } = slotXY(1)
  assert.deepEqual(tileInfo(farm(), x, y), { index: 1, sick: { disease: 'late_blight' } })
  assert.equal(tileInfo(farm(), slotXY(20).x, slotXY(20).y), null)
  assert.equal(isRaining(farm({ rain_mm_next: 1.2 })), true)
  assert.equal(isRaining(farm({ rain_mm_next: null })), false)
  assert.equal(clockMinutes('23:05'), 23 * 60 + 5)
  const cmds = [{ status: 'done' }, { status: 'sent', id: 2 }]
  assert.equal(openCommand(farm({ control: { actuators: [], commands: cmds } })).id, 2)
})
