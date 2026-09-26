import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'

export default function HealthStatus() {
  const { t } = useI18n()
  const [health, setHealth] = useState(null)
  useEffect(() => {
    apiGet('/api/health')
      .then(setHealth)
      .catch((err) => setHealth(err.body || { database: 'error', redis: 'error' }))
  }, [])
  if (!health) return null
  const item = (name, value) => (
    <li className="flex items-center gap-2">
      <span className={`inline-block h-3 w-3 rounded-full ${value === 'ok' ? 'bg-leaf' : 'bg-amber-warn'}`} aria-hidden="true" />
      {name}: {value === 'ok' ? t('ok') : t('unavailable')}
    </li>
  )
  return (
    <section aria-label={t('systemStatus')} className="text-sm text-stone-600">
      <ul className="flex flex-wrap gap-4">
        {item(t('database'), health.database)}
        {item(t('redis'), health.redis)}
      </ul>
    </section>
  )
}
