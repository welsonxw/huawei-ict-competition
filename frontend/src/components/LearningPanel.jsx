import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { errorText } from '../lib/errors.js'

const pct = (v) => (v === null || v === undefined ? '–' : `${Math.round(v * 100)}%`)
const today = () => new Date().toISOString().slice(0, 10)

export default function LearningPanel({ plotId }) {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [harvests, setHarvests] = useState([])
  const [error, setError] = useState(null)
  const [form, setForm] = useState({ kg: '', harvested_on: today() })
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!plotId) return
    Promise.all([apiGet(`/api/plots/${plotId}/learning`), apiGet(`/api/plots/${plotId}/harvests`)])
      .then(([l, h]) => {
        setData(l)
        setHarvests(h.harvests)
        setError(null)
      })
      .catch(setError)
  }, [plotId])

  useEffect(() => {
    load()
  }, [load])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await apiPost(`/api/plots/${plotId}/harvests`, { kg: Number(form.kg), harvested_on: form.harvested_on })
      setForm({ kg: '', harvested_on: today() })
      load()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  if (!data) return error ? <p className="text-red-700">{errorText(error, t)}</p> : null

  return (
    <section className="space-y-3 rounded-xl border border-stone-200 bg-white p-4">
      <div>
        <h3 className="font-bold">{t('lrnTitle')}</h3>
        <p className="text-sm text-stone-600">
          {t('lrnIntro', { crop: t(data.crop), days: data.window_days, n: data.outcome_days })}
        </p>
      </div>
      {data.simulated && (
        <p role="note" className="rounded-lg bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-900">
          {t('lrnSimulated')}
        </p>
      )}
      <p className={`rounded-lg px-3 py-2 text-sm ${data.status === 'learned' ? 'bg-emerald-50' : 'bg-stone-100'}`}>
        {data.status === 'learned'
          ? t('lrnLearned')
          : t('lrnLearning', { d: data.min_days, s: data.min_scans, here: data.days_logged_here })}
      </p>
      {error && <p className="text-red-700">{errorText(error, t)}</p>}

      {data.timings.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-stone-600">
              <th className="py-1">{t('lrnColTiming')}</th>
              <th>{t('lrnColDays')}</th>
              <th>{t('lrnColScans')}</th>
              <th>{t('lrnColSick')}</th>
              <th>{t('lrnColPlots')}</th>
              <th>{t('lrnColEffect')}</th>
            </tr>
          </thead>
          <tbody>
            {data.timings.map((r) => (
              <tr key={r.timing} className="border-t border-stone-100">
                <td className="py-1">{t(`lrnTiming_${r.timing}`)}</td>
                <td>{r.days}</td>
                <td>{r.scans}</td>
                <td>{pct(r.sick_rate)}</td>
                <td>{r.plots}</td>
                <td>
                  {r.timing in data.adjustments
                    ? `${data.adjustments[r.timing] > 0 ? '+' : ''}${data.adjustments[r.timing]}`
                    : t('lrnNotEnough')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="text-xs text-stone-500">{t('lrnPooled', { rate: pct(data.pooled_sick_rate), plots: data.plots })}</p>

      <div className="space-y-2 rounded-lg bg-stone-50 p-3 text-sm">
        <h4 className="font-semibold">{t('lrnHarvest')}</h4>
        {data.harvest.simulated && <p className="font-semibold text-amber-900">{t('lrnSimulated')}</p>}
        {data.harvest.timings.length === 0 ? (
          <p>{t('lrnHarvestNone', { days: data.harvest.season_days })}</p>
        ) : (
          <ul>
            {data.harvest.timings.map((r) => (
              <li key={r.timing}>
                {t('lrnHarvestRow', { timing: t(`lrnTiming_${r.timing}`), kg: r.kg_per_m2, plots: r.plots })}
                {!r.enough && ` – ${t('lrnHarvestFew', { n: data.harvest.min_plots })}`}
              </li>
            ))}
          </ul>
        )}
        {data.can_control && (
          <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col">
              {t('lrnHarvestDate')}
              <input
                type="date"
                required
                max={today()}
                value={form.harvested_on}
                onChange={(e) => setForm((f) => ({ ...f, harvested_on: e.target.value }))}
                className="min-h-[44px] rounded border border-stone-300 px-2"
              />
            </label>
            <label className="flex flex-col">
              {t('lrnHarvestKg')}
              <input
                type="number"
                required
                min="0.1"
                step="0.1"
                value={form.kg}
                onChange={(e) => setForm((f) => ({ ...f, kg: e.target.value }))}
                className="min-h-[44px] w-28 rounded border border-stone-300 px-2"
              />
            </label>
            <button disabled={busy} className="min-h-[44px] rounded-lg bg-leaf px-4 font-semibold text-white disabled:opacity-50">
              {t('lrnHarvestAdd')}
            </button>
          </form>
        )}
        {harvests.length > 0 && (
          <p className="text-xs text-stone-600">
            {t('lrnHarvestLog')}: {harvests.slice(0, 5).map((h) => `${h.harvested_on} ${h.kg} kg`).join(' · ')}
          </p>
        )}
      </div>
      <p className="text-xs text-stone-500">{t('lrnCaveat')}</p>
    </section>
  )
}
