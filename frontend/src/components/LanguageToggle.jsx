import { useI18n } from '../i18n/LanguageContext.jsx'

export default function LanguageToggle() {
  const { lang, setLang, t } = useI18n()
  return (
    <div role="group" aria-label={t('language')} className="flex overflow-hidden rounded-lg border-2 border-leaf">
      {[
        ['ms', 'BM'],
        ['en', 'EN'],
      ].map(([code, label]) => (
        <button
          key={code}
          type="button"
          aria-pressed={lang === code}
          onClick={() => setLang(code)}
          className={`min-h-[44px] min-w-[52px] px-3 font-bold ${lang === code ? 'bg-leaf text-white' : 'bg-white text-leaf'}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
