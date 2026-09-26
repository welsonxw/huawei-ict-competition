import { useCallback, useEffect, useRef, useState } from 'react'
import { apiGet } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import {
  act,
  buySeed,
  COLS,
  CROPS,
  horizonFor,
  isRainyDay,
  move,
  newGame,
  ROWS,
  sleep,
  tileAt,
  treat,
  TREAT_COST,
} from '../game/engine.js'
import { drawFarm, TILE } from '../game/draw.js'

const SAVE_KEY = 'taniguard-farm-v1'
const SCALE = 3
const FARMS = [
  { id: 'johor', lat: 1.8548, lon: 103.3345 },
  { id: 'cameron', lat: 4.5, lon: 101.42 },
  { id: 'kelantan', lat: 6.05, lon: 102.2 },
]
const TREATMENTS = ['spray_timing', 'vector_control', 'hygiene']
const KEYS = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  w: 'up',
  s: 'down',
  a: 'left',
  d: 'right',
}
const BAND_CLS = {
  low: 'bg-leaf-light text-leaf-dark',
  medium: 'bg-amber-soft text-amber-warn',
  high: 'bg-red-100 text-red-800',
  unknown: 'bg-stone-100',
}

function load() {
  try {
    return JSON.parse(localStorage.getItem(SAVE_KEY)) || null
  } catch {
    return null
  }
}

export default function FarmGame() {
  const { t, lang } = useI18n()
  const [saved] = useState(load)
  const [game, setGame] = useState(() => saved?.game || newGame())
  const [farmId, setFarmId] = useState(saved?.farmId || 'johor')
  const [scenario, setScenario] = useState(saved?.scenario || 'demo')
  const [seed, setSeed] = useState('chilli')
  const [outlook, setOutlook] = useState(null)
  const [offline, setOffline] = useState(false)
  const [message, setMessage] = useState(() => t('gameWelcome'))
  const [sick, setSick] = useState(null) // {x, y}
  const canvas = useRef(null)
  const gameRef = useRef(game)
  gameRef.current = game

  const farm = FARMS.find((f) => f.id === farmId)
  const rainy = isRainyDay(game.day, outlook?.weather)

  useEffect(() => {
    localStorage.setItem(SAVE_KEY, JSON.stringify({ game, farmId, scenario }))
  }, [game, farmId, scenario])

  useEffect(() => {
    setOutlook(null)
    apiGet('/api/game/outlook', { lat: farm.lat, lon: farm.lon, scenario })
      .then((o) => {
        setOutlook(o)
        setOffline(false)
      })
      .catch(() => setOffline(true))
  }, [farm.lat, farm.lon, scenario])

  useEffect(() => {
    let id
    const loop = (ts) => {
      const ctx = canvas.current?.getContext('2d')
      if (ctx) drawFarm(ctx, gameRef.current, ts, rainy)
      id = requestAnimationFrame(loop)
    }
    id = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(id)
  }, [rainy])

  const disease = useCallback(
    (crop, name) => outlook?.diseases.find((d) => d.crop === crop && d.disease === name),
    [outlook],
  )

  const doSleep = useCallback(() => {
    setSick(null)
    setGame((g) => {
      const next = sleep(g, outlook)
      const ev = next.log[0].events
      const infected = ev.filter((e) => e.type === 'infected').length
      const died = ev.filter((e) => e.type === 'died').length
      setMessage(
        [
          t('gameMorning', { day: next.day }),
          next.log[0].rainy && t('gameRained'),
          infected && t('gameInfected', { n: infected }),
          died && t('gameDied', { n: died }),
        ]
          .filter(Boolean)
          .join(' '),
      )
      return next
    })
  }, [outlook, t])

  const doAct = useCallback(() => {
    const r = act(gameRef.current, seed)
    if (r.event === 'door') return doSleep()
    if (r.event === 'sick') {
      const c = tileAt(r.state, r.tile.x, r.tile.y).crop
      setSick(r.tile)
      setMessage(
        t('gameScanned', {
          name: disease(c.kind, c.disease)?.name[lang] || c.disease,
        }),
      )
      return
    }
    setGame(r.state)
    setMessage(t(`gameEv_${r.event}`, { crop: t(seed), coins: CROPS[seed].value }))
  }, [seed, doSleep, disease, lang, t])

  const doMove = useCallback((dir) => {
    setSick(null)
    setGame((g) => move(g, dir))
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest?.('input, select, textarea, button')) return
      const dir = KEYS[e.key]
      if (dir) {
        e.preventDefault()
        doMove(dir)
      } else if (e.key === ' ' || e.key === 'e' || e.key === 'Enter') {
        e.preventDefault()
        doAct()
      } else if (e.key === '1') setSeed('chilli')
      else if (e.key === '2') setSeed('tomato')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [doMove, doAct])

  const applyTreatment = (adviceType) => {
    const r = treat(game, sick.x, sick.y, adviceType, outlook?.diseases || [])
    setGame(r.state)
    setMessage(r.ok ? t('gameCured') : game.coins < TREAT_COST ? t('gameNoCoins') : t('gameWrong'))
    if (r.ok) setSick(null)
  }

  const reset = () => {
    setGame(newGame())
    setSick(null)
    setMessage(t('gameWelcome'))
  }

  const h = String(horizonFor(game.day, outlook?.horizons))
  const sickCrop = sick && tileAt(game, sick.x, sick.y).crop
  const sickInfo = sickCrop && disease(sickCrop.kind, sickCrop.disease)
  const top = (outlook?.diseases || [])
    .filter((d) => d.bands[h] !== 'low')
    .sort((a, b) => ['high', 'medium'].indexOf(a.bands[h]) - ['high', 'medium'].indexOf(b.bands[h]))

  return (
    <section className="space-y-3">
      {outlook?.simulated && (
        <p role="status" className="rounded-lg bg-amber-soft px-3 py-2 font-semibold text-amber-warn">
          {t('simulatedBanner')}
        </p>
      )}
      <div className="card space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold">{t('tabGame')}</h2>
            <p className="text-sm text-stone-600">{t('gameIntro')}</p>
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            <label className="flex flex-col">
              {t('gameFarm')}
              <select className="rounded border p-1" value={farmId} onChange={(e) => setFarmId(e.target.value)}>
                {FARMS.map((f) => (
                  <option key={f.id} value={f.id}>
                    {t(`gameFarm_${f.id}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col">
              {t('gameData')}
              <select className="rounded border p-1" value={scenario} onChange={(e) => setScenario(e.target.value)}>
                <option value="demo">{t('gameDataDemo')}</option>
                <option value="live">{t('gameDataLive')}</option>
              </select>
            </label>
          </div>
        </div>

        <div className="flex flex-wrap gap-4 text-sm font-semibold">
          <span>{t('gameDay', { day: game.day })}</span>
          <span>{t('gameForecastDay', { h })}</span>
          <span>🪙 {game.coins}</span>
          <span>💧 {game.water}/10</span>
          <span>{rainy ? t('gameRainy') : t('gameDry')}</span>
          {offline && <span className="text-amber-warn">{t('gameOffline')}</span>}
        </div>

        <div className="overflow-x-auto">
          <canvas
            ref={canvas}
            width={COLS * TILE}
            height={ROWS * TILE}
            style={{
              width: COLS * TILE * SCALE,
              height: ROWS * TILE * SCALE,
              imageRendering: 'pixelated',
            }}
            className="max-w-none rounded-lg border-4 border-leaf-dark"
            role="img"
            aria-label={t('gameCanvas')}
          />
        </div>

        <p aria-live="polite" className="min-h-[1.5rem] rounded bg-stone-50 px-2 py-1 text-sm">
          {message}
        </p>

        <div className="flex flex-wrap items-center gap-4">
          <div className="grid grid-cols-3 gap-1" aria-label={t('gameControls')}>
            <span />
            <button className="btn-pad" onClick={() => doMove('up')} aria-label={t('gameUp')}>
              ▲
            </button>
            <span />
            <button className="btn-pad" onClick={() => doMove('left')} aria-label={t('gameLeft')}>
              ◀
            </button>
            <button className="btn-pad bg-leaf text-white" onClick={doAct}>
              {t('gameAct')}
            </button>
            <button className="btn-pad" onClick={() => doMove('right')} aria-label={t('gameRight')}>
              ▶
            </button>
            <span />
            <button className="btn-pad" onClick={() => doMove('down')} aria-label={t('gameDown')}>
              ▼
            </button>
            <span />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex flex-wrap gap-2">
              {Object.keys(CROPS).map((k) => (
                <button
                  key={k}
                  onClick={() => setSeed(k)}
                  className={`min-h-[40px] rounded-lg border-2 px-3 ${seed === k ? 'border-leaf bg-leaf-light' : 'border-stone-300'}`}
                >
                  {t(k)} ×{game.seeds[k]}
                </button>
              ))}
              {Object.keys(CROPS).map((k) => (
                <button
                  key={`buy-${k}`}
                  onClick={() => setGame(buySeed(game, k))}
                  className="min-h-[40px] rounded-lg border px-3"
                >
                  {t('gameBuy', { crop: t(k), cost: CROPS[k].seedCost })}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={doSleep} className="min-h-[40px] rounded-lg bg-leaf-dark px-3 text-white">
                {t('gameSleep')}
              </button>
              <button onClick={reset} className="min-h-[40px] rounded-lg border px-3">
                {t('gameReset')}
              </button>
            </div>
            <p className="text-xs text-stone-500">{t('gameKeys')}</p>
          </div>
        </div>
      </div>

      {sickCrop && (
        <div className="card space-y-2 border-amber-warn">
          <h3 className="font-bold">
            {t('gameScanTitle', {
              name: sickInfo?.name[lang] || sickCrop.disease,
            })}
          </h3>
          <p className="text-sm">{t('gameScanBody', { days: sickCrop.sickDays })}</p>
          {sickInfo && (
            <ol className="list-decimal space-y-1 pl-5 text-sm">
              {sickInfo.plan[lang].map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          )}
          <p className="text-sm font-semibold">{t('gameChoose', { cost: TREAT_COST })}</p>
          <div className="flex flex-wrap gap-2">
            {TREATMENTS.map((a) => (
              <button
                key={a}
                onClick={() => applyTreatment(a)}
                className="min-h-[44px] rounded-lg border-2 border-leaf px-3 text-sm"
              >
                {t(`gameTreat_${a}`)}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="card">
          <h3 className="font-bold">{t('gameRiskTitle', { h })}</h3>
          {!outlook && !offline && <p className="text-sm">{t('gameLoading')}</p>}
          {outlook && top.length === 0 && <p className="text-sm">{t('gameRiskNone')}</p>}
          <ul className="mt-1 space-y-1 text-sm">
            {top.map((d) => (
              <li key={`${d.crop}-${d.disease}`} className="flex justify-between gap-2">
                <span>
                  {t(d.crop)} – {d.name[lang]}
                </span>
                <span className={`rounded px-2 font-semibold ${BAND_CLS[d.bands[h]]}`}>{t(`risk_${d.bands[h]}`)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-stone-500">{t('gameRiskSource')}</p>
        </div>
        <div className="card text-sm">
          <h3 className="font-bold">{t('gameStats')}</h3>
          <p>
            {t('gameHarvested', { n: game.stats.harvested })} · {t('gameTreated', { n: game.stats.treated })} ·{' '}
            {t('gameLost', { n: game.stats.lost })}
          </p>
          <p className="mt-2 text-xs text-stone-500">{t('gameRulesNote')}</p>
        </div>
      </div>
    </section>
  )
}
