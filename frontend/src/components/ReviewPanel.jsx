import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api.js'
import { errorText } from '../lib/errors.js'
import { useI18n } from '../i18n/LanguageContext.jsx'

const BASE = import.meta.env.VITE_API_BASE || ''
const pct = (x) => `${Math.round(x * 100)}%`

function ReviewItem({ scan, labels, onDone }) {
  const { t, lang } = useI18n()
  const [label, setLabel] = useState(scan.diagnosis)
  const [error, setError] = useState(null)
  const name = (key) => labels.find((l) => l.label === key)?.name[lang] ?? key

  const send = async (value) => {
    setError(null)
    try {
      await apiPost(`/api/review/${scan.id}`, { label: value })
      onDone()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <li className="flex flex-wrap items-start gap-3 border-b border-stone-100 pb-3">
      <img src={`${BASE}${scan.image_url}`} alt={t('leafPhoto')} className="h-20 w-20 rounded object-cover" />
      <div className="min-w-[12rem] flex-1 text-sm">
        <p className="font-semibold">
          #{scan.id} {t(scan.crop)} – {t('modelGuess')}: {name(scan.diagnosis)} ({pct(scan.confidence)})
          {scan.is_stub && <span className="ml-2 rounded bg-amber-100 px-1 text-amber-900">{t('stubShort')}</span>}
        </p>
        <p className="text-stone-600">
          {t('top3')}: {scan.top3.map((x) => `${name(x.label)} ${pct(x.confidence)}`).join(' · ')}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" onClick={() => send(scan.diagnosis)} className="min-h-[44px] rounded-lg bg-leaf px-3 font-bold text-white">
            {t('confirm')}
          </button>
          <select
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            aria-label={t('correctLabel')}
            className="min-h-[44px] rounded-lg border border-stone-300 px-2"
          >
            {labels.map((l) => (
              <option key={l.label} value={l.label}>
                {l.name[lang]}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={label === scan.diagnosis}
            onClick={() => send(label)}
            className="min-h-[44px] rounded-lg border-2 border-leaf px-3 font-bold text-leaf disabled:opacity-50"
          >
            {t('correct')}
          </button>
        </div>
        {error && <p className="text-red-700">{errorText(error, t)}</p>}
      </div>
    </li>
  )
}

export default function ReviewPanel({ refreshKey }) {
  const { t } = useI18n()
  const [items, setItems] = useState([])
  const [labels, setLabels] = useState({ chilli: [], tomato: [] })
  const [tick, setTick] = useState(0)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all(['chilli', 'tomato'].map((c) => apiGet('/api/review/labels', { crop: c })))
      .then(([chilli, tomato]) => setLabels({ chilli, tomato }))
      .catch((e) => setError(e))
  }, [])

  useEffect(() => {
    apiGet('/api/review/queue')
      .then(setItems)
      .catch((e) => setError(e))
  }, [refreshKey, tick])

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-bold">
          {t('reviewQueue')} ({items.length})
        </h3>
        <div className="flex gap-2 text-sm">
          {['chilli', 'tomato'].map((c) => (
            <a
              key={c}
              href={`${BASE}/api/export/training-set?crop=${c}`}
              className="inline-flex min-h-[44px] items-center rounded-lg border border-stone-300 px-3 font-semibold"
            >
              {t('exportSet', { crop: t(c) })}
            </a>
          ))}
        </div>
      </div>
      {error && <p className="text-red-700">{errorText(error, t)}</p>}
      {items.length === 0 ? (
        <p className="text-stone-600">{t('reviewEmpty')}</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {items.slice(0, 20).map((s) => (
            <ReviewItem key={s.id} scan={s} labels={labels[s.crop]} onDone={() => setTick((x) => x + 1)} />
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-stone-500">{t('exportHint')}</p>
    </section>
  )
}
