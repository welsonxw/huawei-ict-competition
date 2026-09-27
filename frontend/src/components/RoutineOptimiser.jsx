import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { errorText } from '../lib/errors.js'
import { applyMode, reasonKey, reasonVars, scoreDelta } from '../monitor/optimizer.js'
import { Checks } from './FarmControls.jsx'

function when(c, t) {
  if (c.kind === 'skip') return t('optSkip')
  return c.in_hours === 0 ? t('optNow', { time: c.time_local }) : t('optAt', { time: c.time_local, h: c.in_hours })
}

export default function RoutineOptimiser({ plotId, onApplied }) {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [cmd, setCmd] = useState(null)
  const [saved, setSaved] = useState(false)

  const load = useCallback(() => {
    if (!plotId) return
    apiGet(`/api/plots/${plotId}/optimise`)
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch(setError)
  }, [plotId])

  useEffect(() => {
    setCmd(null)
    setSaved(false)
    load()
  }, [load])

  const run = async (fn) => {
    setBusy(true)
    try {
      await fn()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const best = data?.best
  const mode = applyMode(best)
  const requestNow = () =>
    run(async () => {
      setCmd(await apiPost(`/api/plots/${plotId}/commands`, { action: 'water', amount: best.litres, source: 'optimizer' }))
    })
  const confirm = () =>
    run(async () => {
      const c = await apiPost(`/api/commands/${cmd.id}/confirm`)
      setCmd(c)
      onApplied?.()
      load()
    })
  const saveSchedule = () =>
    run(async () => {
      await apiPost(`/api/plots/${plotId}/schedules`, {
        action: 'water',
        amount: best.litres,
        time_local: best.time_local,
        days: '0123456',
      })
      setSaved(true)
      onApplied?.()
      load()
    })

  if (!data) return error ? <p className="text-red-700">{errorText(error, t)}</p> : null
  const fert = data.fertilise

  return (
    <section className="space-y-3 rounded-xl border border-stone-200 bg-white p-4" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-auto">
          <h3 className="font-bold">{t('optTitle')}</h3>
          <p className="text-sm text-stone-600">{t('optIntro', { h: data.horizon_hours })}</p>
        </div>
        <button onClick={load} className="min-h-[44px] rounded-lg border border-leaf px-3 font-semibold text-leaf">
          {t('optRefresh')}
        </button>
      </div>
      <p role="note" className="rounded-lg bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-900">
        {t('optEstimate')}
        {data.simulated_input && ` ${t('optSimInput')}`}
      </p>
      {!data.forecast && <p className="rounded-lg bg-stone-100 px-3 py-2 text-sm">{t('optNoForecast')}</p>}
      {error && <p className="text-red-700">{errorText(error, t)}</p>}

      {data.status === 'no_valve' && <p className="rounded-lg bg-stone-100 px-3 py-2">{t('optNoValve')}</p>}
      {data.status === 'no_moisture' && <p className="rounded-lg bg-stone-100 px-3 py-2">{t('optNoMoisture')}</p>}

      {data.status === 'ok' && (
        <>
          <div className="rounded-lg bg-emerald-50 p-3">
            <p className="text-lg font-bold text-emerald-900">
              {t('optWater')}:{' '}
              {best.kind === 'skip' ? t('optSkip') : `${best.litres} L · ${when(best, t)}`}
            </p>
            <ul className="mt-1 list-disc pl-5 text-sm">
              {data.reasons.map((r) => (
                <li key={r.code}>{t(reasonKey(r), reasonVars(r))}</li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-stone-600">
              {t('optConsidered', { n: data.considered, x: data.excluded, m: data.moisture_pct })}
            </p>
          </div>
          {data.can_control && mode === 'now' && !cmd && (
            <button disabled={busy} onClick={requestNow} className="min-h-[44px] rounded-lg bg-leaf px-4 font-semibold text-white disabled:opacity-50">
              {t('optRequestNow')}
            </button>
          )}
          {data.can_control && mode === 'schedule' && !saved && (
            <button disabled={busy} onClick={saveSchedule} className="min-h-[44px] rounded-lg bg-leaf px-4 font-semibold text-white disabled:opacity-50">
              {t('optSaveSchedule', { time: best.time_local, amount: best.litres })}
            </button>
          )}
          {saved && <p className="text-sm text-emerald-800">{t('optSaved')}</p>}
          {cmd && (
            <div className="space-y-2 rounded-lg border border-stone-200 p-3">
              <p className="font-semibold">{t(`ctlStatus_${cmd.status}`)}</p>
              <Checks checks={cmd.checks} />
              {cmd.status === 'awaiting_confirmation' && !cmd.checks.some((c) => c.level === 'block') && (
                <button disabled={busy} onClick={confirm} className="min-h-[44px] rounded-lg bg-leaf px-4 font-semibold text-white">
                  {t(cmd.is_simulated ? 'ctlConfirmSim' : 'ctlConfirm')}
                </button>
              )}
            </div>
          )}

          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-stone-600">
                <th className="py-1">{t('optColWhen')}</th>
                <th>{t('optColAmount')}</th>
                <th>{t('optColDry')}</th>
                <th>{t('optColLeafWet')}</th>
                <th>{t('optColScore')}</th>
              </tr>
            </thead>
            <tbody>
              {[...data.ranked, ...data.schedules.map((s) => ({ ...s, mine: true }))].map((c, i) => (
                <tr key={`${c.kind}-${c.at}-${c.litres}-${i}`} className={`border-t border-stone-100 ${i === 0 ? 'font-semibold' : ''}`}>
                  <td className="py-1">
                    {when(c, t)}
                    {c.mine && ` (${t('optYourSchedule')})`}
                    {c.blocked.length > 0 && ` – ${c.blocked.map((b) => t(`optBlocked_${b}`)).join(', ')}`}
                  </td>
                  <td>{c.litres} L</td>
                  <td>{c.hours_dry} h</td>
                  <td>{c.added_leaf_wet_hours} h</td>
                  <td>{i === 0 ? c.score : `+${scoreDelta(c, best)}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <div className="rounded-lg bg-stone-50 p-3 text-sm">
        <p className="font-semibold">
          {t('optFert')}:{' '}
          {fert.status === 'ok'
            ? t('optFertAt', { date: fert.date_local, time: fert.time_local, h: fert.in_hours })
            : t(`optFert_${fert.status}`, { ec: fert.ec ?? '', limit: fert.limit ?? '', earliest: fert.earliest ?? '–', h: fert.hours ?? '' })}
        </p>
        {(fert.reasons ?? []).map((r, i) => (
          <p key={`${r.code}-${i}`}>{t(reasonKey(r), reasonVars(r))}</p>
        ))}
        {fert.status === 'ok' && (
          <p className="text-xs text-stone-600">
            {fert.last_amount ? t('optFertLast', { amount: fert.last_amount, unit: fert.unit }) : t('optFertNoRate')}
          </p>
        )}
      </div>
      <p className="text-xs text-stone-500">{t('optPlaceholder')}</p>
    </section>
  )
}
