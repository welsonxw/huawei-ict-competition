import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Rectangle, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { apiGet } from '../lib/api.js'
import { useI18n } from '../i18n/LanguageContext.jsx'

const COLORS = { low: '#84CC16', medium: '#D97706', high: '#B91C1C', unknown: '#9CA3AF' }
const MALAYSIA = [4.2, 102.0]

function FitBounds({ cells }) {
  const map = useMap()
  const key = cells.length ? `${cells[0].cell}-${cells.length}` : ''
  useEffect(() => {
    if (!cells.length) return
    const lats = cells.flatMap((c) => [c.bounds[0][0], c.bounds[1][0]])
    const lons = cells.flatMap((c) => [c.bounds[0][1], c.bounds[1][1]])
    map.fitBounds([
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ], { padding: [20, 20], maxZoom: 11 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return null
}

export default function OutbreakMap() {
  const { t, lang } = useI18n()
  const [meta, setMeta] = useState(null)
  const [selected, setSelected] = useState('chilli:anthracnose')
  const [scenario, setScenario] = useState(null)
  const [hIndex, setHIndex] = useState(0)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiGet('/api/risk/diseases')
      .then((m) => {
        setMeta(m)
        setScenario(m.demo_scans > 0 ? 'demo' : 'live')
      })
      .catch((e) => setError(e.message))
  }, [])

  const horizons = meta?.horizons ?? [0, 3, 5]
  const horizon = horizons[hIndex]
  const [crop, disease] = selected.split(':')

  useEffect(() => {
    if (!scenario) return
    setError(null)
    apiGet('/api/risk', { crop, disease, horizon, scenario })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [crop, disease, horizon, scenario])

  const shown = useMemo(() => (data?.cells ?? []).filter((c) => c.band !== 'low' || c.reports > 0), [data])
  const horizonLabel = (h) => (h === 0 ? t('today') : `+${h} ${t('days')}`)

  return (
    <section className="space-y-3">
      {data?.simulated && (
        <p role="status" className="rounded-lg bg-amber-soft px-3 py-2 font-bold text-amber-warn">
          {t('simulatedBanner')}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <label>
          <span className="font-semibold">{t('disease')}</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="mt-1 block min-h-[48px] w-full rounded-lg border border-stone-300 px-3"
          >
            {(meta?.diseases ?? []).map((d) => (
              <option key={`${d.crop}:${d.disease}`} value={`${d.crop}:${d.disease}`}>
                {t(d.crop)} – {d.name[lang]}
              </option>
            ))}
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
            <option value="demo" disabled={!meta?.demo_scans}>
              {t('simulatedScenario')}
            </option>
          </select>
        </label>
        <label>
          <span className="font-semibold">
            {t('forecastDay')}: {horizonLabel(horizon)} {data?.date ? `(${data.date})` : ''}
          </span>
          <input
            type="range"
            min={0}
            max={horizons.length - 1}
            step={1}
            value={hIndex}
            onChange={(e) => setHIndex(Number(e.target.value))}
            className="mt-3 block w-full accent-leaf"
            aria-valuetext={horizonLabel(horizon)}
          />
          <span className="flex justify-between text-sm text-stone-600">
            {horizons.map((h) => (
              <span key={h}>{horizonLabel(h)}</span>
            ))}
          </span>
        </label>
      </div>
      {error && <p className="text-red-700">{error}</p>}

      <div className="h-[420px] overflow-hidden rounded-xl border border-stone-200">
        <MapContainer center={MALAYSIA} zoom={7} className="h-full w-full" scrollWheelZoom={false}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBounds cells={shown} />
          {shown.map((c) => (
            <Rectangle
              key={c.cell}
              bounds={c.bounds}
              pathOptions={{ color: COLORS[c.band], weight: 1, fillOpacity: c.band === 'low' ? 0.2 : 0.5 }}
            >
              <Tooltip>
                {t(`risk_${c.band}`)} · {t('riskScore')} {c.risk ?? '–'} · {t('weatherScore')} {c.s_weather ?? '–'} ·{' '}
                {c.reports} {t('reportsNearby')}
              </Tooltip>
            </Rectangle>
          ))}
          {(data?.report_points ?? []).map((p, i) => (
            <CircleMarker
              key={i}
              center={[p.lat, p.lon]}
              radius={3}
              pathOptions={{ color: '#1F2933', weight: 1, fillOpacity: 0.7 }}
            />
          ))}
        </MapContainer>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-sm">
        {['low', 'medium', 'high'].map((b) => (
          <span key={b} className="flex items-center gap-2">
            <span className="inline-block h-4 w-4 rounded" style={{ background: COLORS[b] }} />
            {t(`risk_${b}`)}: {data?.counts?.[b] ?? 0}
          </span>
        ))}
        <span className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-ink" /> {t('reportDots')}
        </span>
      </div>
      <p className="text-sm text-stone-600">{t('riskExplainer')}</p>
    </section>
  )
}
