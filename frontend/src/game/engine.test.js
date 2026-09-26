import { test } from 'node:test'
import assert from 'node:assert/strict'
import { act, buySeed, CROPS, DEATH_DAYS, horizonFor, isRainyDay, newGame, sleep, tileAt, treat } from './engine.js'

const onField = (s) => ({ ...s, player: { x: 4, y: 2, dir: 'down' } }) // facing (4,3), a field tile

const outlook = (band) => ({
  horizons: [0, 3, 5],
  weather: { rain_hours: 0, rain_when: null },
  diseases: [
    {
      crop: 'chilli',
      disease: 'anthracnose',
      advice_type: 'spray_timing',
      bands: { 0: band, 3: band, 5: band },
    },
  ],
})

test('horizon follows the real forecast week', () => {
  assert.deepEqual(
    [1, 2, 3, 4, 5, 6, 7, 8].map((d) => horizonFor(d)),
    [0, 0, 0, 3, 3, 5, 5, 0],
  )
})

test('rain from the 48 h forecast waters days 1-2 only', () => {
  const wx = { rain_hours: 3, rain_when: 'tomorrow' }
  assert.equal(isRainyDay(1, wx), false)
  assert.equal(isRainyDay(2, wx), true)
  assert.equal(isRainyDay(3, wx), false)
  assert.equal(isRainyDay(1, { rain_hours: 2, rain_when: 'soon' }), true)
})

test('till, plant, water, grow and harvest', () => {
  let s = onField(newGame(1))
  s = act(s, 'chilli').state
  assert.equal(tileAt(s, 4, 3).tilled, true)
  s = act(s, 'chilli').state
  assert.equal(s.seeds.chilli, 3)
  for (let d = 0; d < CROPS.chilli.harvestDay; d++) {
    const r = act(onField(s), 'chilli')
    assert.equal(r.event, 'water')
    s = onField(sleep(r.state, outlook('low')))
    if (tileAt(s, 4, 3).crop.disease) s = treat(s, 4, 3, 'spray_timing', outlook('low').diseases).state
  }
  const r = act(s, 'chilli')
  assert.equal(r.event, 'harvest')
  assert.equal(r.crop, 'chilli')
  assert.ok(r.state.coins > 0 && r.state.stats.harvested === 1)
})

test('high risk infects, wrong treatment fails, untreated plant dies', () => {
  let s = onField(newGame(7))
  s = act(act(s, 'chilli').state, 'chilli').state
  for (let i = 0; i < 20 && !tileAt(s, 4, 3).crop.disease; i++) s = onField(sleep(s, outlook('high')))
  assert.equal(tileAt(s, 4, 3).crop.disease, 'anthracnose')
  assert.equal(act(s, 'chilli').event, 'sick')
  const wrong = treat(s, 4, 3, 'vector_control', outlook('high').diseases)
  assert.equal(wrong.ok, false)
  for (let i = 0; i < DEATH_DAYS; i++) s = onField(sleep(s, outlook('high')))
  assert.equal(tileAt(s, 4, 3).crop.dead, true)
  assert.equal(s.stats.lost, 1)
})

test('right treatment cures; offline outlook never infects', () => {
  let s = onField(newGame(3))
  s = act(act(s, 'chilli').state, 'chilli').state
  for (let i = 0; i < 30; i++) s = onField(sleep(s, null))
  assert.equal(tileAt(s, 4, 3).crop.disease, null)
  s.tiles['4,3'].crop.disease = 'anthracnose'
  const r = treat(s, 4, 3, 'spray_timing', outlook('high').diseases)
  assert.equal(r.ok, true)
  assert.equal(tileAt(r.state, 4, 3).crop.disease, null)
})

test('seeds cost coins', () => {
  const s = buySeed(newGame(1), 'tomato')
  assert.equal(s.seeds.tomato, 5)
  assert.equal(s.coins, 100 - CROPS.tomato.seedCost)
})
