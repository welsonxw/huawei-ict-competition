// "My farm" mode: turns the /api/plots/<id>/farm view of a real plot into a scene the farm renderer can draw.
// Nothing here is simulated by the game: soil, sick plants, rain and clock come from sensors, scans and the forecast.
import { CROPS, FIELD } from './engine.js'

export const FIELD_COLS = FIELD.x1 - FIELD.x0 + 1
export const FIELD_ROWS = FIELD.y1 - FIELD.y0 + 1

export function slotXY(i) {
  return { x: FIELD.x0 + (i % FIELD_COLS), y: FIELD.y0 + Math.floor(i / FIELD_COLS) }
}

export function slotAt(x, y) {
  if (x < FIELD.x0 || x > FIELD.x1 || y < FIELD.y0 || y > FIELD.y1) return null
  return (y - FIELD.y0) * FIELD_COLS + (x - FIELD.x0)
}

export function clockMinutes(hhmm) {
  const [h, m] = (hhmm || '12:00').split(':').map(Number)
  return h * 60 + m
}

// Growth stage is not tracked yet, so every plant is drawn at the same "growing" stage.
export function sceneFromFarm(farm, player) {
  const kind = CROPS[farm.plot.crop] ? farm.plot.crop : 'chilli'
  const age = Math.ceil(CROPS[kind].harvestDay * 0.6)
  const watered = farm.soil === 'moist' || farm.soil === 'wet'
  const tiles = {}
  for (let i = 0; i < farm.plants; i++) {
    const { x, y } = slotXY(i)
    const sick = farm.sick[i]
    tiles[`${x},${y}`] = {
      tilled: true,
      watered,
      crop: { kind, age, disease: sick?.disease ?? null, sickDays: 0, dead: false },
    }
  }
  return { tiles, player, minutes: clockMinutes(farm.local_time) }
}

export function isRaining(farm) {
  return (farm?.rain_mm_next ?? 0) > 0
}

export function tileInfo(farm, x, y) {
  const i = slotAt(x, y)
  if (i === null || i >= farm.plants) return null
  return { index: i, sick: farm.sick[i] ?? null }
}

export function openCommand(farm) {
  return farm.control.commands.find((c) => c.status === 'awaiting_confirmation' || c.status === 'sent') ?? null
}

export function hasActuator(farm, action) {
  return farm.control.actuators.some((a) => a.action === action)
}
