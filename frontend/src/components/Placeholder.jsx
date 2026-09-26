import { useI18n } from '../i18n/LanguageContext.jsx'

export default function Placeholder({ title }) {
  const { t } = useI18n()
  return (
    <section className="card">
      <h2 className="mb-2 text-xl font-bold">{title}</h2>
      <p>{t('placeholder')}</p>
    </section>
  )
}
