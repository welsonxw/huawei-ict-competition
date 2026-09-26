import { useState } from 'react'
import { apiPost } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { errorText } from '../lib/errors.js'

const STAGES = ['seedling', 'vegetative', 'flowering', 'fruiting']
const NUTRIENTS = ['n', 'p2o5', 'k2o']

export default function FertiliserPlanner({ plot }) {
  const { t, lang } = useI18n()
  const [stage, setStage] = useState('vegetative')
  const [ph, setPh] = useState('')
  const [advanced, setAdvanced] = useState(false)
  const [soil, setSoil] = useState({ n: '', p2o5: '', k2o: '' })
  const [previous, setPrevious] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!plot) return
    setBusy(true)
    setError(null)
    try {
      setResult(
        await apiPost('/api/fertiliser/recommend', {
          plot_id: plot.id,
          stage,
          ph: ph === '' ? null : ph,
          soil: advanced ? soil : null,
          previous_fertiliser: advanced ? previous : null,
        }),
      )
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const select = 'mt-1 block min-h-[48px] w-full rounded-lg border border-stone-300 px-3'
  return (
    <section className="space-y-3 rounded-xl border border-stone-200 bg-white p-4">
      <h3 className="text-lg font-bold">{t('fertTitle')}</h3>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <label>
          <span className="font-semibold">{t('fertStage')}</span>
          <select value={stage} onChange={(e) => setStage(e.target.value)} className={select}>
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {t(`stage_${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="font-semibold">{t('fertPh')}</span>
          <select value={ph} onChange={(e) => setPh(e.target.value)} className={select}>
            <option value="">{t('dontKnow')}</option>
            {Array.from({ length: 21 }, (_, i) => (4 + i * 0.2).toFixed(1)).map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 sm:col-span-2">
          <input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} className="h-5 w-5" />
          <span>{t('fertAdvanced')}</span>
        </label>
        {advanced && (
          <>
            {NUTRIENTS.map((n) => (
              <label key={n}>
                <span className="font-semibold">{t(`soil_${n}`)}</span>
                <select value={soil[n]} onChange={(e) => setSoil({ ...soil, [n]: e.target.value })} className={select}>
                  <option value="">{t('dontKnow')}</option>
                  <option value="low">{t('level_low')}</option>
                  <option value="medium">{t('level_medium')}</option>
                  <option value="high">{t('level_high')}</option>
                </select>
              </label>
            ))}
            <label>
              <span className="font-semibold">{t('fertPrevious')}</span>
              <input
                value={previous}
                onChange={(e) => setPrevious(e.target.value)}
                maxLength={120}
                className="mt-1 block min-h-[48px] w-full rounded-lg border border-stone-300 px-3"
              />
            </label>
          </>
        )}
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={!plot || busy}
            className="min-h-[48px] rounded-lg bg-leaf px-5 font-bold text-white disabled:opacity-50"
          >
            {t('fertButton')}
          </button>
        </div>
      </form>
      {error && <p className="text-red-700">{errorText(error, t)}</p>}
      {result && (
        <div className="space-y-2" aria-live="polite">
          {(result.placeholder_requirements || result.placeholder_prices) && (
            <p className="rounded-lg bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-900">
              {t('fertPlaceholder')}
            </p>
          )}
          <p className={`font-semibold ${result.feasible ? '' : 'text-orange-800'}`}>{result.text[lang].summary}</p>
          {result.products.length > 0 && (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-1">{t('fertProduct')}</th>
                  <th>{t('fertPlot')}</th>
                  <th>{t('fertPerPlant')}</th>
                  <th>{t('fertBag')}</th>
                </tr>
              </thead>
              <tbody>
                {result.products.map((p) => (
                  <tr key={p.name} className="border-b border-stone-100">
                    <td className="py-1">{p.name}</td>
                    <td>{p.kg_plot} kg</td>
                    <td>{p.g_per_plant != null ? `${p.g_per_plant} g` : '–'}</td>
                    <td>
                      {p.bag.count} × {p.bag.bag_kg} kg
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="text-sm text-stone-600">
            {t('fertCost')}: {result.cost_rm_plot != null ? `RM ${result.cost_rm_plot}` : t('fertCostTodo')}
          </p>
          <ul className="list-disc pl-5 text-sm">
            {result.text[lang].notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
