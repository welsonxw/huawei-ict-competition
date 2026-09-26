import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { useAuth } from '../auth/AuthContext.jsx'
import { errorText } from '../lib/errors.js'
import AssistantPanel from './AssistantPanel.jsx'
import FertiliserPlanner from './FertiliserPlanner.jsx'
import ModelPanel from './ModelPanel.jsx'
import ReviewPanel from './ReviewPanel.jsx'

const pct = (x) => `${Math.round(x * 100)}%`

export default function ScanTab() {
  const { t, lang } = useI18n()
  const { user, ready } = useAuth()
  const [plots, setPlots] = useState([])
  const [plotId, setPlotId] = useState('')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!user) return
    apiGet('/api/plots')
      .then((ps) => {
        setPlots(ps)
        if (ps.length) setPlotId(String(ps[0].id))
      })
      .catch(() => setPlots([]))
  }, [user])

  useEffect(() => {
    if (!file) return setPreview(null)
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  const plot = plots.find((p) => String(p.id) === plotId)

  const submit = async (e) => {
    e.preventDefault()
    if (!file || !plot) return
    setBusy(true)
    setError(null)
    const form = new FormData()
    form.append('image', file)
    form.append('crop', plot.crop)
    form.append('plot_id', plot.id)
    try {
      setResult(await apiPost('/api/scans', form))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const scan = result?.scan
  if (!ready) return null
  if (!user) {
    return (
      <div className="space-y-4">
        <p className="rounded-xl border border-stone-200 bg-white p-4">{t('loginToScan')}</p>
        <ModelPanel />
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="space-y-3 rounded-xl border border-stone-200 bg-white p-4">
        <label className="block">
          <span className="font-semibold">{t('choosePlot')}</span>
          <select
            value={plotId}
            onChange={(e) => setPlotId(e.target.value)}
            className="mt-1 block min-h-[48px] w-full rounded-lg border border-stone-300 px-3"
          >
            {plots.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} – {t(p.crop)} ({p.region})
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="font-semibold">{t('leafPhoto')}</span>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-1 block w-full"
          />
        </label>
        {preview && <img src={preview} alt={t('leafPhoto')} className="h-40 rounded-lg object-cover" />}
        <button
          type="submit"
          disabled={!file || !plot || busy}
          className="min-h-[48px] rounded-lg bg-leaf px-5 font-bold text-white disabled:opacity-50"
        >
          {busy ? t('scanning') : t('scanButton')}
        </button>
        {error && <p className="text-red-700">{errorText(error, t)}</p>}
      </form>

      {scan && (
        <section className="space-y-3 rounded-xl border border-stone-200 bg-white p-4" aria-live="polite">
          {scan.is_stub && (
            <p className="rounded-lg bg-amber-100 px-3 py-2 font-semibold text-amber-900">
              {t('stubBadge')} {result.stub_reason ? `– ${result.stub_reason}` : ''}
            </p>
          )}
          {result.low_confidence ? (
            <p className="rounded-lg bg-orange-100 px-3 py-2 font-bold text-orange-900">{t('lowConfidence')}</p>
          ) : null}
          <div className="flex flex-wrap gap-4">
            <div>
              <p className="text-sm text-stone-600">{t('diagnosis')}</p>
              <p className="text-2xl font-extrabold">{result.display_name[lang]}</p>
              <p>
                {t('confidence')}: <strong>{pct(scan.confidence)}</strong> · {t('severity')}:{' '}
                <strong>{pct(scan.severity)}</strong>
              </p>
              <p className="mt-2 text-sm font-semibold">{t('top3')}</p>
              <ol className="list-decimal pl-5 text-sm">
                {result.top3_names.map((x) => (
                  <li key={x.label}>
                    {x.name[lang]} – {pct(x.confidence)}
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-xs text-stone-500">
                {t('model')}: {scan.model_version}
              </p>
            </div>
            <div className="flex gap-2">
              <figure>
                <img src={scan.image_url} alt={t('leafPhoto')} className="h-40 w-40 rounded-lg object-cover" />
                <figcaption className="text-center text-xs">{t('photo')}</figcaption>
              </figure>
              {scan.heatmap_url && (
                <figure>
                  <img src={scan.heatmap_url} alt={t('heatmap')} className="h-40 w-40 rounded-lg object-cover" />
                  <figcaption className="text-center text-xs">{t('heatmap')}</figcaption>
                </figure>
              )}
            </div>
          </div>
          <div>
            <h3 className="font-bold">{t('actionPlan')}</h3>
            <ol className="mt-1 list-decimal space-y-1 pl-5">
              {result.action_plan[lang].map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </div>
        </section>
      )}

      {scan && <AssistantPanel key={scan.id} scanId={scan.id} />}

      <FertiliserPlanner key={plot?.id} plot={plot} />

      {user.role === 'expert' && <ReviewPanel refreshKey={scan?.id} />}

      <ModelPanel />
    </div>
  )
}
