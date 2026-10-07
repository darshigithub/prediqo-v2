import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDefaultDashboard, moveChart, removeChart, saveDashboardConfig } from '../services/api'
import type { Dashboard } from '../types'
import ChartCard from '../components/ChartCard'

export default function DashboardPage() {
  const [dash, setDash] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const load = () => {
    getDefaultDashboard()
      .then(setDash)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }

  useEffect(load, [])

  const act = async (fn: () => Promise<Dashboard>) => {
    setError(null)
    try {
      setDash(await fn())
      setSaved(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  if (error) return <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">{error}</div>
  if (!dash) return <div className="text-slate-400 text-sm">Loading dashboard…</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold">{dash.name}</h1>
          <p className="text-sm text-slate-500">
            {dash.layout.length} chart{dash.layout.length === 1 ? '' : 's'} · stored as JSON in data/metadata
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/analyst" className="btn-secondary">✦ Ask Analyst</Link>
          <Link to="/charts" className="btn-secondary">◔ Build Chart</Link>
          <button className="btn-primary" disabled={saved} onClick={async () => {
            setError(null)
            try {
              await saveDashboardConfig(dash)
              setSaved(true)
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e))
            }
          }}>
            {saved ? '✓ Saved' : 'Save Dashboard'}
          </button>
        </div>
      </div>

      {dash.layout.length === 0 ? (
        <div className="card p-10 text-center text-slate-400 mt-6">
          No charts yet. Ask the <Link to="/analyst" className="text-brand-600 hover:underline">AI Analyst</Link> a
          question and click “Add to Dashboard”, or{' '}
          <Link to="/charts" className="text-brand-600 hover:underline">build a chart</Link> manually.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
          {dash.layout.map((chart, i) => (
            <div key={chart.id} className={dash.layout.length % 2 === 1 && i === dash.layout.length - 1 ? 'md:col-span-2' : ''}>
              <ChartCard
                title={chart.title}
                chartType={chart.chart_type}
                data={chart.data}
                dimension={chart.spec?.dimension ?? null}
                metric={chart.spec?.metric ?? null}
                insight={chart.insight}
                actions={
                  <div className="flex gap-1 text-xs">
                    <button className="px-1.5 py-0.5 rounded hover:bg-slate-100" title="Move earlier"
                      onClick={() => act(() => moveChart(dash.id, chart.id, 'prev'))}>←</button>
                    <button className="px-1.5 py-0.5 rounded hover:bg-slate-100" title="Move later"
                      onClick={() => act(() => moveChart(dash.id, chart.id, 'next'))}>→</button>
                    <button className="px-1.5 py-0.5 rounded text-red-500 hover:bg-red-50" title="Remove"
                      onClick={() => act(() => removeChart(dash.id, chart.id))}>✕</button>
                  </div>
                }
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
