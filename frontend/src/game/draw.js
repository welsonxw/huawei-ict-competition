// Procedural pixel art for the farm game (no image assets). One tile = 16 px, scaled up with
// image-rendering: pixelated. Colours come from the ENDESGA 32 palette (free pixel-art palette by Endesga).
import { COLS, CROPS, FENCE, HOUSE, POND, ROWS, TREES, facing, isField } from './engine.js'

export const TILE = 16

export const P = {
  rust: '#be4a2f',
  orange: '#d77643',
  sand: '#ead4aa',
  tan: '#e4a672',
  wood: '#b86f50',
  bark: '#733e39',
  night: '#3e2731',
  wine: '#a22633',
  red: '#e43b44',
  amber: '#f77622',
  gold: '#feae34',
  yellow: '#fee761',
  lime: '#63c74d',
  green: '#3e8948',
  pine: '#265c42',
  deep: '#193c3e',
  navy: '#124e89',
  sky: '#0099db',
  cyan: '#2ce8f5',
  white: '#ffffff',
  mist: '#c0cbdc',
  grey: '#8b9bb4',
  slate: '#5a6988',
  ink: '#3a4466',
  dusk: '#262b44',
  black: '#181425',
  skin: '#e8b796',
  skin2: '#c28569',
  pink: '#f6757a',
}

function px(ctx, color, x, y, w = 1, h = 1) {
  ctx.fillStyle = color
  ctx.fillRect(x, y, w, h)
}

const hash = (a, b) => {
  let h = (a * 374761393 + b * 668265263) >>> 0
  h = Math.imul(h ^ (h >>> 13), 1274126177) >>> 0
  return (h ^ (h >>> 16)) >>> 0
}

const onPath = (gx, gy) => (gx === HOUSE.door.x && gy >= HOUSE.door.y && gy <= 5) || (gy === 2 && gx >= 1 && gx <= 11)

function grass(ctx, gx, gy, t) {
  const x = gx * TILE
  const y = gy * TILE
  px(ctx, P.green, x, y, TILE, TILE)
  const h = hash(gx, gy)
  for (let i = 0; i < 6; i++) {
    const r = hash(h, i)
    const sx = x + (r % 15)
    const sy = y + ((r >> 4) % 14)
    px(ctx, i % 2 ? P.lime : P.pine, sx, sy, 1, 2)
    if (i % 3 === 0) px(ctx, P.lime, sx + 1, sy + 1)
  }
  const deco = h % 11
  if (deco === 0) {
    const sway = Math.floor(t / 700 + gx) % 2
    px(ctx, P.pine, x + 7, y + 9, 1, 4)
    px(ctx, P.white, x + 6 + sway, y + 7, 3, 1)
    px(ctx, P.white, x + 7 + sway, y + 6, 1, 3)
    px(ctx, P.yellow, x + 7 + sway, y + 7)
  } else if (deco === 1) {
    px(ctx, P.pine, x + 4, y + 10, 1, 3)
    px(ctx, P.red, x + 3, y + 8, 3, 2)
    px(ctx, P.pink, x + 4, y + 8)
  } else if (deco === 2) {
    px(ctx, P.slate, x + 9, y + 10, 4, 2)
    px(ctx, P.grey, x + 10, y + 9, 3, 2)
    px(ctx, P.mist, x + 10, y + 9)
  }
}

function path(ctx, gx, gy) {
  const x = gx * TILE
  const y = gy * TILE
  px(ctx, P.tan, x, y, TILE, TILE)
  const h = hash(gx + 50, gy)
  for (let i = 0; i < 7; i++) {
    const r = hash(h, i)
    px(ctx, i % 2 ? P.skin2 : P.sand, x + (r % 15), y + ((r >> 5) % 15), 2, 1)
  }
  // grassy edges where the path meets grass
  if (!onPath(gx, gy - 1)) for (let i = 0; i < 16; i += 3) px(ctx, P.green, x + i, y, 2, 1)
  if (!onPath(gx, gy + 1)) for (let i = 1; i < 16; i += 3) px(ctx, P.green, x + i, y + 15, 2, 1)
}

function soil(ctx, gx, gy, tile, t) {
  const x = gx * TILE
  const y = gy * TILE
  if (!tile?.tilled) {
    px(ctx, P.green, x, y, TILE, TILE)
    px(ctx, P.skin2, x + 1, y + 1, 14, 14)
    const h = hash(gx, gy + 99)
    for (let i = 0; i < 6; i++) {
      const r = hash(h, i)
      px(ctx, i % 2 ? P.wood : P.tan, x + 2 + (r % 12), y + 2 + ((r >> 4) % 12), 2, 1)
    }
    px(ctx, P.lime, x + 2 + (h % 10), y + 3, 1, 2)
    return
  }
  const wet = tile.watered
  px(ctx, P.green, x, y, TILE, TILE)
  px(ctx, wet ? P.night : P.bark, x + 1, y + 1, 14, 14)
  px(ctx, wet ? P.bark : P.wood, x + 1, y + 1, 14, 1)
  for (const fy of [4, 8, 12]) {
    px(ctx, wet ? P.black : P.night, x + 2, y + fy, 12, 1)
    px(ctx, wet ? P.bark : P.wood, x + 2, y + fy - 1, 12, 1)
  }
  if (wet && Math.floor(t / 900 + gx + gy) % 4 === 0) px(ctx, P.sky, x + 4 + (gx % 7), y + 6, 2, 1)
}

function crop(ctx, x, y, c, t) {
  const { harvestDay } = CROPS[c.kind]
  const stage = c.age >= harvestDay ? 3 : c.age >= harvestDay * 0.6 ? 2 : c.age >= 2 ? 1 : 0
  const sway = Math.floor(t / 600 + x) % 2
  const leaf = c.dead ? P.grey : c.disease ? P.gold : P.lime
  const leaf2 = c.dead ? P.slate : c.disease ? P.skin2 : P.green
  const stem = c.dead ? P.slate : P.pine
  px(ctx, 'rgba(24,20,37,0.25)', x + 4, y + 13, 8, 2)
  if (stage === 0) {
    px(ctx, stem, x + 7, y + 10, 1, 4)
    px(ctx, leaf, x + 5, y + 9, 2, 2)
    px(ctx, leaf, x + 8, y + 8, 2, 2)
    px(ctx, leaf2, x + 5, y + 10)
    return
  }
  if (c.kind === 'tomato' && stage >= 2) {
    px(ctx, P.bark, x + 11, y + 1, 1, 13)
    px(ctx, P.wood, x + 11, y + 1, 1, 1)
  }
  const top = stage === 1 ? 7 : 2
  px(ctx, stem, x + 7, y + top, 2, 14 - top)
  for (let i = top + 1; i < 13; i += 3) {
    const s = (i >> 1) % 2 ? sway : 0
    px(ctx, leaf, x + 3 + s, y + i, 4, 2)
    px(ctx, leaf2, x + 3 + s, y + i + 1, 2, 1)
    px(ctx, leaf, x + 9 - s, y + i + 1, 4, 2)
    px(ctx, leaf2, x + 11 - s, y + i + 2, 2, 1)
  }
  if (stage === 1) return
  px(ctx, leaf, x + 6, y + top - 1, 4, 2)
  if (c.disease && !c.dead) {
    for (const [sx, sy] of [
      [4, 3],
      [11, 5],
      [5, 7],
      [10, 9],
    ])
      px(ctx, P.night, x + sx, y + top + sy - 2)
  }
  if (c.dead) return
  const ripe = stage === 3
  if (c.kind === 'tomato') {
    for (const [fx, fy] of [
      [3, 6],
      [9, 4],
      [5, 10],
      [10, 9],
    ]) {
      px(ctx, ripe ? P.red : P.lime, x + fx, y + fy, 3, 3)
      px(ctx, ripe ? P.wine : P.green, x + fx + 1, y + fy + 2, 2, 1)
      px(ctx, ripe ? P.pink : P.yellow, x + fx, y + fy)
      px(ctx, P.pine, x + fx + 1, y + fy - 1)
    }
  } else {
    for (const [fx, fy] of [
      [4, 6],
      [11, 5],
      [6, 10],
      [10, 10],
    ]) {
      px(ctx, P.pine, x + fx, y + fy - 1)
      px(ctx, ripe ? P.red : P.lime, x + fx, y + fy, 1, 4)
      px(ctx, ripe ? P.wine : P.green, x + fx + 1, y + fy + 1, 1, 3)
      px(ctx, ripe ? P.pink : P.yellow, x + fx, y + fy)
    }
  }
  if (ripe && Math.floor(t / 400) % 6 === 0) {
    px(ctx, P.white, x + 13, y + 2)
    px(ctx, P.white, x + 12, y + 3, 3, 1)
    px(ctx, P.white, x + 13, y + 4)
  }
}

function tree(ctx, gx, gy, t) {
  const x = gx * TILE
  const y = gy * TILE
  const sway = Math.floor(t / 900 + gx) % 2
  px(ctx, 'rgba(24,20,37,0.3)', x + 1, y + 12, 14, 4)
  px(ctx, P.bark, x + 6, y + 6, 4, 9)
  px(ctx, P.night, x + 9, y + 6, 1, 9)
  px(ctx, P.wood, x + 6, y + 8, 1, 5)
  const cx = x + sway
  const cy = y - 12
  const blobs = [
    [2, 8, 12, 8, P.pine],
    [0, 4, 16, 10, P.pine],
    [3, 0, 10, 6, P.pine],
    [2, 2, 10, 8, P.green],
    [1, 6, 12, 6, P.green],
    [4, 1, 6, 4, P.lime],
    [2, 5, 3, 2, P.lime],
    [9, 4, 3, 2, P.lime],
  ]
  for (const [bx, by, bw, bh, col] of blobs) px(ctx, col, cx + bx, cy + by, bw, bh)
  if (gy % 2 === 0) {
    px(ctx, P.red, cx + 4, cy + 9, 2, 2)
    px(ctx, P.red, cx + 10, cy + 6, 2, 2)
  }
}

function fencePost(ctx, gx, gy) {
  const x = gx * TILE
  const y = gy * TILE
  const right = FENCE.some((f) => f.x === gx + 1 && f.y === gy)
  const down = FENCE.some((f) => f.x === gx && f.y === gy + 1)
  px(ctx, 'rgba(24,20,37,0.25)', x + 5, y + 13, 7, 2)
  if (right) {
    px(ctx, P.wood, x + 8, y + 5, 16, 2)
    px(ctx, P.bark, x + 8, y + 7, 16, 1)
    px(ctx, P.wood, x + 8, y + 9, 16, 2)
    px(ctx, P.bark, x + 8, y + 11, 16, 1)
  }
  if (down) {
    px(ctx, P.wood, x + 7, y + 8, 2, 16)
    px(ctx, P.bark, x + 9, y + 8, 1, 16)
  }
  px(ctx, P.bark, x + 6, y + 2, 5, 12)
  px(ctx, P.wood, x + 6, y + 2, 4, 11)
  px(ctx, P.tan, x + 6, y + 2, 4, 1)
  px(ctx, P.night, x + 10, y + 3, 1, 11)
}

function house(ctx, t, night) {
  const x = HOUSE.x * TILE
  const y = HOUSE.y * TILE
  const w = HOUSE.w * TILE
  const h = HOUSE.h * TILE
  px(ctx, 'rgba(24,20,37,0.3)', x + 2, y + h - 2, w - 2, 4)
  // walls: horizontal planks
  px(ctx, P.bark, x + 3, y + 13, w - 6, h - 13)
  for (let py = y + 14; py < y + h; py += 3) {
    px(ctx, P.wood, x + 4, py, w - 8, 2)
    px(ctx, P.tan, x + 4 + ((py * 7) % 20), py, 6, 1)
  }
  // roof with shingles
  for (let i = 0; i < 14; i++) {
    const inset = Math.max(0, 6 - i)
    px(ctx, i % 3 === 2 ? P.wine : P.red, x + inset, y + i, w - inset * 2, 1)
  }
  for (let sx = 2; sx < w - 2; sx += 4) px(ctx, P.wine, x + sx, y + 5 + (sx % 8 === 2 ? 3 : 0), 1, 3)
  px(ctx, P.night, x, y + 13, w, 1)
  // chimney + smoke
  px(ctx, P.slate, x + 34, y, 5, 5)
  px(ctx, P.grey, x + 34, y, 5, 1)
  const puff = Math.floor(t / 250) % 8
  px(ctx, 'rgba(192,203,220,0.7)', x + 36 + (puff % 3), y - 2 - puff, 3, 2)
  // windows
  for (const wx of [x + 5, x + 34]) {
    px(ctx, P.bark, wx - 1, y + 17, 9, 8)
    px(ctx, night ? P.gold : P.sky, wx, y + 18, 7, 6)
    px(ctx, night ? P.yellow : P.cyan, wx + 1, y + 19, 2, 2)
    px(ctx, P.bark, wx + 3, y + 18, 1, 6)
    px(ctx, P.lime, wx - 1, y + 25, 9, 2)
    px(ctx, P.red, wx + 1, y + 24, 1, 1)
    px(ctx, P.yellow, wx + 5, y + 24, 1, 1)
  }
  // door
  const dx = HOUSE.door.x * TILE + 3
  px(ctx, P.night, dx - 1, y + 17, 12, h - 17)
  px(ctx, P.orange, dx, y + 18, 10, h - 18)
  px(ctx, P.rust, dx + 4, y + 18, 1, h - 18)
  px(ctx, P.gold, dx + 7, y + 24, 1, 2)
}

function pond(ctx, t) {
  const x = POND.x * TILE
  const y = POND.y * TILE
  const w = POND.w * TILE
  const h = POND.h * TILE
  px(ctx, P.sand, x + 1, y, w - 1, h - 1)
  px(ctx, P.skin2, x + 2, y + h - 3, w - 3, 2)
  px(ctx, P.navy, x + 3, y + 1, w - 5, h - 5)
  px(ctx, P.sky, x + 4, y + 2, w - 7, h - 8)
  px(ctx, P.navy, x + 3, y + 1, w - 5, 2)
  const wave = Math.floor(t / 500) % 3
  px(ctx, P.cyan, x + 8 + wave * 2, y + 10, 5, 1)
  px(ctx, P.cyan, x + 18 - wave * 2, y + 20, 4, 1)
  px(ctx, P.white, x + 22, y + 7 + wave, 1, 1)
  px(ctx, P.lime, x + 7, y + 18, 5, 3)
  px(ctx, P.green, x + 9, y + 20, 3, 1)
  px(ctx, P.pink, x + 8, y + 18, 2, 1)
  px(ctx, P.pine, x + 26, y + 2, 1, 6)
  px(ctx, P.bark, x + 26, y + 1, 1, 2)
}

function farmer(ctx, fx, fy, dir, walking, t) {
  const x = Math.round(fx)
  const y = Math.round(fy) - 6
  const step = walking ? Math.floor(t / 120) % 2 : 0
  const bob = walking ? step : Math.floor(t / 600) % 2 ? 0 : 0
  px(ctx, 'rgba(24,20,37,0.3)', x + 3, y + 20, 10, 2)
  // legs
  px(ctx, P.navy, x + 5, y + 16, 2, 3 + (step ? 0 : 1))
  px(ctx, P.navy, x + 9, y + 16, 2, 3 + (step ? 1 : 0))
  px(ctx, P.night, x + 5, y + 19 + (step ? 0 : 1), 2, 1)
  px(ctx, P.night, x + 9, y + 19 + (step ? 1 : 0), 2, 1)
  // body: red shirt, blue overalls
  px(ctx, P.red, x + 4, y + 10 + bob, 8, 6)
  px(ctx, P.navy, x + 5, y + 12 + bob, 6, 5)
  px(ctx, P.sky, x + 5, y + 12 + bob, 1, 1)
  px(ctx, P.sky, x + 10, y + 12 + bob, 1, 1)
  // arms
  const swing = walking ? (step ? 1 : -1) : 0
  px(ctx, P.red, x + 3, y + 11 + bob + swing, 1, 3)
  px(ctx, P.red, x + 12, y + 11 + bob - swing, 1, 3)
  px(ctx, P.skin, x + 3, y + 14 + bob + swing, 1, 1)
  px(ctx, P.skin, x + 12, y + 14 + bob - swing, 1, 1)
  // head
  px(ctx, P.skin, x + 5, y + 5 + bob, 6, 5)
  px(ctx, P.bark, x + 4, y + 5 + bob, 1, 3)
  px(ctx, P.bark, x + 11, y + 5 + bob, 1, 3)
  if (dir === 'up') px(ctx, P.bark, x + 5, y + 5 + bob, 6, 4)
  else if (dir === 'left') {
    px(ctx, P.bark, x + 9, y + 5 + bob, 3, 3)
    px(ctx, P.black, x + 6, y + 7 + bob)
    px(ctx, P.skin2, x + 4, y + 8 + bob)
  } else if (dir === 'right') {
    px(ctx, P.bark, x + 4, y + 5 + bob, 3, 3)
    px(ctx, P.black, x + 9, y + 7 + bob)
    px(ctx, P.skin2, x + 11, y + 8 + bob)
  } else {
    px(ctx, P.black, x + 6, y + 7 + bob)
    px(ctx, P.black, x + 9, y + 7 + bob)
    px(ctx, P.pink, x + 5, y + 8 + bob)
    px(ctx, P.pink, x + 10, y + 8 + bob)
  }
  // straw hat
  px(ctx, P.tan, x + 2, y + 4 + bob, 12, 2)
  px(ctx, P.gold, x + 4, y + 1 + bob, 8, 3)
  px(ctx, P.yellow, x + 5, y + 1 + bob, 5, 1)
  px(ctx, P.rust, x + 4, y + 3 + bob, 8, 1)
  px(ctx, P.skin2, x + 2, y + 5 + bob, 12, 1)
}

function cursor(ctx, gx, gy, t) {
  const x = gx * TILE
  const y = gy * TILE
  const a = 0.55 + 0.35 * Math.sin(t / 200)
  ctx.strokeStyle = `rgba(255,255,255,${a.toFixed(2)})`
  ctx.lineWidth = 1
  ctx.strokeRect(x + 0.5, y + 0.5, TILE - 1, TILE - 1)
  px(ctx, P.yellow, x, y, 3, 1)
  px(ctx, P.yellow, x, y, 1, 3)
  px(ctx, P.yellow, x + 13, y + 15, 3, 1)
  px(ctx, P.yellow, x + 15, y + 13, 1, 3)
}

function butterfly(ctx, t) {
  const bx = 40 + Math.sin(t / 2100) * 30 + Math.sin(t / 700) * 6
  const by = 125 + Math.cos(t / 1600) * 8
  const flap = Math.floor(t / 150) % 2
  px(ctx, P.yellow, Math.round(bx) - (flap ? 2 : 1), Math.round(by), flap ? 2 : 1, 2)
  px(ctx, P.yellow, Math.round(bx) + 1, Math.round(by), flap ? 2 : 1, 2)
  px(ctx, P.black, Math.round(bx), Math.round(by), 1, 2)
}

// Ambient light: warm dusk from 17:00, blue night from 20:00.
export function lightTint(minutes) {
  if (minutes < 17 * 60) return null
  const k = Math.min(1, (minutes - 17 * 60) / (5 * 60))
  return minutes < 20 * 60
    ? `rgba(247,118,34,${(0.08 + 0.1 * k).toFixed(2)})`
    : `rgba(38,43,68,${(0.3 + 0.2 * k).toFixed(2)})`
}

// view = { x, y } animated player position in pixels, eased toward the logical tile.
export function drawFarm(ctx, state, t, { rainy, view }) {
  ctx.imageSmoothingEnabled = false
  const minutes = state.minutes ?? 360
  const night = minutes >= 19 * 60
  for (let gy = 0; gy < ROWS; gy++) {
    for (let gx = 0; gx < COLS; gx++) {
      if (isField(gx, gy)) soil(ctx, gx, gy, state.tiles[`${gx},${gy}`], t)
      else if (onPath(gx, gy)) path(ctx, gx, gy)
      else grass(ctx, gx, gy, t)
    }
  }
  pond(ctx, t)
  const p = state.player
  const tx = p.x * TILE
  const ty = p.y * TILE
  view.x += (tx - view.x) * 0.35
  view.y += (ty - view.y) * 0.35
  if (Math.abs(tx - view.x) < 0.3) view.x = tx
  if (Math.abs(ty - view.y) < 0.3) view.y = ty
  const walking = view.x !== tx || view.y !== ty
  const f = facing(p)
  if (!walking && f.x >= 0 && f.y >= 0 && f.x < COLS && f.y < ROWS) cursor(ctx, f.x, f.y, t)
  // y-sorted objects so the farmer walks behind crops, fences and trees below him
  const objects = [
    { y: HOUSE.y + HOUSE.h - 1, draw: () => house(ctx, t, night) },
    ...TREES.map((tr) => ({ y: tr.y, draw: () => tree(ctx, tr.x, tr.y, t) })),
    ...FENCE.map((fp) => ({ y: fp.y, draw: () => fencePost(ctx, fp.x, fp.y) })),
    ...Object.entries(state.tiles)
      .filter(([, tile]) => tile.crop)
      .map(([k, tile]) => {
        const [cx, cy] = k.split(',').map(Number)
        return { y: cy, draw: () => crop(ctx, cx * TILE, cy * TILE, tile.crop, t) }
      }),
    { y: view.y / TILE + 0.5, draw: () => farmer(ctx, view.x, view.y, p.dir, walking, t) },
  ].sort((a, b) => a.y - b.y)
  for (const o of objects) o.draw()
  if (!rainy && !night) butterfly(ctx, t)
  const tint = lightTint(minutes)
  if (tint) px(ctx, tint, 0, 0, COLS * TILE, ROWS * TILE)
  if (rainy) {
    px(ctx, 'rgba(58,68,102,0.28)', 0, 0, COLS * TILE, ROWS * TILE)
    for (let i = 0; i < 90; i++) {
      const rx = Math.floor((i * 53 + t / 6) % (COLS * TILE))
      const ry = Math.floor((i * 97 + t / 2.5) % (ROWS * TILE))
      px(ctx, 'rgba(192,203,220,0.6)', rx, ry, 1, 3)
      if (i % 9 === 0) px(ctx, 'rgba(192,203,220,0.5)', (rx + 7) % (COLS * TILE), (ry + 40) % (ROWS * TILE), 2, 1)
    }
  }
}

// Small UI icons drawn on 16x16 canvases (hotbar, HUD).
const ICONS = {
  coin: (c) => {
    px(c, P.bark, 4, 3, 8, 10)
    px(c, P.bark, 3, 4, 10, 8)
    px(c, P.gold, 4, 4, 8, 8)
    px(c, P.yellow, 5, 4, 5, 2)
    px(c, P.amber, 7, 6, 2, 4)
  },
  water: (c) => {
    px(c, P.slate, 3, 6, 9, 7)
    px(c, P.grey, 3, 6, 9, 2)
    px(c, P.mist, 4, 6, 3, 1)
    px(c, P.slate, 12, 7, 3, 1)
    px(c, P.slate, 14, 5, 1, 2)
    px(c, P.slate, 5, 3, 5, 1)
    px(c, P.slate, 4, 4, 1, 2)
    px(c, P.slate, 10, 4, 1, 2)
    px(c, P.sky, 14, 8, 1, 2)
  },
  chilli: (c) => {
    px(c, P.pine, 9, 1, 2, 3)
    px(c, P.green, 7, 3, 5, 2)
    px(c, P.red, 7, 5, 4, 3)
    px(c, P.red, 6, 8, 4, 3)
    px(c, P.red, 5, 11, 3, 2)
    px(c, P.red, 4, 13, 2, 1)
    px(c, P.wine, 9, 6, 1, 4)
    px(c, P.pink, 7, 5, 1, 2)
  },
  tomato: (c) => {
    px(c, P.red, 3, 5, 10, 8)
    px(c, P.red, 4, 4, 8, 10)
    px(c, P.wine, 5, 12, 7, 2)
    px(c, P.pink, 5, 5, 2, 2)
    px(c, P.green, 5, 3, 6, 2)
    px(c, P.pine, 7, 1, 2, 3)
  },
  sun: (c) => {
    px(c, P.gold, 5, 5, 6, 6)
    px(c, P.yellow, 6, 6, 3, 3)
    for (const [x, y] of [
      [7, 1],
      [7, 13],
      [1, 7],
      [13, 7],
      [3, 3],
      [11, 3],
      [3, 11],
      [11, 11],
    ])
      px(c, P.gold, x, y, 2, 2)
  },
  rain: (c) => {
    px(c, P.mist, 3, 4, 10, 4)
    px(c, P.white, 5, 3, 5, 2)
    px(c, P.grey, 3, 7, 10, 1)
    for (const [x, y] of [
      [4, 10],
      [8, 11],
      [11, 9],
      [6, 13],
    ])
      px(c, P.sky, x, y, 1, 2)
  },
  moon: (c) => {
    px(c, P.yellow, 5, 3, 6, 10)
    px(c, P.yellow, 4, 5, 2, 6)
    px(c, P.dusk, 8, 3, 4, 8)
  },
  farmer: (c) => {
    px(c, P.skin, 4, 6, 8, 7)
    px(c, P.bark, 3, 6, 1, 4)
    px(c, P.bark, 12, 6, 1, 4)
    px(c, P.black, 6, 9, 1, 1)
    px(c, P.black, 9, 9, 1, 1)
    px(c, P.pink, 5, 11, 1, 1)
    px(c, P.pink, 10, 11, 1, 1)
    px(c, P.tan, 1, 5, 14, 2)
    px(c, P.gold, 4, 1, 8, 4)
    px(c, P.rust, 4, 4, 8, 1)
    px(c, P.red, 3, 13, 10, 3)
  },
}

export function drawIcon(ctx, name) {
  ctx.clearRect(0, 0, 16, 16)
  ctx.imageSmoothingEnabled = false
  ICONS[name]?.(ctx)
}
