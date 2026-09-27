import { useCallback, useEffect, useRef, useState } from 'react'
import { apiGet, apiPost } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { useAuth } from '../auth/AuthContext.jsx'
import { errorText } from '../lib/errors.js'
import { COLS, ROWS, facing, move } from '../game/engine.js'
import { drawFarm, TILE } from '../game/draw.js'
import { hasActuator, isRaining, openCommand, sceneFromFarm, tileInfo } from '../game/myfarm.js'
import { METRICS, formatValue } from '../monitor/format.js'
import { Checks } from './FarmControls.jsx'
import PixelIcon from './PixelIcon.jsx'

const REFRESH_MS = 15000
const MAX_SCALE = 4
const KEYS = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', w: 'up', s: 'down', a: 'left', d: 'right' }
const HUD = ['soil_moisture_pct', 'soil_ec_ds_m', 'air_temp_c', 'air_rh_pct'].map((k) => METRICS.find((m) => m.key === k))
const STATUS_CLS = { low: 'text-[#feae34]', high: 'text-[#feae34]', ok: 'text-[#63c74d]' }

export default function MyFarm() {
  const { t, lang } = useI18n()
  const { user, ready } = useAuth()
  const [plots, setPlots] = useState([])
  const [plotId, setPlotId] = useState('')
  const [farm, setFarm] = useState(null)
  const [outlook, setOutlook] = useState(null)
  const [error, setError] = useState(null)
  const [player, setPlayer] = useState({ x: 1, y: 3, dir: 'down' })
  const [selected, setSelected] = useState(null)
  const [cmdForm, setCmdForm] = useState(null) // {action, amount}
  const [cmd, setCmd] = useState(null)
  const [busy, setBusy] = useState(false)
  const canvas = useRef(null)
  const view = useRef({ x: TILE, y: 3 * TILE })
  const sceneRef = useRef(null)
  const farmRef = useRef(null)
  const playerRef = useRef(player)
  playerRef.current = player
  farmRef.current = farm

  useEffect(() => {
    if (!user) return
    apiGet('/api/plots')
      .then((ps) => {
        setPlots(ps)
        if (ps.length) setPlotId((cur) => cur || String(ps[0].id))
      })
      .catch(setError)
  }, [user])

  const load = useCallback(() => {
    if (!plotId) return
    apiGet(`/api/plots/${plotId}/farm`)
      .then((f) => {
        setFarm(f)
        setError(null)
      })
      .catch(setError)
  }, [plotId])

  useEffect(() => {
    setFarm(null)
    setSelected(null)
    setCmd(null)
    setCmdForm(null)
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    if (!farm) return
    apiGet('/api/game/outlook', { lat: farm.plot.lat, lon: farm.plot.lon, scenario: 'live' })
      .then(setOutlook)
      .catch(() => setOutlook(null))
  }, [farm?.plot.id, farm?.plot.lat, farm?.plot.lon]) // eslint-disable-line react-hooks/exhaustive-deps

  sceneRef.current = farm ? sceneFromFarm(farm, player) : null
  const rainy = isRaining(farm)

  useEffect(() => {
    let id
    const loop = (ts) => {
      const ctx = canvas.current?.getContext('2d')
      if (ctx && sceneRef.current) drawFarm(ctx, sceneRef.current, ts, { rainy, view: view.current })
      id = requestAnimationFrame(loop)
    }
    id = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(id)
  }, [rainy])

  const doMove = useCallback((dir) => setPlayer((p) => move({ player: p }, dir).player), [])
  const doAct = useCallback(() => {
    const f = farmRef.current
    if (!f) return
    const { x, y } = facing(playerRef.current)
    setSelected(tileInfo(f, x, y) ?? { none: true })
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
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [doMove, doAct])

  const run = async (fn) => {
    setBusy(true)
    try {
      await fn()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
      load()
    }
  }

  const request = () =>
    run(async () => {
      const c = await apiPost(`/api/plots/${plotId}/commands`, {
        action: cmdForm.action,
        amount: Number(cmdForm.amount),
        source: 'game',
      })
      setCmd(c)
      setCmdForm(null)
    })
  const confirm = () => run(async () => setCmd(await apiPost(`/api/commands/${cmd.id}/confirm`)))
  const cancel = () =>
    run(async () => {
      await apiPost(`/api/commands/${cmd.id}/cancel`)
      setCmd(null)
    })

  if (!ready) return null
  if (!user) return <p className="sv-parchment p-4">{t('myLogin')}</p>

  const disease = (name) => outlook?.diseases.find((d) => d.crop === farm?.plot.crop && d.disease === name)
  const latest = farm?.sensors.latest ?? {}
  const units = farm?.sensors.units ?? {}
  const open = farm && openCommand(farm)
  const control = farm?.control
  const sickInfo = selected?.sick && disease(selected.sick.disease)

  return (
    <section className="farm-game space-y-3">
      {farm?.sensors.simulated && (
        <p role="note" className="rounded-lg bg-amber-soft px-3 py-2 font-semibold text-amber-warn">
          {t('monSimBanner')}
        </p>
      )}
      {control?.simulated && (
        <p role="note" className="rounded-lg bg-amber-soft px-3 py-2 font-semibold text-amber-warn">
          {t('ctlSimBanner')}
        </p>
      )}
      {farm?.scans_simulated && (
        <p role="note" className="rounded-lg bg-amber-soft px-3 py-2 font-semibold text-amber-warn">
          {t('simulatedBanner')}
        </p>
      )}
      <div className="sv-wood space-y-3 p-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="sv-sign px-3 py-1">
            <h2 className="pixel text-2xl font-bold">{t('gameMode_mine')}</h2>
            <p className="text-sm">{t('myIntro')}</p>
          </div>
          <label className="sv-sign flex flex-col px-2 py-1 text-sm">
            <span className="pixel">{t('choosePlot')}</span>
            <select className="sv-select" value={plotId} onChange={(e) => setPlotId(e.target.value)}>
              {plots.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} – {t(p.crop)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && <p className="sv-parchment p-2 text-[#a22633]">{errorText(error, t)}</p>}
        {plots.length === 0 && !error && <p className="sv-parchment p-2">{t('monNoPlots')}</p>}

        {farm && (
          <>
            <div className="flex flex-wrap items-stretch justify-end gap-2">
              {HUD.map((m) => (
                <div key={m.key} className="sv-parchment pixel px-2 py-1 text-sm leading-tight">
                  <div className="opacity-80">{t(m.label)}</div>
                  <div className={`font-bold ${STATUS_CLS[farm.sensors.status[m.key]] ?? ''}`}>
                    {formatValue(m, latest[m.key]?.value, units[m.key])}
                  </div>
                </div>
              ))}
              <div className="sv-parchment pixel flex items-center gap-2 px-2 py-1 text-sm">
                <PixelIcon name={rainy ? 'rain' : 'sun'} size={28} />
                <div className="leading-tight">
                  <div className="font-bold">{farm.local_time} MYT</div>
                  <div>
                    {farm.rain_mm_next === null
                      ? t('myRainUnknown')
                      : t('myRain', { mm: farm.rain_mm_next, h: farm.rain_hours })}
                  </div>
                </div>
              </div>
            </div>

            <div className="relative mx-auto overflow-x-auto" style={{ maxWidth: COLS * TILE * MAX_SCALE }}>
              <canvas
                ref={canvas}
                width={COLS * TILE}
                height={ROWS * TILE}
                style={{ width: '100%', minWidth: COLS * TILE * 2, aspectRatio: `${COLS} / ${ROWS}`, imageRendering: 'pixelated' }}
                className="sv-canvas block focus:outline-none focus-visible:ring-4 focus-visible:ring-[#fee761]"
                tabIndex={0}
                role="img"
                aria-label={t('myCanvas', {
                  n: farm.plants,
                  sick: farm.sick.length,
                  soil: farm.soil ? t(`mySoil_${farm.soil}`) : t('mySoil_unknown'),
                })}
              />
            </div>

            <div className="sv-parchment flex items-start gap-3 p-2" aria-live="polite">
              <div className="sv-portrait shrink-0">
                <PixelIcon name="farmer" size={48} />
              </div>
              <div className="pixel min-h-[3rem] space-y-1 text-base leading-snug">
                <p>
                  {t(farm.soil ? `mySoil_${farm.soil}` : 'mySoil_unknown')}{' '}
                  {t('myScans', { n: farm.sick.length, total: farm.scans_recent, days: farm.scan_days })}
                </p>
                {selected?.none && <p>{t('myNothing')}</p>}
                {selected && !selected.none && (
                  <p>
                    {selected.sick
                      ? t('myPlantSick', {
                          n: selected.index + 1,
                          name: sickInfo?.name[lang] || selected.sick.disease,
                          date: new Date(selected.sick.created_at).toLocaleDateString(lang === 'ms' ? 'ms-MY' : 'en-MY'),
                        })
                      : t('myPlantOk', { n: selected.index + 1 })}
                    {selected.sick?.expert_checked && ` ${t('myExpertChecked')}`}
                  </p>
                )}
              </div>
            </div>
            {farm.plants_total > farm.plants && (
              <p className="pixel text-xs text-[#ead4aa]">{t('myScaled', { n: farm.plants, total: farm.plants_total })}</p>
            )}

            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap gap-2">
                {['water', 'fertilise'].map((action) => (
                  <button
                    key={action}
                    disabled={!control.can_control || !hasActuator(farm, action) || busy || Boolean(cmd && cmd.status === 'awaiting_confirmation')}
                    onClick={() => setCmdForm({ action, amount: '' })}
                    title={!hasActuator(farm, action) ? t(`ctlNoActuator_${action}`) : undefined}
                    className={`sv-btn pixel px-3 disabled:opacity-50 ${action === 'water' ? 'sv-btn-blue' : 'sv-btn-green'}`}
                  >
                    <PixelIcon name={action === 'water' ? 'water' : farm.plot.crop} size={20} />
                    {t(`ctlAction_${action}`)}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-3 gap-1" aria-label={t('gameControls')}>
                <span />
                <button className="sv-btn sv-pad" onClick={() => doMove('up')} aria-label={t('gameUp')}>▲</button>
                <span />
                <button className="sv-btn sv-pad" onClick={() => doMove('left')} aria-label={t('gameLeft')}>◀</button>
                <button className="sv-btn sv-btn-green sv-pad pixel" onClick={doAct}>{t('myLook')}</button>
                <button className="sv-btn sv-pad" onClick={() => doMove('right')} aria-label={t('gameRight')}>▶</button>
                <span />
                <button className="sv-btn sv-pad" onClick={() => doMove('down')} aria-label={t('gameDown')}>▼</button>
                <span />
              </div>
            </div>
            {!control.can_control && <p className="sv-parchment p-2 text-sm">{t('ctlViewOnly')}</p>}
            {control.actuators.length === 0 && control.can_control && (
              <p className="sv-parchment p-2 text-sm">{t('myNoActuators')}</p>
            )}
            <p className="pixel text-xs text-[#ead4aa]">{t('myKeys')}</p>
          </>
        )}
      </div>

      {farm && cmdForm && (
        <div className="sv-parchment space-y-2 p-4">
          <h3 className="pixel text-lg font-bold">{t(`ctlAction_${cmdForm.action}`)}</h3>
          <p className="text-sm">
            {t('ctlLimit', {
              max: control.limits[cmdForm.action].max_command,
              day: control.limits[cmdForm.action].max_day,
              unit: control.limits[cmdForm.action].unit,
            })}
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              type="number"
              min="0"
              step="any"
              inputMode="decimal"
              autoFocus
              value={cmdForm.amount}
              placeholder={t('ctlAmount', { unit: control.limits[cmdForm.action].unit })}
              onChange={(e) => setCmdForm({ ...cmdForm, amount: e.target.value })}
              className="min-h-[44px] w-40 rounded border border-[#733e39] px-2"
            />
            <button disabled={busy || !cmdForm.amount} onClick={request} className="sv-btn sv-btn-green pixel px-3 disabled:opacity-50">
              {t('ctlCheck')}
            </button>
            <button onClick={() => setCmdForm(null)} className="sv-btn pixel px-3">
              {t('ctlCancel')}
            </button>
          </div>
        </div>
      )}

      {cmd && (
        <div className="sv-parchment space-y-2 p-4" aria-live="polite">
          <p className="pixel font-bold">
            {t(`ctlAction_${cmd.action}`)}: {cmd.amount} {cmd.unit} – {t(`ctlStatus_${cmd.status}`)}
          </p>
          <Checks checks={cmd.checks} />
          {cmd.status === 'awaiting_confirmation' && !cmd.checks.some((c) => c.level === 'block') ? (
            <div className="flex gap-2">
              <button disabled={busy} onClick={confirm} className="sv-btn sv-btn-green pixel px-3">
                {t(cmd.is_simulated ? 'ctlConfirmSim' : 'ctlConfirm')}
              </button>
              <button disabled={busy} onClick={cancel} className="sv-btn pixel px-3">
                {t('ctlCancel')}
              </button>
            </div>
          ) : (
            <button onClick={() => setCmd(null)} className="sv-btn pixel px-3">
              {t('ctlDismiss')}
            </button>
          )}
        </div>
      )}
      {!cmd && open && (
        <p className="sv-parchment p-2 text-sm">
          {t('myOpen', { action: t(`ctlAction_${open.action}`), status: t(`ctlStatus_${open.status}`) })}
        </p>
      )}

      {sickInfo && (
        <div className="sv-parchment space-y-2 p-4">
          <h3 className="pixel text-xl font-bold text-[#a22633]">{sickInfo.name[lang]}</h3>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {sickInfo.plan[lang].map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        </div>
      )}

      {farm && control.commands.length > 0 && (
        <div className="sv-parchment p-3 text-sm">
          <h3 className="pixel text-lg font-bold">{t('ctlLog')}</h3>
          <ul className="space-y-1">
            {control.commands.slice(0, 5).map((c) => (
              <li key={c.id}>
                {c.created_at && new Date(c.created_at).toLocaleTimeString(lang === 'ms' ? 'ms-MY' : 'en-MY', { timeZone: 'Asia/Kuala_Lumpur', hour: '2-digit', minute: '2-digit' })}{' '}
                · {t(`ctlAction_${c.action}`)} {c.amount} {c.unit} · {t(`ctlSource_${c.source}`)} · {t(`ctlStatus_${c.status}`)}
                {c.is_simulated && ` (${t('monSimBadge')})`}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs opacity-80">{t('myLogNote')}</p>
        </div>
      )}
    </section>
  )
}
