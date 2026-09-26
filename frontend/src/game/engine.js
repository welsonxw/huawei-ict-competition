// Farm-game rules. Pure functions so they can be unit-tested with `node --test`.
// Growth times, prices and infection chances are game rules for play, not agronomic data.
// Disease risk per day comes from the real TaniGuard risk engine via /api/game/outlook.

export const COLS = 14
export const ROWS = 9
export const FIELD = { x0: 3, x1: 12, y0: 3, y1: 7 } // inclusive soil area
export const HOUSE = { x: 0, y: 0, w: 3, h: 2, door: { x: 1, y: 2 } }
export const POND = { x: 12, y: 0, w: 2, h: 2 }
export const TREES = [
  { x: 0, y: 6 },
  { x: 0, y: 8 },
  { x: 1, y: 8 },
]
// Fence along the bottom and right of the field; the field is entered from the top and left.
export const FENCE = [
  ...Array.from({ length: 12 }, (_, i) => ({ x: 2 + i, y: 8 })),
  ...Array.from({ length: 5 }, (_, i) => ({ x: 13, y: 3 + i })),
]
export const DAY_START = 6 * 60
export const BEDTIME = 24 * 60
export const ACTION_MINUTES = 10

export const CROPS = {
  chilli: { seedCost: 10, harvestDay: 8, value: 30 },
  tomato: { seedCost: 8, harvestDay: 7, value: 24 },
}
export const TREAT_COST = 5
export const DEATH_DAYS = 3 // untreated sick days before a plant dies
export const BAND_CHANCE = {
  low: 0.01,
  medium: 0.08,
  high: 0.2,
  unknown: 0.01,
}
export const NEIGHBOUR_CHANCE = 0.1
export const WEEK = 7

export function mulberry32(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const isField = (x, y) => x >= FIELD.x0 && x <= FIELD.x1 && y >= FIELD.y0 && y <= FIELD.y1
const inRect = (r, x, y) => x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h
const onList = (list, x, y) => list.some((p) => p.x === x && p.y === y)
export const isBlocked = (x, y) =>
  x < 0 ||
  y < 0 ||
  x >= COLS ||
  y >= ROWS ||
  inRect(HOUSE, x, y) ||
  inRect(POND, x, y) ||
  onList(TREES, x, y) ||
  onList(FENCE, x, y)
export const isDoor = (x, y) => x === HOUSE.door.x && y === HOUSE.door.y
export const nearPond = (x, y) => x >= POND.x - 1 && y <= POND.y

const key = (x, y) => `${x},${y}`

export function newGame(seed = Date.now()) {
  return {
    seed: seed >>> 0,
    rngState: seed >>> 0,
    day: 1,
    minutes: DAY_START,
    coins: 100,
    seeds: { chilli: 4, tomato: 4 },
    water: 10,
    player: { x: 1, y: 3, dir: 'down' },
    tiles: {}, // "x,y" -> { tilled, watered, crop: {kind, age, disease, sickDays, dead} }
    stats: { harvested: 0, lost: 0, treated: 0 },
    log: [],
  }
}

// Which real forecast horizon applies on a game day: day 1 = today, day 4 = +3, day 6 = +5, then the week repeats.
export function horizonFor(day, horizons = [0, 3, 5]) {
  const offset = (day - 1) % WEEK
  return horizons.filter((h) => h <= offset).pop() ?? horizons[0]
}

// Real 48 h forecast rain waters the field on the first two game days of each week.
export function isRainyDay(day, weather) {
  const offset = (day - 1) % WEEK
  if (!weather || offset > 1) return false
  if (offset === 0) return weather.rain_hours > 0 && ['soon', 'today'].includes(weather.rain_when)
  return weather.rain_hours > 0
}

export function facing(p) {
  const d = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[p.dir]
  return { x: p.x + d[0], y: p.y + d[1] }
}

export function move(state, dir) {
  const p = { ...state.player, dir }
  const t = facing(p)
  if (!isBlocked(t.x, t.y)) Object.assign(p, t)
  return { ...state, player: p }
}

function setTile(state, x, y, tile) {
  return { ...state, tiles: { ...state.tiles, [key(x, y)]: tile } }
}

export function tileAt(state, x, y) {
  return state.tiles[key(x, y)] || { tilled: false, watered: false, crop: null }
}

// Context action on the tile the player faces. Returns { state, event } where event names what happened.
function actOnTile(state, seedKind) {
  const { x, y } = facing(state.player)
  if (isDoor(x, y) || isDoor(state.player.x, state.player.y)) return { state, event: 'door' }
  if (nearPond(x, y) || (x >= POND.x && y < POND.y + POND.h)) return { state: { ...state, water: 10 }, event: 'refill' }
  if (!isField(x, y)) return { state, event: 'none' }
  const tile = tileAt(state, x, y)
  const crop = tile.crop
  if (!tile.tilled)
    return {
      state: setTile(state, x, y, { ...tile, tilled: true }),
      event: 'till',
    }
  if (!crop) {
    if (state.seeds[seedKind] <= 0) return { state, event: 'noSeeds' }
    const next = setTile(state, x, y, {
      ...tile,
      crop: { kind: seedKind, age: 0, disease: null, sickDays: 0, dead: false },
    })
    return {
      state: {
        ...next,
        seeds: { ...state.seeds, [seedKind]: state.seeds[seedKind] - 1 },
      },
      event: 'plant',
    }
  }
  if (crop.dead)
    return {
      state: setTile(state, x, y, { ...tile, crop: null }),
      event: 'clear',
    }
  if (crop.disease) return { state, event: 'sick', tile: { x, y } }
  if (crop.age >= CROPS[crop.kind].harvestDay) {
    const next = setTile(state, x, y, { ...tile, crop: null })
    return {
      state: {
        ...next,
        coins: state.coins + CROPS[crop.kind].value,
        stats: { ...state.stats, harvested: state.stats.harvested + 1 },
      },
      event: 'harvest',
      crop: crop.kind,
    }
  }
  if (tile.watered) return { state, event: 'alreadyWatered' }
  if (state.water <= 0) return { state, event: 'noWater' }
  return {
    state: {
      ...setTile(state, x, y, { ...tile, watered: true }),
      water: state.water - 1,
    },
    event: 'water',
  }
}

// Each farm action takes ACTION_MINUTES of the day; after midnight the farmer is too tired and must sleep.
export function act(state, seedKind) {
  const minutes = state.minutes ?? DAY_START
  const r = actOnTile(state, seedKind)
  if (r.event === 'door' || r.event === 'none' || r.event === 'sick') return r
  if (minutes >= BEDTIME) return { state, event: 'tooLate' }
  if (r.state === state) return r
  return { ...r, state: { ...r.state, minutes: minutes + ACTION_MINUTES } }
}

export function buySeed(state, kind) {
  const cost = CROPS[kind].seedCost
  if (state.coins < cost) return state
  return {
    ...state,
    coins: state.coins - cost,
    seeds: { ...state.seeds, [kind]: state.seeds[kind] + 1 },
  }
}

// Treatment choices are the disease profile's advice types; only the matching one cures.
export function treat(state, x, y, adviceType, profiles) {
  const tile = tileAt(state, x, y)
  const crop = tile.crop
  if (!crop?.disease || state.coins < TREAT_COST) return { state, ok: false }
  const right = profiles.find((d) => d.crop === crop.kind && d.disease === crop.disease)?.advice_type === adviceType
  const paid = { ...state, coins: state.coins - TREAT_COST }
  if (!right) return { state: paid, ok: false }
  const next = setTile(paid, x, y, {
    ...tile,
    crop: { ...crop, disease: null, sickDays: 0 },
  })
  return {
    state: {
      ...next,
      stats: { ...state.stats, treated: state.stats.treated + 1 },
    },
    ok: true,
  }
}

function sickNeighbours(state, x, y, kind) {
  let n = 0
  for (const [dx, dy] of [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ]) {
    const c = tileAt(state, x + dx, y + dy).crop
    if (c && c.kind === kind && c.disease && !c.dead) n++
  }
  return n
}

// Advance one night. `outlook` is the /api/game/outlook body (or null when offline: no disease, no rain).
export function sleep(state, outlook) {
  const rng = mulberry32(state.rngState)
  const day = state.day + 1
  const h = String(horizonFor(day, outlook?.horizons))
  const rainy = isRainyDay(day, outlook?.weather)
  const tiles = {}
  const events = []
  let lost = 0
  for (const [k, tile] of Object.entries(state.tiles)) {
    const [x, y] = k.split(',').map(Number)
    let crop = tile.crop
    if (crop && !crop.dead) {
      crop = { ...crop }
      if (tile.watered || rainy) crop.age += 1
      if (crop.disease) {
        crop.sickDays += 1
        if (crop.sickDays >= DEATH_DAYS) {
          crop.dead = true
          lost++
          events.push({ type: 'died', x, y, disease: crop.disease })
        }
      } else {
        const neighbours = sickNeighbours(state, x, y, crop.kind)
        for (const d of (outlook?.diseases || []).filter((d) => d.crop === crop.kind)) {
          const p = (BAND_CHANCE[d.bands[h]] ?? 0) + neighbours * NEIGHBOUR_CHANCE
          if (rng() < p) {
            crop.disease = d.disease
            crop.sickDays = 0
            events.push({ type: 'infected', x, y, disease: d.disease })
            break
          }
        }
      }
    }
    tiles[k] = { ...tile, watered: rainy, crop }
  }
  return {
    ...state,
    day,
    minutes: DAY_START,
    rngState: Math.floor(rng() * 4294967296),
    tiles,
    player: { x: HOUSE.door.x, y: HOUSE.door.y + 1, dir: 'down' },
    stats: { ...state.stats, lost: state.stats.lost + lost },
    log: [{ day, rainy, horizon: Number(h), events }, ...state.log].slice(0, 10),
  }
}
