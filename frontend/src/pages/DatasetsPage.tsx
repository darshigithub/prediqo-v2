import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteDataset, listDatasets, refreshDataset } from '../services/api'
import type { DatasetListItem } from '../types'

const SOURCE_BADGE: Record<string, string> = {
  csv: 'bg-amber-100 text-amber-700',
  excel: 'bg-green-100 text-green-700',
  google_sheets: 'bg-emerald-100 text-emerald-700',
  postgresql: 'bg-blue-100 text-blue-700',
}

const STATUS_BADGE: Record<string, string> = {
  READY: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  PROCESSING: 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse',
  FAILED: 'bg-red-50 text-red-700 border-red-200',
  STALE: 'bg-amber-50 text-amber-700 border-amber-200',
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState<Record<string, boolean>>({})

  const load = () => {
    listDatasets()
      .then((r) => setDatasets(r.datasets))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }

  useEffect(load, [])

  const handleDelete = async (id: string) => {
    try {
      await deleteDataset(id)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleRefresh = async (id: string) => {
    setRefreshing((prev) => ({ ...prev, [id]: true }))
    setError(null)
    try {
      await refreshDataset(id)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setTimeout(() => {
        setRefreshing((prev) => ({ ...prev, [id]: false }))
        load()
      }, 1000)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold">Datasets</h1>
        <Link to="/sources" className="btn-primary">+ Connect Data</Link>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Analytical datasets stored as Parquet and indexed with semantic metadata.
      </p>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">{error}</div>
      )}

      {datasets.length === 0 ? (
        <div className="card p-10 text-center text-slate-400">
          No datasets yet. <Link to="/sources" className="text-brand-600 hover:underline">Connect a data source</Link> to get started.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-slate-500">
                <th className="px-5 py-3 font-medium">Dataset Name</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Version</th>
                <th className="px-5 py-3 font-medium">Source</th>
                <th className="px-5 py-3 font-medium">Rows</th>
                <th className="px-5 py-3 font-medium">Columns</th>
                <th className="px-5 py-3 font-medium">Created</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => {
                const status = d.status || 'READY'
                const isRefreshing = refreshing[d.dataset_id]
                return (
                  <tr key={d.dataset_id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <Link to={`/datasets/${d.dataset_id}`} className="font-semibold text-brand-600 hover:underline">
                        {d.dataset_name}
                      </Link>
                      {d.error && (
                        <div className="text-xs text-red-500 mt-0.5 truncate max-w-xs">{d.error}</div>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${STATUS_BADGE[status] || STATUS_BADGE.READY}`}>
                        {status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                        v{d.version || 1}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${SOURCE_BADGE[d.source_type] ?? 'bg-slate-100 text-slate-600'}`}>
                        {d.source_type}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-medium text-slate-700">
                      {typeof d.rows === 'number' ? d.rows.toLocaleString() : '—'}
                    </td>
                    <td className="px-5 py-3 text-slate-600">{d.columns ?? '—'}</td>
                    <td className="px-5 py-3 text-slate-400 text-xs">
                      {d.created_at ? new Date(d.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-5 py-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          className="text-xs text-brand-600 hover:underline disabled:opacity-50"
                          disabled={isRefreshing || status === 'PROCESSING'}
                          onClick={() => handleRefresh(d.dataset_id)}
                          title="Refresh source into new version"
                        >
                          {isRefreshing ? 'Refreshing…' : '↻ Refresh'}
                        </button>
                        <button
                          className="text-xs text-red-500 hover:underline"
                          onClick={() => handleDelete(d.dataset_id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
