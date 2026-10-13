import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDefaultDashboard, listDatasets, moveChart, removeChart, saveDashboardConfig } from '../services/api'
import { getDecisionOverview } from '../services/decisionApi'
import type { Dashboard } from '../types'
import type { DecisionOverviewStats } from '../types/decisionTypes'
import ChartCard from '../components/ChartCard'

export default function DashboardPage() {
  const [dash, setDash] = useState<Dashboard | null>(null)
  const [datasetCount, setDatasetCount] = useState<number>(0)
  const [decisionStats, setDecisionStats] = useState<DecisionOverviewStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const load = () => {
    getDefaultDashboard()
      .then(setDash)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))

    listDatasets()
      .then((r) => setDatasetCount(r.datasets?.length || 0))
      .catch(() => setDatasetCount(0))

    getDecisionOverview()
      .then(setDecisionStats)
      .catch(() => {})
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

  if (error) {
    return (
      <div className="rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm px-4 py-3 shadow-sm">
        {error}
      </div>
    )
  }

  if (!dash) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Loading Dashboard…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <span>{dash.name || 'Executive Analytics Dashboard'}</span>
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            {dash.layout.length} analytical chart{dash.layout.length === 1 ? '' : 's'} · {datasetCount} active dataset{datasetCount === 1 ? '' : 's'}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link to="/analyst" className="btn-secondary">
            <span>✦</span> Ask Analyst
          </Link>
          <Link to="/charts" className="btn-secondary">
            <span>◔</span> Build Chart
          </Link>
          <button
            className="btn-primary"
            disabled={saved}
            onClick={async () => {
              setError(null)
              try {
                await saveDashboardConfig(dash)
                setSaved(true)
              } catch (e) {
                setError(e instanceof Error ? e.message : String(e))
              }
            }}
          >
            {saved ? '✓ Saved' : 'Save Dashboard'}
          </button>
        </div>
      </div>

      {/* Decision Intelligence Center Banner */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950 text-white shadow-md border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-2xl shadow-inner">
            ⚖️
          </div>
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="font-bold text-base text-white">Decision Intelligence Center</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/30 text-brand-200 font-semibold uppercase tracking-wider">
                Operational MVP
              </span>
            </div>
            <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
              {decisionStats ? (
                <>
                  <span className="font-bold text-white">{decisionStats.total_active_rules}</span> active deterministic rules ·{' '}
                  <span className="font-bold text-amber-300">{decisionStats.needs_review_count}</span> actions needing review ·{' '}
                  <span className="font-bold text-rose-300">{decisionStats.high_priority_count}</span> high priority alerts
                </>
              ) : (
                'Translate ML predictions, time-series forecasts, and dataset quality into explainable, rule-based operational actions.'
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/decisions"
            className="px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-md transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <span>Open Decision Center</span>
            <span>→</span>
          </Link>
        </div>
      </div>

      {/* Main Charts Grid or Empty State */}
      {dash.layout.length === 0 ? (
        <div className="card p-12 text-center text-slate-500 space-y-4">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center text-2xl">
            📊
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-800">Your Dashboard is Empty</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
              Add visual insights by asking the AI Analyst questions or building custom analytical charts with DuckDB.
            </p>
          </div>
          <div className="flex justify-center gap-3 pt-2">
            <Link to="/analyst" className="btn-primary">
              ✦ Ask AI Analyst
            </Link>
            <Link to="/charts" className="btn-secondary">
              ◔ Create Chart
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {dash.layout.map((chart, i) => (
            <div
              key={chart.id}
              className={dash.layout.length % 2 === 1 && i === dash.layout.length - 1 ? 'md:col-span-2' : ''}
            >
              <ChartCard
                title={chart.title}
                chartType={chart.chart_type}
                data={chart.data}
                dimension={chart.spec?.dimension ?? null}
                metric={chart.spec?.metric ?? null}
                insight={chart.insight}
                actions={
                  <div className="flex gap-1 text-xs">
                    <button
                      className="px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                      title="Move earlier"
                      onClick={() => act(() => moveChart(dash.id, chart.id, 'prev'))}
                    >
                      ←
                    </button>
                    <button
                      className="px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                      title="Move later"
                      onClick={() => act(() => moveChart(dash.id, chart.id, 'next'))}
                    >
                      →
                    </button>
                    <button
                      className="px-2 py-1 rounded bg-rose-50 text-rose-600 hover:bg-rose-100 transition-colors"
                      title="Remove"
                      onClick={() => act(() => removeChart(dash.id, chart.id))}
                    >
                      ✕
                    </button>
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
