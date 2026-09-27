import { useCallback, useEffect, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiGet, apiPost } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { useAuth } from '../auth/AuthContext.jsx'
import FarmControls from './FarmControls.jsx'
import RoutineOptimiser from './RoutineOptimiser.jsx'
import { errorText } from '../lib/errors.js'
import { METRICS, alertKey, alertVars, chartRows, formatBand, formatValue, minutesAgo } from '../monitor/format.js'

const REFRESH_MS = 30000
const RANGES = [24, 72, 168]
const TRANSPORT_LABELS = { http: 'HTTP', mqtt: 'MQTT', iotda: 'Huawei IoTDA' }
const STATUS_STYLE = {
  ok: 'border-emerald-300 bg-emerald-50',
  low: 'border-amber-400 bg-amber-50',
  high: 'border-red-400 bg-red-50',
}

function MetricCard({ metric, data, status, band, unit, extra }) {
  const { t } = useI18n()
  const value = data?.value
  const shown = metric.bool ? (value === undefined ? '–' : t(value ? 'monYes' : 'monNo')) : formatValue(metric, value, unit)
  return (
    <div className={`rounded-xl border p-3 ${STATUS_STYLE[status] ?? 'border-stone-200 bg-white'}`}>
      <p className="text-sm text-stone-600">{t(metric.label)}</p>
      <p className="text-2xl font-extrabold">{shown}</p>
      <p className="text-xs text-stone-600">
        {status && <strong className="mr-1">{t(`monStatus_${status}`)}</strong>}
        {band && `${t('monTarget')} ${formatBand(band, unit)}`}
        {extra}
      </p>
    </div>
  )
}

export default function FarmMonitor() {
  const { t, lang } = useI18n()
  const { user, ready } = useAuth()
  const [plots, setPlots] = useState([])
  const [plotId, setPlotId] = useState('')
  const [hours, setHours] = useState(24)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [newKey, setNewKey] = useState(null)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    if (!user) return
    apiGet('/api/plots')
      .then((ps) => {
        setPlots(ps)
        if (ps.length) setPlotId((cur) => cur || String(ps[0].id))
      })
      .catch(setError)
  }, [user])

  const load = useCallback(() => {
    if (!plotId) return
    apiGet(`/api/plots/${plotId}/monitor`, { hours })
      .then((d) => {
        setData(d)
        setError(null)
        setNow(Date.now())
      })
      .catch(setError)
  }, [plotId, hours])

  useEffect(() => {
    setNewKey(null)
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [load])

  const addDevice = async (simulated) => {
    setBusy(true)
    try {
      const d = await apiPost(`/api/plots/${plotId}/devices`, { simulated })
      if (d.key) setNewKey({ uid: d.uid, key: d.key })
      load()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  if (!ready) return null
  if (!user) return <p className="rounded-xl border border-stone-200 bg-white p-4">{t('monLogin')}</p>

  const rows = data ? chartRows(data.history, lang) : []
  const units = data?.units ?? {}

  return (
    <div className="space-y-4">
      <section className="flex flex-wrap items-end gap-3 rounded-xl border border-stone-200 bg-white p-4">
        <div className="mr-auto">
          <h2 className="text-lg font-bold">{t('monTitle')}</h2>
          <p className="text-sm text-stone-600">{t('monIntro')}</p>
        </div>
        <label>
          <span className="block text-sm font-semibold">{t('choosePlot')}</span>
          <select
            value={plotId}
            onChange={(e) => setPlotId(e.target.value)}
            className="min-h-[48px] rounded-lg border border-stone-300 px-3"
          >
            {plots.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} – {t(p.crop)} ({p.region})
              </option>
            ))}
          </select>
        </label>
        <button onClick={load} className="min-h-[48px] rounded-lg border border-leaf px-4 font-semibold text-leaf">
          {t('monRefresh')}
        </button>
      </section>

      {error && <p className="text-red-700">{errorText(error, t)}</p>}

      {plots.length === 0 && !error && <p className="rounded-lg bg-stone-100 px-3 py-2">{t('monNoPlots')}</p>}

      {data?.simulated && (
        <p role="note" className="rounded-lg bg-amber-100 px-3 py-2 font-semibold text-amber-900">
          {t('monSimBanner')}
        </p>
      )}

      {data && (
        <section className="flex flex-wrap items-center gap-2 rounded-xl border border-stone-200 bg-white p-4">
          {data.devices.length === 0 && <p className="mr-auto">{t('monNoDevice')}</p>}
          {data.devices.map((d) => {
            const ago = minutesAgo(d.last_seen_at, now)
            return (
              <div key={d.id} className="mr-auto flex flex-wrap items-center gap-2 text-sm">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                    d.is_simulated ? 'bg-amber-200 text-amber-900' : 'bg-sky-100 text-sky-900'
                  }`}
                >
                  {t(d.is_simulated ? 'monSimBadge' : 'monRealBadge')}
                </span>
                <strong>{d.name}</strong>
                {TRANSPORT_LABELS[d.transport] && (
                  <span className="text-xs text-stone-500">
                    {t('monVia', { value: TRANSPORT_LABELS[d.transport] })}
                  </span>
                )}
                <span className={d.online ? 'text-emerald-700' : 'text-red-700'}>
                  ● {t(d.online ? 'monOnline' : 'monOffline')}
                </span>
                <span className="text-stone-600">
                  {t('monLastSeen')}: {ago === null ? t('monNever') : t('monMinAgo', { n: ago })}
                </span>
              </div>
            )
          })}
          <button
            disabled={busy}
            onClick={() => addDevice(true)}
            className="min-h-[44px] rounded-lg bg-leaf px-3 font-semibold text-white disabled:opacity-50"
          >
            {t('monAddSim')}
          </button>
          <button
            disabled={busy}
            onClick={() => addDevice(false)}
            className="min-h-[44px] rounded-lg border border-stone-300 px-3 font-semibold disabled:opacity-50"
          >
            {t('monAddReal')}
          </button>
          {newKey && (
            <div className="w-full rounded-lg bg-sky-50 p-3 text-sm" aria-live="polite">
              <p className="font-semibold">{t('monKeyOnce')}</p>
              <p>
                {t('monDeviceId')}: <code>{newKey.uid}</code>
              </p>
              <p>
                {t('monDeviceKey')}: <code className="break-all">{newKey.key}</code>
              </p>
            </div>
          )}
        </section>
      )}

      {data && Object.keys(data.latest).length > 0 && (
        <>
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {METRICS.map((m) => (
              <MetricCard
                key={m.key}
                metric={m}
                data={data.latest[m.key]}
                status={data.status[m.key]}
                band={data.targets[m.key]}
                unit={units[m.key]}
                extra={
                  m.key === 'leaf_wet' && data.leaf_wet_hours > 0 ? ` ${t('monLeafWetFor', { n: data.leaf_wet_hours })}` : null
                }
              />
            ))}
          </section>
          {data.targets_placeholder && <p className="text-xs text-stone-500">{t('monPlaceholder')}</p>}
        </>
      )}

      {data && <FarmControls plotId={plotId} onApplied={load} />}

      {data && <RoutineOptimiser plotId={plotId} onApplied={load} />}

      {data && (
        <section className="rounded-xl border border-stone-200 bg-white p-4" aria-live="polite">
          <h3 className="mb-2 font-bold">{t('monAlerts')}</h3>
          {data.alerts.length === 0 ? (
            <p className="text-emerald-700">{t('monNoAlerts')}</p>
          ) : (
            <ul className="space-y-1">
              {data.alerts.map((a, i) => (
                <li
                  key={`${a.code}-${i}`}
                  className={`rounded-lg px-3 py-2 ${a.level === 'danger' ? 'bg-red-100 text-red-900' : 'bg-amber-50 text-amber-900'}`}
                >
                  {t(alertKey(a), alertVars(a, units))}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {data && (
        <section className="rounded-xl border border-stone-200 bg-white p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h3 className="mr-auto font-bold">{t('monHistory')}</h3>
            {RANGES.map((h) => (
              <button
                key={h}
                onClick={() => setHours(h)}
                aria-pressed={hours === h}
                className={`min-h-[40px] rounded-lg px-3 text-sm font-semibold ${
                  hours === h ? 'bg-leaf text-white' : 'border border-stone-300'
                }`}
              >
                {t('monHours', { n: h })}
              </button>
            ))}
          </div>
          {rows.length === 0 ? (
            <p className="text-stone-600">{t('monNoReadings')}</p>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="t" minTickGap={40} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="pct" domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="c" orientation="right" domain={[15, 40]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line yAxisId="pct" dataKey="soil" name={t('monChartSoil')} stroke="#1d4ed8" dot={false} strokeWidth={2} />
                  <Line yAxisId="pct" dataKey="rh" name={t('monChartRh')} stroke="#0d9488" dot={false} />
                  <Line yAxisId="c" dataKey="air" name={t('monChartAir')} stroke="#dc2626" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
