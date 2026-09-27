import { useState } from 'react'
import { useI18n } from './i18n/LanguageContext.jsx'
import LanguageToggle from './components/LanguageToggle.jsx'
import HealthStatus from './components/HealthStatus.jsx'
import LoginBox from './components/LoginBox.jsx'
import ArchitectureTab from './components/ArchitectureTab.jsx'
import FarmGame from './components/FarmGame.jsx'
import FarmMonitor from './components/FarmMonitor.jsx'
import ScanTab from './components/ScanTab.jsx'
import OutbreakMap from './components/OutbreakMap.jsx'
import NationalDashboard from './components/NationalDashboard.jsx'

const TABS = [
  { id: 'scan', label: 'tabScan', render: () => <ScanTab /> },
  { id: 'monitor', label: 'tabMonitor', render: () => <FarmMonitor /> },
  { id: 'map', label: 'tabMap', render: () => <OutbreakMap /> },
  { id: 'nation', label: 'tabNation', render: () => <NationalDashboard /> },
  { id: 'game', label: 'tabGame', render: () => <FarmGame /> },
  { id: 'arch', label: 'tabArch', render: () => <ArchitectureTab /> },
]

export default function App() {
  const { t } = useI18n()
  const [active, setActive] = useState('scan')
  const tab = TABS.find((x) => x.id === active)

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 pb-10">
      <header className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div>
          <h1 className="text-2xl font-extrabold text-leaf">{t('appName')}</h1>
          <p className="max-w-xl text-stone-600">{t('tagline')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <LoginBox />
          <LanguageToggle />
        </div>
      </header>

      <nav role="tablist" aria-label={t('tabsLabel')} className="-mx-4 mb-4 flex gap-1 overflow-x-auto border-b border-stone-200 px-4">
        {TABS.map((x) => (
          <button
            key={x.id}
            role="tab"
            id={`tab-${x.id}`}
            aria-selected={active === x.id}
            aria-controls={`panel-${x.id}`}
            onClick={() => setActive(x.id)}
            className={`min-h-[48px] whitespace-nowrap border-b-4 px-3 font-semibold ${
              active === x.id ? 'border-leaf text-leaf' : 'border-transparent text-stone-600 hover:text-leaf'
            }`}
          >
            {t(x.label)}
          </button>
        ))}
      </nav>

      <main id={`panel-${active}`} role="tabpanel" aria-labelledby={`tab-${active}`} className="flex-1">
        {tab.render(t)}
      </main>

      <footer className="mt-8 border-t border-stone-200 pt-4">
        <HealthStatus />
      </footer>
    </div>
  )
}
