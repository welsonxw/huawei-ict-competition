import { useState } from 'react'
import { apiPost } from '../lib/api.js'
import { errorText } from '../lib/errors.js'
import { useI18n } from '../i18n/LanguageContext.jsx'

export default function AssistantPanel({ scanId }) {
  const { t, lang } = useI18n()
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const ask = async (q) => {
    setBusy(true)
    setError(null)
    try {
      const res = await apiPost('/api/assistant', { scan_id: scanId, question: q, lang })
      setHistory((h) => [...h, { q: q || t('askExplain'), ...res }])
      setQuestion('')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-4">
      <h3 className="font-bold">{t('assistant')}</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {['askExplain', 'askSpray', 'askSpread'].map((k) => (
          <button
            key={k}
            type="button"
            disabled={busy}
            onClick={() => ask(k === 'askExplain' ? '' : t(k))}
            className="min-h-[44px] rounded-full border border-leaf px-3 text-sm font-semibold text-leaf disabled:opacity-50"
          >
            {t(k)}
          </button>
        ))}
      </div>
      <ul className="mt-3 space-y-2" aria-live="polite">
        {history.map((m, i) => (
          <li key={i} className="text-sm">
            <p className="font-semibold">{m.q}</p>
            <p className="rounded-lg bg-leaf-light px-3 py-2">{m.answer}</p>
            <p className="text-xs text-stone-500">{m.source === 'llm' ? t('sourceLlm') : t('sourceTemplate')}</p>
          </li>
        ))}
      </ul>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          ask(question)
        }}
        className="mt-2 flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t('askPlaceholder')}
          aria-label={t('askPlaceholder')}
          maxLength={500}
          className="min-h-[44px] flex-1 rounded-lg border border-stone-300 px-3"
        />
        <button type="submit" disabled={busy || !question.trim()} className="min-h-[44px] rounded-lg bg-leaf px-4 font-bold text-white disabled:opacity-50">
          {t('ask')}
        </button>
      </form>
      {error && <p className="text-red-700">{errorText(error, t)}</p>}
    </section>
  )
}
