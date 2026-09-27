import { useCallback, useEffect, useState } from 'react'
import { apiDelete, apiGet, apiPatch, apiPost } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { errorText } from '../lib/errors.js'
import {
  LEVEL_STYLE,
  STATUS_STYLE,
  checkKey,
  checkVars,
  daysLabel,
  formatTime,
  isBlocked,
  sortChecks,
  toggleDay,
} from '../monitor/control.js'

const REFRESH_MS = 15000
const ACTIONS = ['water', 'fertilise']
const DAYS = ['0', '1', '2', '3', '4', '5', '6']

export function Checks({ checks }) {
  const { t } = useI18n()
  return (
    <ul className="space-y-1 text-sm">
      {sortChecks(checks).map((c, i) => (
        <li key={`${c.code}-${i}`} className={`rounded px-2 py-1 ${LEVEL_STYLE[c.level]}`}>
          <strong className="mr-1">{t(`ctlLevel_${c.level}`)}</strong>
          {t(checkKey(c), checkVars(c))}
        </li>
      ))}
    </ul>
  )
}

export default function FarmControls({ plotId, onApplied }) {
  const { t, lang } = useI18n()
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [amounts, setAmounts] = useState({ water: '', fertilise: '' })
  const [pending, setPending] = useState(null)
  const [form, setForm] = useState({ action: 'water', amount: '', time_local: '07:00', days: '0123456' })

  const load = useCallback(() => {
    if (!plotId) return
    apiGet(`/api/plots/${plotId}/control`)
      .then((s) => {
        setState(s)
        setError(null)
      })
      .catch(setError)
  }, [plotId])

  useEffect(() => {
    setPending(null)
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [load])

  const run = async (fn) => {
    setBusy(true)
    try {
      return await fn()
    } catch (err) {
      setError(err)
      return null
    } finally {
      setBusy(false)
      load()
    }
  }

  const addActuator = (kind) => run(() => apiPost(`/api/plots/${plotId}/devices`, { kind, simulated: true }))

  const requestCmd = (action) =>
    run(async () => {
      const cmd = await apiPost(`/api/plots/${plotId}/commands`, { action, amount: Number(amounts[action]) })
      setPending(cmd)
    })

  const confirm = () =>
    run(async () => {
      const cmd = await apiPost(`/api/commands/${pending.id}/confirm`)
      setPending(cmd)
      if (cmd.status === 'done') onApplied?.()
    })

  const cancel = () =>
    run(async () => {
      await apiPost(`/api/commands/${pending.id}/cancel`)
      setPending(null)
    })

  const addSchedule = (e) => {
    e.preventDefault()
    run(async () => {
      await apiPost(`/api/plots/${plotId}/schedules`, { ...form, amount: Number(form.amount) })
      setForm((f) => ({ ...f, amount: '' }))
    })
  }

  if (!state) return error ? <p className="text-red-700">{errorText(error, t)}</p> : null

  const { limits, can_control: canControl } = state
  const has = (action) => state.actuators.some((a) => a.action === action)

  return (
    <section className="space-y-4 rounded-xl border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-auto">
          <h3 className="font-bold">{t('ctlTitle')}</h3>
          <p className="text-sm text-stone-600">{t('ctlIntro', { time: state.local_time })}</p>
        </div>
        {canControl && !has('water') && (
          <button
            disabled={busy}
            onClick={() => addActuator('valve')}
            className="min-h-[44px] rounded-lg border border-leaf px-3 font-semibold text-leaf disabled:opacity-50"
          >
            {t('ctlAddValve')}
          </button>
        )}
        {canControl && !has('fertilise') && (
          <button
            disabled={busy}
            onClick={() => addActuator('doser')}
            className="min-h-[44px] rounded-lg border border-leaf px-3 font-semibold text-leaf disabled:opacity-50"
          >
            {t('ctlAddDoser')}
          </button>
        )}
      </div>

      {state.simulated && (
        <p role="note" className="rounded-lg bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-900">
          {t('ctlSimBanner')}
        </p>
      )}
      {!canControl && <p className="rounded-lg bg-stone-100 px-3 py-2 text-sm">{t('ctlViewOnly')}</p>}
      {error && <p className="text-red-700">{errorText(error, t)}</p>}

      {state.actuators.length > 0 && (
        <ul className="flex flex-wrap gap-2 text-sm">
          {state.actuators.map((a) => (
            <li key={a.id} className="flex items-center gap-2 rounded-lg border border-stone-200 px-2 py-1">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                  a.is_simulated ? 'bg-amber-200 text-amber-900' : 'bg-sky-100 text-sky-900'
                }`}
              >
                {t(a.is_simulated ? 'monSimBadge' : 'monRealBadge')}
              </span>
              <strong>{a.name}</strong>
              <span className={a.online ? 'text-emerald-700' : 'text-red-700'}>
                ● {t(a.online ? 'monOnline' : 'monOffline')}
              </span>
            </li>
          ))}
        </ul>
      )}

      {canControl && (
        <div className="grid gap-3 sm:grid-cols-2">
          {ACTIONS.map((action) => {
            const lim = limits[action]
            return (
              <div key={action} className="rounded-lg border border-stone-200 p-3">
                <p className="font-semibold">{t(`ctlAction_${action}`)}</p>
                <p className="text-xs text-stone-600">
                  {t('ctlLimit', { max: lim.max_command, day: lim.max_day, unit: lim.unit })}
                </p>
                {has(action) ? (
                  <div className="mt-2 flex gap-2">
                    <label className="flex-1">
                      <span className="sr-only">{t('ctlAmount', { unit: lim.unit })}</span>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        inputMode="decimal"
                        value={amounts[action]}
                        placeholder={t('ctlAmount', { unit: lim.unit })}
                        onChange={(e) => setAmounts((a) => ({ ...a, [action]: e.target.value }))}
                        className="min-h-[44px] w-full rounded-lg border border-stone-300 px-3"
                      />
                    </label>
                    <button
                      disabled={busy || !amounts[action] || (pending && pending.status === 'awaiting_confirmation')}
                      onClick={() => requestCmd(action)}
                      className="min-h-[44px] rounded-lg bg-leaf px-3 font-semibold text-white disabled:opacity-50"
                    >
                      {t('ctlCheck')}
                    </button>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-stone-600">{t(`ctlNoActuator_${action}`)}</p>
                )}
              </div>
            )
          })}
        </div>
      )}
      {limits.placeholder && (
        <p className="text-xs text-stone-500">
          {t('ctlPlaceholder')} {limits.area_is_default && t('ctlAreaDefault', { area: limits.area_m2 })}
        </p>
      )}

      {pending && (
        <div className="space-y-2 rounded-lg border-2 border-sky-300 bg-sky-50 p-3" aria-live="polite">
          <p className="font-semibold">
            {t(`ctlAction_${pending.action}`)}: {pending.amount} {pending.unit} —{' '}
            <span className={`rounded px-2 py-0.5 text-sm ${STATUS_STYLE[pending.status]}`}>
              {t(`ctlStatus_${pending.status}`)}
            </span>
          </p>
          <Checks checks={pending.checks} />
          {pending.status === 'awaiting_confirmation' && !isBlocked(pending.checks) && (
            <div className="flex gap-2">
              <button
                disabled={busy}
                onClick={confirm}
                className="min-h-[44px] rounded-lg bg-leaf px-4 font-semibold text-white disabled:opacity-50"
              >
                {t(pending.is_simulated ? 'ctlConfirmSim' : 'ctlConfirm')}
              </button>
              <button
                disabled={busy}
                onClick={cancel}
                className="min-h-[44px] rounded-lg border border-stone-300 px-4 font-semibold disabled:opacity-50"
              >
                {t('ctlCancel')}
              </button>
            </div>
          )}
          {pending.status !== 'awaiting_confirmation' && (
            <button onClick={() => setPending(null)} className="text-sm font-semibold text-leaf underline">
              {t('ctlDismiss')}
            </button>
          )}
        </div>
      )}

      <div>
        <h4 className="mb-2 font-semibold">{t('ctlSchedules')}</h4>
        {state.schedules.length === 0 ? (
          <p className="text-sm text-stone-600">{t('ctlNoSchedules')}</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {state.schedules.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-stone-200 px-2 py-1">
                <strong>{s.time_local}</strong>
                <span>
                  {t(`ctlAction_${s.action}`)} {s.amount} {limits[s.action].unit}
                </span>
                <span className="mr-auto text-stone-600">{daysLabel(s.days, t)}</span>
                {canControl && (
                  <>
                    <label className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        onChange={(e) => run(() => apiPatch(`/api/schedules/${s.id}`, { enabled: e.target.checked }))}
                      />
                      {t('ctlEnabled')}
                    </label>
                    <button
                      onClick={() => run(() => apiDelete(`/api/schedules/${s.id}`))}
                      className="min-h-[36px] rounded border border-red-300 px-2 text-red-700"
                    >
                      {t('ctlDelete')}
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
        {canControl && state.actuators.length > 0 && (
          <form onSubmit={addSchedule} className="mt-2 flex flex-wrap items-end gap-2 text-sm">
            <label>
              <span className="block font-semibold">{t('ctlActionLabel')}</span>
              <select
                value={form.action}
                onChange={(e) => setForm({ ...form, action: e.target.value })}
                className="min-h-[40px] rounded-lg border border-stone-300 px-2"
              >
                {ACTIONS.filter(has).map((a) => (
                  <option key={a} value={a}>
                    {t(`ctlAction_${a}`)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="block font-semibold">{t('ctlAmount', { unit: limits[form.action].unit })}</span>
              <input
                type="number"
                min="0"
                step="any"
                required
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                className="min-h-[40px] w-24 rounded-lg border border-stone-300 px-2"
              />
            </label>
            <label>
              <span className="block font-semibold">{t('ctlTime')}</span>
              <input
                type="time"
                required
                value={form.time_local}
                onChange={(e) => setForm({ ...form, time_local: e.target.value })}
                className="min-h-[40px] rounded-lg border border-stone-300 px-2"
              />
            </label>
            <fieldset className="flex flex-wrap gap-1">
              <legend className="font-semibold">{t('ctlDays')}</legend>
              {DAYS.map((d) => (
                <button
                  type="button"
                  key={d}
                  aria-pressed={form.days.includes(d)}
                  onClick={() => setForm({ ...form, days: toggleDay(form.days, d) || form.days })}
                  className={`min-h-[40px] rounded px-2 ${form.days.includes(d) ? 'bg-leaf text-white' : 'border border-stone-300'}`}
                >
                  {t(`ctlDay${d}`)}
                </button>
              ))}
            </fieldset>
            <button
              disabled={busy || !has(form.action)}
              className="min-h-[40px] rounded-lg bg-leaf px-3 font-semibold text-white disabled:opacity-50"
            >
              {t('ctlAddSchedule')}
            </button>
          </form>
        )}
      </div>

      <div>
        <h4 className="mb-2 font-semibold">{t('ctlLog')}</h4>
        {state.commands.length === 0 ? (
          <p className="text-sm text-stone-600">{t('ctlNoLog')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-stone-600">
                <tr>
                  <th className="py-1 pr-2">{t('ctlWhen')}</th>
                  <th className="py-1 pr-2">{t('ctlActionLabel')}</th>
                  <th className="py-1 pr-2">{t('ctlSource')}</th>
                  <th className="py-1 pr-2">{t('ctlStatus')}</th>
                  <th className="py-1">{t('ctlReason')}</th>
                </tr>
              </thead>
              <tbody>
                {state.commands.map((c) => {
                  const reasons = sortChecks(c.checks).filter((x) => x.level !== 'ok')
                  return (
                    <tr key={c.id} className="border-t border-stone-100 align-top">
                      <td className="py-1 pr-2 whitespace-nowrap">{formatTime(c.created_at, lang)}</td>
                      <td className="py-1 pr-2 whitespace-nowrap">
                        {t(`ctlAction_${c.action}`)} {c.amount} {c.unit}
                        {c.is_simulated && <span className="ml-1 text-xs text-amber-800">({t('monSimBadge')})</span>}
                      </td>
                      <td className="py-1 pr-2">{t(`ctlSource_${c.source}`)}</td>
                      <td className="py-1 pr-2">
                        <span className={`rounded px-2 py-0.5 ${STATUS_STYLE[c.status]}`}>{t(`ctlStatus_${c.status}`)}</span>
                      </td>
                      <td className="py-1 text-xs">
                        {reasons.length ? reasons.map((r) => t(checkKey(r), checkVars(r))).join(' · ') : '–'}
                        {c.result?.paras?.error && ` · ${c.result.paras.error}`}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
