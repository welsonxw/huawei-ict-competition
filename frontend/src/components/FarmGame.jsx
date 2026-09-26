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
import { drawFarm, drawIcon, TILE } from '../game/draw.js'
import '@fontsource/pixelify-sans/400.css'
import '@fontsource/pixelify-sans/700.css'

const SAVE_KEY = 'taniguard-farm-v1'
const MAX_SCALE = 4
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
  low: 'bg-[#63c74d] text-[#193c3e]',
  medium: 'bg-[#feae34] text-[#3e2731]',
  high: 'bg-[#e43b44] text-white',
  unknown: 'bg-[#c0cbdc] text-[#3e2731]',
}

function PixelIcon({ name, size = 32, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    const ctx = ref.current?.getContext('2d')
    if (ctx) drawIcon(ctx, name)
  }, [name])
  return (
    <canvas
      ref={ref}
      width={16}
      height={16}
      aria-hidden="true"
      className={className}
      style={{ width: size, height: size, imageRendering: 'pixelated' }}
    />
  )
}

const clock = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`

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
  const [message, setMessage] = useState([{ key: 'gameWelcome' }])
  const [sick, setSick] = useState(null) // {x, y}
  const canvas = useRef(null)
  const view = useRef({ x: game.player.x * TILE, y: game.player.y * TILE })
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
    canvas.current?.focus({ preventScroll: true })
  }, [])

  useEffect(() => {
    let id
    const loop = (ts) => {
      const ctx = canvas.current?.getContext('2d')
      if (ctx) drawFarm(ctx, gameRef.current, ts, { rainy, view: view.current })
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
          { key: 'gameMorning', vars: { day: next.day } },
          next.log[0].rainy && { key: 'gameRained' },
          infected && { key: 'gameInfected', vars: { n: infected } },
          died && { key: 'gameDied', vars: { n: died } },
        ].filter(Boolean),
      )
      return next
    })
  }, [outlook])

  const doAct = useCallback(() => {
    const r = act(gameRef.current, seed)
    if (r.event === 'door') return doSleep()
    if (r.event === 'sick') {
      const c = tileAt(r.state, r.tile.x, r.tile.y).crop
      setSick(r.tile)
      setMessage([{ key: 'gameScanned', crop: c.kind, disease: c.disease }])
      return
    }
    const crop = r.crop || seed
    setGame(r.state)
    setMessage([{ key: `gameEv_${r.event}`, crop, vars: { coins: CROPS[crop].value } }])
  }, [seed, doSleep])

  const doMove = useCallback((dir) => {
    setSick(null)
    setGame((g) => move(g, dir))
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest?.('input, select, textarea')) return
      const dir = KEYS[e.key]
      if (!dir && e.target.closest?.('button')) return
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
    setMessage([{ key: r.ok ? 'gameCured' : game.coins < TREAT_COST ? 'gameNoCoins' : 'gameWrong' }])
    if (r.ok) setSick(null)
  }

  const reset = () => {
    setGame(newGame())
    setSick(null)
    setMessage([{ key: 'gameWelcome' }])
  }

  const h = String(horizonFor(game.day, outlook?.horizons))
  const sickCrop = sick && tileAt(game, sick.x, sick.y).crop
  const sickInfo = sickCrop && disease(sickCrop.kind, sickCrop.disease)
  const top = (outlook?.diseases || [])
    .filter((d) => d.bands[h] !== 'low')
    .sort((a, b) => ['high', 'medium'].indexOf(a.bands[h]) - ['high', 'medium'].indexOf(b.bands[h]))

  const minutes = game.minutes ?? 360
  const night = minutes >= 19 * 60
  const text = message
    .map((m) =>
      t(m.key, {
        ...m.vars,
        crop: m.crop && t(m.crop),
        name: m.disease && (disease(m.crop, m.disease)?.name[lang] || m.disease),
      }),
    )
    .join(' ')

  return (
    <section className="farm-game space-y-3">
      {outlook?.simulated && (
        <p role="status" className="rounded-lg bg-amber-soft px-3 py-2 font-semibold text-amber-warn">
          {t('simulatedBanner')}
        </p>
      )}
      <div className="sv-wood space-y-3 p-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="sv-sign px-3 py-1">
            <h2 className="pixel text-2xl font-bold">{t('tabGame')}</h2>
            <p className="text-sm">{t('gameIntro')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="sv-sign flex flex-col px-2 py-1 text-sm">
              <span className="pixel">{t('gameFarm')}</span>
              <select className="sv-select" value={farmId} onChange={(e) => setFarmId(e.target.value)}>
                {FARMS.map((f) => (
                  <option key={f.id} value={f.id}>
                    {t(`gameFarm_${f.id}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="sv-sign flex flex-col px-2 py-1 text-sm">
              <span className="pixel">{t('gameData')}</span>
              <select className="sv-select" value={scenario} onChange={(e) => setScenario(e.target.value)}>
                <option value="demo">{t('gameDataDemo')}</option>
                <option value="live">{t('gameDataLive')}</option>
              </select>
            </label>
          </div>
        </div>

        <div className="flex items-stretch justify-end gap-2">
          <div className="sv-parchment pixel flex items-center gap-2 px-2 py-1 text-sm sm:text-base">
            <PixelIcon name={rainy ? 'rain' : night ? 'moon' : 'sun'} size={28} />
            <div className="leading-tight">
              <div className="font-bold">{t('gameDay', { day: game.day })}</div>
              <div>{clock(minutes)}</div>
            </div>
          </div>
          <div className="sv-parchment pixel flex items-center gap-1 px-3 text-sm sm:text-base">
            <PixelIcon name="coin" size={20} />
            <span className="font-bold tabular-nums">{game.coins}</span>
          </div>
        </div>
        <div className="relative mx-auto overflow-x-auto" style={{ maxWidth: COLS * TILE * MAX_SCALE }}>
          <canvas
            ref={canvas}
            width={COLS * TILE}
            height={ROWS * TILE}
            style={{
              width: '100%',
              minWidth: COLS * TILE * 2,
              aspectRatio: `${COLS} / ${ROWS}`,
              imageRendering: 'pixelated',
            }}
            className="sv-canvas block focus:outline-none focus-visible:ring-4 focus-visible:ring-[#fee761]"
            tabIndex={0}
            role="img"
            aria-label={t('gameCanvas')}
          />
        </div>

        <div className="sv-parchment flex items-start gap-3 p-2" aria-live="polite">
          <div className="sv-portrait shrink-0">
            <PixelIcon name="farmer" size={48} />
          </div>
          <p className="pixel min-h-[3rem] text-base leading-snug sm:text-lg">{text}</p>
        </div>

        <div className="pixel flex flex-wrap gap-x-4 gap-y-1 text-sm text-[#ead4aa]">
          <span>{t('gameForecastDay', { h })}</span>
          <span>{rainy ? t('gameRainy') : t('gameDry')}</span>
          {offline && <span className="text-[#feae34]">{t('gameOffline')}</span>}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="sv-hotbar flex gap-1 p-1" aria-label={t('gameHotbar')}>
            {Object.keys(CROPS).map((k, i) => (
              <button
                key={k}
                onClick={() => setSeed(k)}
                aria-pressed={seed === k}
                title={t(k)}
                className={`sv-slot ${seed === k ? 'sv-slot-on' : ''}`}
              >
                <PixelIcon name={k} size={32} />
                <span className="sv-slot-key">{i + 1}</span>
                <span className="sv-slot-count">{game.seeds[k]}</span>
                <span className="sr-only">{t(k)}</span>
              </button>
            ))}
            <div className="sv-slot" title={t('gameWater')}>
              <PixelIcon name="water" size={32} />
              <span className="sv-water-bar">
                <span style={{ width: `${game.water * 10}%` }} />
              </span>
              <span className="sr-only">
                {t('gameWater')} {game.water}/10
              </span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-1" aria-label={t('gameControls')}>
            <span />
            <button className="sv-btn sv-pad" onClick={() => doMove('up')} aria-label={t('gameUp')}>
              ▲
            </button>
            <span />
            <button className="sv-btn sv-pad" onClick={() => doMove('left')} aria-label={t('gameLeft')}>
              ◀
            </button>
            <button className="sv-btn sv-btn-green sv-pad pixel" onClick={doAct}>
              {t('gameAct')}
            </button>
            <button className="sv-btn sv-pad" onClick={() => doMove('right')} aria-label={t('gameRight')}>
              ▶
            </button>
            <span />
            <button className="sv-btn sv-pad" onClick={() => doMove('down')} aria-label={t('gameDown')}>
              ▼
            </button>
            <span />
          </div>

          <div className="flex flex-col gap-2">
            <div className="sv-parchment p-2">
              <p className="pixel mb-1 font-bold">{t('gameShop')}</p>
              <div className="flex flex-wrap gap-2">
                {Object.keys(CROPS).map((k) => (
                  <button
                    key={`buy-${k}`}
                    onClick={() => setGame(buySeed(game, k))}
                    className="sv-btn pixel px-2 text-sm"
                  >
                    <PixelIcon name={k} size={20} />
                    {t('gameBuy', { crop: t(k), cost: CROPS[k].seedCost })}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={doSleep} className="sv-btn sv-btn-blue pixel px-3">
                <PixelIcon name="moon" size={20} />
                {t('gameSleep')}
              </button>
              <button onClick={reset} className="sv-btn pixel px-3">
                {t('gameReset')}
              </button>
            </div>
          </div>
        </div>
        <p className="pixel text-xs text-[#ead4aa]">{t('gameKeys')}</p>
      </div>

      {sickCrop && (
        <div className="sv-parchment space-y-2 p-4">
          <h3 className="pixel text-xl font-bold text-[#a22633]">
            {t('gameScanTitle', { name: sickInfo?.name[lang] || sickCrop.disease })}
          </h3>
          <p className="text-sm">{t('gameScanBody', { days: sickCrop.sickDays })}</p>
          {sickInfo && (
            <ol className="list-decimal space-y-1 pl-5 text-sm">
              {sickInfo.plan[lang].map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          )}
          <p className="pixel font-bold">{t('gameChoose', { cost: TREAT_COST })}</p>
          <div className="flex flex-wrap gap-2">
            {TREATMENTS.map((a) => (
              <button key={a} onClick={() => applyTreatment(a)} className="sv-btn px-3 text-sm">
                {t(`gameTreat_${a}`)}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="sv-parchment p-3">
          <h3 className="pixel text-lg font-bold">{t('gameRiskTitle', { h })}</h3>
          {!outlook && !offline && <p className="text-sm">{t('gameLoading')}</p>}
          {outlook && top.length === 0 && <p className="text-sm">{t('gameRiskNone')}</p>}
          <ul className="mt-1 space-y-1 text-sm">
            {top.map((d) => (
              <li key={`${d.crop}-${d.disease}`} className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1">
                  <PixelIcon name={d.crop} size={20} />
                  {t(d.crop)} – {d.name[lang]}
                </span>
                <span className={`pixel px-2 font-bold ${BAND_CLS[d.bands[h]]}`}>{t(`risk_${d.bands[h]}`)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs opacity-80">{t('gameRiskSource')}</p>
        </div>
        <div className="sv-parchment p-3 text-sm">
          <h3 className="pixel text-lg font-bold">{t('gameStats')}</h3>
          <p className="pixel text-base">
            {t('gameHarvested', { n: game.stats.harvested })} · {t('gameTreated', { n: game.stats.treated })} ·{' '}
            {t('gameLost', { n: game.stats.lost })}
          </p>
          <p className="mt-2 text-xs opacity-80">{t('gameRulesNote')}</p>
        </div>
      </div>
    </section>
  )
}
