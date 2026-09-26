import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'

const pct = (x) => `${(x * 100).toFixed(1)}%`

export default function ModelPanel() {
  const { t } = useI18n()
  const [runs, setRuns] = useState(null)

  useEffect(() => {
    apiGet('/api/model/metrics')
      .then((m) => setRuns(m.runs))
      .catch(() => setRuns([]))
  }, [])

  const byCrop = (runs ?? []).reduce((acc, r) => ({ ...acc, [r.crop]: [...(acc[r.crop] ?? []), r] }), {})

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-4">
      <h3 className="font-bold">{t('modelPanel')}</h3>
      {runs && runs.length === 0 && <p className="text-stone-600">{t('noRuns')}</p>}
      <ul className="mt-2 space-y-1">
        {Object.entries(byCrop).map(([crop, list]) => {
          const last = list.slice(-2)
          return (
            <li key={crop}>
              <strong>{t(crop)}:</strong>{' '}
              {last.map((r) => `${r.version} ${pct(r.val_accuracy)}`).join(' → ')}
              {last.length === 2 && (
                <span className={last[1].val_accuracy >= last[0].val_accuracy ? 'ml-2 text-leaf' : 'ml-2 text-red-700'}>
                  ({last[1].val_accuracy >= last[0].val_accuracy ? '+' : ''}
                  {((last[1].val_accuracy - last[0].val_accuracy) * 100).toFixed(1)} pp)
                </span>
              )}
              <span className="ml-2 text-xs text-stone-500">
                {t('trainedOn', { n: list[list.length - 1].train_size ?? '?' })}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
