import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getConnectors,
  getIngestionJob,
  listDatasets,
  startIngestionJob,
  startIngestionJobFile,
} from '../services/api'
import type { ConnectorCard, IngestionJob } from '../types'

const STAGES = [
  { key: 'READING', label: 'Reading source' },
  { key: 'STANDARDIZING', label: 'Standardizing columns' },
  { key: 'PROFILING', label: 'Profiling data' },
  { key: 'SEMANTIC_ANALYSIS', label: 'Building semantic model' },
  { key: 'WRITING', label: 'Writing analytical storage' },
]

export default function DataSourcesPage() {
  const [connectors, setConnectors] = useState<ConnectorCard[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [datasetCount, setDatasetCount] = useState(0)
  const [activeJob, setActiveJob] = useState<IngestionJob | null>(null)

  // modal state
  const [modal, setModal] = useState<'google_sheets' | 'postgresql' | null>(null)
  const [sheetId, setSheetId] = useState('')
  const [sheetName, setSheetName] = useState('')
  const [pg, setPg] = useState({ host: 'localhost', port: 5432, database: '', user: '', password: '', table: '' })

  const pollIntervalRef = useRef<number | null>(null)

  useEffect(() => {
    getConnectors().then((r) => setConnectors(r.connectors)).catch(() => setConnectors([]))
    listDatasets().then((r) => setDatasetCount(r.datasets.length)).catch(() => setDatasetCount(0))
  }, [activeJob?.status])

  useEffect(() => {
    if (!activeJob || activeJob.status === 'COMPLETED' || activeJob.status === 'FAILED') {
      if (pollIntervalRef.current) {
        window.clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      return
    }

    pollIntervalRef.current = window.setInterval(async () => {
      try {
        const latest = await getIngestionJob(activeJob.job_id)
        setActiveJob(latest)
        if (latest.status === 'FAILED' && latest.error) {
          setError(latest.error)
        }
      } catch (err) {
        console.warn('Failed to poll ingestion job:', err)
      }
    }, 500)

    return () => {
      if (pollIntervalRef.current) {
        window.clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
  }, [activeJob?.job_id, activeJob?.status])

  const handleFile = async (kind: 'csv' | 'excel', file?: File | null) => {
    if (!file) return
    setBusy(kind)
    setError(null)
    try {
      const job = await startIngestionJobFile(file)
      setActiveJob(job)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const handleSheets = async () => {
    setBusy('google_sheets')
    setError(null)
    try {
      const job = await startIngestionJob({
        source_type: 'google_sheets',
        dataset_name: sheetName.trim() || undefined,
        source_config: { sheet_id: sheetId.trim(), sheet_name: sheetName.trim() || null },
      })
      setActiveJob(job)
      setModal(null)
      setSheetId('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const handlePostgres = async () => {
    setBusy('postgresql')
    setError(null)
    try {
      const job = await startIngestionJob({
        source_type: 'postgresql',
        dataset_name: pg.table,
        source_config: pg,
      })
      setActiveJob(job)
      setModal(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const getStageState = (stageKey: string) => {
    if (!activeJob) return 'todo'
    if (activeJob.status === 'COMPLETED') return 'done'
    const stageOrder = ['READING', 'STANDARDIZING', 'PROFILING', 'SEMANTIC_ANALYSIS', 'WRITING', 'COMPLETED']
    const currIdx = stageOrder.indexOf(activeJob.stage)
    const targetIdx = stageOrder.indexOf(stageKey)
    if (currIdx > targetIdx) return 'done'
    if (currIdx === targetIdx) return 'active'
    return 'todo'
  }

  const cardActions = (id: string) => {
    switch (id) {
      case 'csv':
        return (
          <label className="btn-primary cursor-pointer">
            {busy === 'csv' ? 'Starting…' : 'Connect'}
            <input type="file" accept=".csv" className="hidden"
              onChange={(e) => handleFile('csv', e.target.files?.[0])} />
          </label>
        )
      case 'excel':
        return (
          <label className="btn-primary cursor-pointer">
            {busy === 'excel' ? 'Starting…' : 'Connect'}
            <input type="file" accept=".xlsx,.xls" className="hidden"
              onChange={(e) => handleFile('excel', e.target.files?.[0])} />
          </label>
        )
      case 'google_sheets':
        return <button className="btn-primary" onClick={() => setModal('google_sheets')}>Connect</button>
      case 'postgresql':
        return <button className="btn-primary" onClick={() => setModal('postgresql')}>Connect</button>
      default:
        return null
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight mb-1">Data Sources</h1>
      <p className="text-sm text-slate-600 mb-6">
        Connect a data source once. The ingestion pipeline prepares, profiles, and persists it for repeated fast analysis.
      </p>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">
          {error}
        </div>
      )}

      {/* Real-time Ingestion Job Progress Card */}
      {activeJob && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white shadow-sm p-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-brand-600">
                {activeJob.status === 'COMPLETED' ? 'Dataset Ready' : 'Preparing Dataset'}
              </span>
              <h2 className="text-lg font-bold text-slate-900 mt-0.5">
                {activeJob.dataset_name}
              </h2>
            </div>
            <div className="text-right">
              <span className="text-2xl font-extrabold text-slate-900">{activeJob.progress}%</span>
              <div className="text-xs text-slate-500">{activeJob.status}</div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-slate-100 rounded-full h-2.5 mb-6 overflow-hidden">
            <div
              className={`h-2.5 rounded-full transition-all duration-300 ${
                activeJob.status === 'FAILED'
                  ? 'bg-red-500'
                  : activeJob.status === 'COMPLETED'
                  ? 'bg-emerald-500'
                  : 'bg-brand-600'
              }`}
              style={{ width: `${activeJob.progress}%` }}
            />
          </div>

          {/* Multi-Stage Stepper Checklist */}
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 pt-2 border-t border-slate-100">
            {STAGES.map((s) => {
              const state = getStageState(s.key)
              return (
                <div key={s.key} className="flex items-center gap-2 text-xs">
                  {state === 'done' && (
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 font-bold">
                      ✓
                    </span>
                  )}
                  {state === 'active' && (
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-100 text-brand-600 animate-pulse font-bold">
                      ●
                    </span>
                  )}
                  {state === 'todo' && (
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                      ○
                    </span>
                  )}
                  <span
                    className={`font-medium ${
                      state === 'done'
                        ? 'text-slate-800'
                        : state === 'active'
                        ? 'text-brand-600 font-semibold'
                        : 'text-slate-400'
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
              )
            })}
          </div>

          {activeJob.status === 'COMPLETED' && (
            <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-sm font-medium text-emerald-700">
                ✓ Dataset ready — {activeJob.row_count?.toLocaleString()} rows prepared and indexed
              </span>
              <div className="flex gap-2">
                <Link
                  to={`/datasets/${activeJob.dataset_id}`}
                  className="btn-secondary text-xs"
                >
                  Inspect Dataset →
                </Link>
                <Link
                  to="/analyst"
                  className="btn-primary text-xs"
                >
                  Analyze with AI →
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {connectors.map((c) => (
          <div key={c.id} className="card p-5 flex flex-col items-start">
            <div className="w-10 h-10 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center text-lg mb-3">
              {c.id === 'csv' && '📄'}
              {c.id === 'excel' && '📊'}
              {c.id === 'google_sheets' && '🟩'}
              {c.id === 'postgresql' && '🐘'}
            </div>
            <div className="font-semibold text-slate-800">{c.label}</div>
            <div className="text-xs text-slate-500 mt-0.5 mb-4">{c.description}</div>
            <div className="mt-auto">{cardActions(c.id)}</div>
          </div>
        ))}
      </div>

      {datasetCount > 0 && (
        <p className="mt-6 text-sm text-slate-500">
          {datasetCount} dataset{datasetCount > 1 ? 's' : ''} prepared —{' '}
          <Link to="/datasets" className="text-brand-600 hover:underline">view all</Link>
        </p>
      )}

      {modal === 'google_sheets' && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center z-50 p-4" onClick={() => setModal(null)}>
          <div className="card p-6 w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-slate-900 mb-1">Connect Google Sheet</h2>
            <p className="text-xs text-slate-600 mb-4">
              Paste the Sheet URL or ID. The sheet must be shared as “Anyone with the link”.
            </p>
            <input className="input mb-3" placeholder="https://docs.google.com/spreadsheets/d/…"
              value={sheetId} onChange={(e) => setSheetId(e.target.value)} />
            <input className="input mb-4" placeholder="Dataset name (optional)"
              value={sheetName} onChange={(e) => setSheetName(e.target.value)} />
            <div className="flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModal(null)}>Cancel</button>
              <button className="btn-primary" disabled={!sheetId.trim() || busy === 'google_sheets'}
                onClick={handleSheets}>
                {busy === 'google_sheets' ? 'Connecting…' : 'Start Ingestion'}
              </button>
            </div>
          </div>
        </div>
      )}

      {modal === 'postgresql' && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center z-50 p-4" onClick={() => setModal(null)}>
          <div className="card p-6 w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-slate-900 mb-4">Connect PostgreSQL</h2>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <input className="input" placeholder="Host" value={pg.host}
                onChange={(e) => setPg({ ...pg, host: e.target.value })} />
              <input className="input" placeholder="Port" type="number" value={pg.port}
                onChange={(e) => setPg({ ...pg, port: Number(e.target.value) })} />
            </div>
            <input className="input mb-3" placeholder="Database" value={pg.database}
              onChange={(e) => setPg({ ...pg, database: e.target.value })} />
            <input className="input mb-3" placeholder="User" value={pg.user}
              onChange={(e) => setPg({ ...pg, user: e.target.value })} />
            <input className="input mb-3" placeholder="Password" type="password" value={pg.password}
              onChange={(e) => setPg({ ...pg, password: e.target.value })} />
            <input className="input mb-4" placeholder="Table" value={pg.table}
              onChange={(e) => setPg({ ...pg, table: e.target.value })} />
            <div className="flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModal(null)}>Cancel</button>
              <button className="btn-primary" disabled={!pg.database || !pg.table || busy === 'postgresql'}
                onClick={handlePostgres}>
                {busy === 'postgresql' ? 'Connecting…' : 'Start Ingestion'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
