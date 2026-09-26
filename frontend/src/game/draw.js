// Procedural pixel art for the farm game (no image assets). One tile = 16 px, drawn at 2x.
import { COLS, CROPS, FIELD, HOUSE, POND, ROWS, isField } from './engine.js'

export const TILE = 16

const C = {
  grass: '#6DAA45',
  grass2: '#5E9A3A',
  soil: '#9A6B3F',
  tilled: '#7A4E2A',
  wet: '#553419',
  stem: '#2F7D32',
  leaf: '#3FA34D',
  red: '#D7263D',
  sick: '#8D6E2F',
  spot: '#4A3410',
  dead: '#8C8C8C',
  wall: '#C98C5A',
  roof: '#A23B2A',
  door: '#5B3A1E',
  water: '#3A8FD1',
  water2: '#6DB6EA',
  skin: '#F1C27D',
  shirt: '#2A6FBF',
  hat: '#E0B04A',
  path: '#D9C28F',
}

function px(ctx, color, x, y, w = 1, h = 1) {
  ctx.fillStyle = color
  ctx.fillRect(x, y, w, h)
}

function grass(ctx, x, y) {
  px(ctx, C.grass, x, y, TILE, TILE)
  const seed = (x * 7 + y * 13) % 5
  px(ctx, C.grass2, x + 3 + seed, y + 4, 1, 2)
  px(ctx, C.grass2, x + 10 - seed, y + 11, 1, 2)
}

function crop(ctx, x, y, c) {
  const { harvestDay } = CROPS[c.kind]
  const stage = c.age >= harvestDay ? 3 : c.age >= harvestDay * 0.6 ? 2 : c.age >= 2 ? 1 : 0
  const leaf = c.dead ? C.dead : c.disease ? C.sick : C.leaf
  const stem = c.dead ? C.dead : C.stem
  if (stage === 0) {
    px(ctx, stem, x + 7, y + 10, 2, 3)
    px(ctx, leaf, x + 5, y + 9, 2, 1)
    px(ctx, leaf, x + 9, y + 9, 2, 1)
    return
  }
  const top = stage === 1 ? 7 : 3
  px(ctx, stem, x + 7, y + top, 2, 13 - top)
  for (let i = top + 1; i < 12; i += 3) {
    px(ctx, leaf, x + 3, y + i, 4, 2)
    px(ctx, leaf, x + 9, y + i + 1, 4, 2)
  }
  if (c.disease && !c.dead) {
    px(ctx, C.spot, x + 4, y + top + 2)
    px(ctx, C.spot, x + 11, y + top + 4)
    px(ctx, C.spot, x + 5, y + top + 5)
  }
  if (stage === 3 && !c.dead) {
    if (c.kind === 'tomato') {
      px(ctx, C.red, x + 3, y + 8, 3, 3)
      px(ctx, C.red, x + 10, y + 6, 3, 3)
    } else {
      px(ctx, C.red, x + 4, y + 7, 1, 4)
      px(ctx, C.red, x + 11, y + 6, 1, 4)
      px(ctx, C.red, x + 6, y + 10, 1, 3)
    }
  }
}

function player(ctx, p, t) {
  const x = p.x * TILE
  const y = p.y * TILE
  const bob = Math.floor(t / 300) % 2
  px(ctx, C.hat, x + 3, y + 1 + bob, 10, 2)
  px(ctx, C.hat, x + 5, y + bob, 6, 1)
  px(ctx, C.skin, x + 5, y + 3 + bob, 6, 4)
  if (p.dir !== 'up') {
    const eye = p.dir === 'left' ? 0 : p.dir === 'right' ? 2 : 1
    px(ctx, '#222', x + 5 + eye, y + 4 + bob)
    px(ctx, '#222', x + 8 + eye, y + 4 + bob)
  }
  px(ctx, C.shirt, x + 4, y + 7 + bob, 8, 5)
  px(ctx, '#3B2F2F', x + 5, y + 12, 2, 3)
  px(ctx, '#3B2F2F', x + 9, y + 12, 2, 3)
}

export function drawFarm(ctx, state, t, rainy) {
  ctx.imageSmoothingEnabled = false
  for (let gy = 0; gy < ROWS; gy++) {
    for (let gx = 0; gx < COLS; gx++) {
      const x = gx * TILE
      const y = gy * TILE
      grass(ctx, x, y)
      if (gy === HOUSE.door.y && gx <= FIELD.x0 - 1) px(ctx, C.path, x, y + 4, TILE, 8)
      if (isField(gx, gy)) {
        const tile = state.tiles[`${gx},${gy}`]
        px(ctx, tile?.watered ? C.wet : tile?.tilled ? C.tilled : C.soil, x + 1, y + 1, TILE - 2, TILE - 2)
        if (tile?.tilled) {
          px(ctx, 'rgba(0,0,0,0.15)', x + 2, y + 5, TILE - 4, 1)
          px(ctx, 'rgba(0,0,0,0.15)', x + 2, y + 10, TILE - 4, 1)
        }
        if (tile?.crop) crop(ctx, x, y, tile.crop)
      }
    }
  }
  // house
  const hx = HOUSE.x * TILE
  const hy = HOUSE.y * TILE
  px(ctx, C.wall, hx + 2, hy + 12, HOUSE.w * TILE - 4, HOUSE.h * TILE - 12)
  for (let i = 0; i < 12; i++) px(ctx, C.roof, hx + i, hy + 12 - i, HOUSE.w * TILE - i * 2, 1)
  px(ctx, C.door, HOUSE.door.x * TILE + 4, hy + HOUSE.h * TILE - 12, 8, 12)
  px(ctx, '#BFE3FF', hx + 6, hy + 18, 6, 5)
  px(ctx, '#BFE3FF', hx + 36, hy + 18, 6, 5)
  // pond
  const wave = Math.floor(t / 500) % 2
  px(ctx, C.water, POND.x * TILE + 1, POND.y * TILE + 1, POND.w * TILE - 2, POND.h * TILE - 2)
  px(ctx, C.water2, POND.x * TILE + 5 + wave * 3, POND.y * TILE + 8, 6, 1)
  px(ctx, C.water2, POND.x * TILE + 14 - wave * 3, POND.y * TILE + 20, 6, 1)
  player(ctx, state.player, t)
  if (rainy) {
    ctx.fillStyle = 'rgba(160,200,255,0.55)'
    for (let i = 0; i < 60; i++) {
      const rx = (i * 53 + t / 8) % (COLS * TILE)
      const ry = (i * 97 + t / 3) % (ROWS * TILE)
      ctx.fillRect(Math.floor(rx), Math.floor(ry), 1, 4)
    }
  }
}
