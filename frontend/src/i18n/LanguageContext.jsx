import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { strings } from './strings.js'

const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem('lang') || 'en')
  const changeLang = useCallback((next) => {
    localStorage.setItem('lang', next)
    document.documentElement.lang = next === 'ms' ? 'ms' : 'en'
    setLang(next)
  }, [])
  const t = useCallback(
    (key, vars = {}) => {
      const template = strings[lang]?.[key] ?? strings.en[key] ?? key
      return template.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '')
    },
    [lang],
  )
  const value = useMemo(() => ({ lang, setLang: changeLang, t }), [lang, changeLang, t])
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useI18n() {
  return useContext(LanguageContext)
}
