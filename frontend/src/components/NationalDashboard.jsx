import { useEffect, useMemo, useState } from 'react'
import { GeoJSON, MapContainer, TileLayer, Tooltip } from 'react-leaflet'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts'
import 'leaflet/dist/leaflet.css'
import { apiGet } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'

const LEVEL_COLORS = { low: '#84CC16', watch: '#D97706', high: '#B91C1C', insufficient: '#D1D5DB' }
const CROP_COLORS = { chilli: '#B91C1C', tomato: '#1F5C3A' }

const pct = (x) => (x == null ? '–' : `${(x * 100).toFixed(1)}%`)
const tonnes = (x) => (x == null ? '–' : x.toLocaleString(undefined, { maximumFractionDigits: 1 }))

export default function NationalDashboard() {
  const { t } = useI18n()
  const [geo, setGeo] = useState(null)
  const [scenario, setScenario] = useState(null)
  const [demoScans, setDemoScans] = useState(0)
  const [crop, setCrop] = useState('chilli')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiGet('/api/regions/geojson').then(setGeo).catch((e) => setError(e.message))
    apiGet('/api/risk/diseases')
      .then((m) => {
        setDemoScans(m.demo_scans)
        setScenario(m.demo_scans > 0 ? 'demo' : 'live')
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!scenario) return
    setError(null)
    apiGet('/api/national', { scenario }).then(setData).catch((e) => setError(e.message))
  }, [scenario])

  const rows = useMemo(() => data?.crops?.[crop]?.regions ?? [], [data, crop])
  const byCode = useMemo(() => Object.fromEntries(rows.map((r) => [r.code, r])), [rows])

  const style = (feature) => ({
    color: '#374151',
    weight: 1,
    fillOpacity: 0.6,
    fillColor: LEVEL_COLORS[byCode[feature.properties.code]?.level ?? 'insufficient'],
  })

  return (
    <section className="space-y-3">
      {data?.simulated && (
        <p role="status" className="rounded-lg bg-amber-soft px-3 py-2 font-bold text-amber-warn">
          {t('simulatedBanner')}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <label>
          <span className="font-semibold">{t('crop')}</span>
          <select
            value={crop}
            onChange={(e) => setCrop(e.target.value)}
            className="mt-1 block min-h-[48px] w-full rounded-lg border border-stone-300 px-3"
          >
            <option value="chilli">{t('chilli')}</option>
            <option value="tomato">{t('tomato')}</option>
          </select>
        </label>
        <label>
          <span className="font-semibold">{t('dataSource')}</span>
          <select
            value={scenario ?? 'live'}
            onChange={(e) => setScenario(e.target.value)}
            className="mt-1 block min-h-[48px] w-full rounded-lg border border-stone-300 px-3"
          >
            <option value="live">{t('liveData')}</option>
            <option value="demo" disabled={!demoScans}>
              {t('simulatedScenario')}
            </option>
          </select>
        </label>
      </div>
      {error && <p className="text-red-700">{error}</p>}

      {data && (
        <p className="rounded-lg bg-leaf-light px-3 py-2">
          <strong>{t('tonnesAtRisk')}:</strong> {tonnes(data.crops[crop].tonnes_at_risk)} t / {t('expectedHarvest')}{' '}
          {tonnes(data.crops[crop].production_t_window)} t ({t('nextDays', { n: data.window_days })})
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-[420px] overflow-hidden rounded-xl border border-stone-200">
          <MapContainer center={[4.2, 102.0]} zoom={6} className="h-full w-full" scrollWheelZoom={false}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors; boundaries: geoBoundaries (ODbL)'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {geo &&
              geo.features.map((f) => {
                const r = byCode[f.properties.code]
                return r ? (
                  <GeoJSON key={`${f.properties.code}-${crop}-${data?.generated_at}`} data={f} style={style}>
                    <Tooltip sticky>
                      {r.name}: {t(`supply_${r.level}`)} · {tonnes(r.tonnes_at_risk)} t · {pct(r.share_at_risk)}
                    </Tooltip>
                  </GeoJSON>
                ) : null
              })}
          </MapContainer>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-stone-300">
                <th className="py-2 pr-2">{t('region')}</th>
                <th className="pr-2">{t('supplyRisk')}</th>
                <th className="pr-2 text-right">{t('tonnesAtRisk')}</th>
                <th className="pr-2 text-right">{t('shareAtRisk')}</th>
                <th className="pr-2 text-right">{t('scansCol')}</th>
                <th className="text-right">{t('productionYear', { year: data?.production_year ?? '' })}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.code} className="border-b border-stone-100">
                  <td className="py-2 pr-2">{r.name}</td>
                  <td className="pr-2">
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block h-3 w-3 rounded" style={{ background: LEVEL_COLORS[r.level] }} />
                      {t(`supply_${r.level}`)}
                    </span>
                  </td>
                  <td className="pr-2 text-right">{tonnes(r.tonnes_at_risk)}</td>
                  <td className="pr-2 text-right">{pct(r.share_at_risk)}</td>
                  <td className="pr-2 text-right">
                    {r.diseased}/{r.scans}
                  </td>
                  <td className="text-right">{tonnes(r.production_t_year)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="font-semibold">{t('trendTitle')}</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data?.trend ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} />
              <YAxis unit=" t" width={70} />
              <ChartTooltip />
              <Legend />
              {['chilli', 'tomato'].map((c) => (
                <Line key={c} type="monotone" dataKey={c} name={t(c)} stroke={CROP_COLORS[c]} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 text-sm">
        {['low', 'watch', 'high', 'insufficient'].map((l) => (
          <span key={l} className="flex items-center gap-2">
            <span className="inline-block h-4 w-4 rounded" style={{ background: LEVEL_COLORS[l] }} />
            {t(`supply_${l}`)}
          </span>
        ))}
      </div>
      <p className="text-sm font-semibold text-amber-warn">{t('surveyBiasNote')}</p>
      <p className="text-sm text-stone-600">
        {t('nationalExplainer')} {t('productionSource')}: {data?.production_source}.{' '}
        {data?.damage_placeholder && t('damagePlaceholder')}
      </p>
    </section>
  )
}
