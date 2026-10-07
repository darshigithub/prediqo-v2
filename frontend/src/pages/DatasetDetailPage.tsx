import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getDataset, getPreview, getProfile, getSchema } from '../services/api'
import type { ColumnMeta, DatasetProfile, PreviewData } from '../types'

const TABS = ['Overview', 'Data', 'Profile', 'Schema'] as const
type Tab = (typeof TABS)[number]

const SEMANTIC_BADGE: Record<string, string> = {
  ID: 'bg-slate-100 text-slate-600',
  DIMENSION: 'bg-indigo-100 text-indigo-700',
  MEASURE: 'bg-sky-100 text-sky-700',
  DATE: 'bg-violet-100 text-violet-700',
  CATEGORY: 'bg-emerald-100 text-emerald-700',
  TEXT: 'bg-amber-100 text-amber-700',
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return String(v)
}

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [tab, setTab] = useState<Tab>('Overview')
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null)
  const [profile, setProfile] = useState<DatasetProfile | null>(null)
  const [columns, setColumns] = useState<ColumnMeta[]>([])
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([getDataset(id), getProfile(id), getSchema(id), getPreview(id, 50)])
      .then(([m, p, s, pv]) => {
        setMeta(m)
        setProfile(p.profile)
        setColumns(s.columns)
        setPreview(pv)
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (error) return <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">{error}</div>
  if (!meta || !profile) return <div className="text-slate-400 text-sm">Loading dataset…</div>

  const name = meta.dataset_name as string
  const source = meta.source_type as string

  return (
    <div>
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-2xl font-bold">{name}</h1>
        <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">{source}</span>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        {profile.rows.toLocaleString()} rows · {profile.columns} columns
        {' · '}
        <Link to="/explorer" className="text-brand-600 hover:underline">Open in Data Explorer</Link>
      </p>

      <div className="flex gap-1 mb-5 bg-slate-200/60 p-1 rounded-lg w-fit">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`tab ${tab === t ? 'bg-white shadow text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Overview' && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Rows', value: profile.rows.toLocaleString() },
            { label: 'Columns', value: profile.columns },
            { label: 'Missing Values', value: profile.missing_values.toLocaleString() },
            { label: 'Duplicate Rows', value: profile.duplicate_rows.toLocaleString() },
            { label: 'Numeric Columns', value: profile.numeric_columns.length },
            { label: 'Categorical Columns', value: profile.categorical_columns.length },
            { label: 'Date Columns', value: profile.date_columns.length },
            {
              label: 'Source Connected',
              value: meta.created_at ? new Date(meta.created_at as string).toLocaleDateString() : '—',
            },
          ].map((s) => (
            <div key={s.label} className="card p-5">
              <div className="text-xs text-slate-500">{s.label}</div>
              <div className="text-2xl font-bold mt-1">{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'Data' && preview && (
        <div className="card overflow-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-slate-500">
                {preview.columns.map((c) => (
                  <th key={c} className="px-4 py-2.5 font-medium whitespace-nowrap">{c.replace(/_/g, ' ')}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row, i) => (
                <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                  {preview.columns.map((c) => (
                    <td key={c} className="px-4 py-2 whitespace-nowrap">{fmt(row[c])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-2 text-xs text-slate-400 border-t border-slate-100">
            Showing {preview.rows.length} of {preview.total_rows.toLocaleString()} rows
          </div>
        </div>
      )}

      {tab === 'Profile' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Rows', value: profile.rows.toLocaleString() },
              { label: 'Columns', value: profile.columns },
              { label: 'Missing Values', value: profile.missing_values.toLocaleString() },
              { label: 'Duplicate Rows', value: profile.duplicate_rows.toLocaleString() },
            ].map((s) => (
              <div key={s.label} className="card p-4">
                <div className="text-xs text-slate-500">{s.label}</div>
                <div className="text-xl font-bold mt-1">{s.value}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {columns.filter((c) => profile.column_stats[c.name]).map((c) => {
              const st = profile.column_stats[c.name]
              return (
                <div key={c.name} className="card p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-sm">{c.name.replace(/_/g, ' ')}</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${SEMANTIC_BADGE[st.semantic_type] ?? 'bg-slate-100'}`}>
                      {st.semantic_type}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mb-2">
                    {st.dtype} · {st.unique_count.toLocaleString()} unique · {st.null_count} nulls
                  </div>
                  {st.min !== null && st.min !== undefined && (
                    <div className="text-xs text-slate-600">
                      min {fmt(st.min)} · max {fmt(st.max)} · avg {fmt(st.avg)}
                    </div>
                  )}
                  {st.top_values && st.top_values.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {st.top_values.slice(0, 5).map((tv) => (
                        <div key={tv.value} className="flex items-center gap-2 text-xs">
                          <span className="w-28 truncate text-slate-600">{tv.value}</span>
                          <div className="flex-1 h-1.5 bg-slate-100 rounded">
                            <div className="h-1.5 bg-brand-500 rounded"
                              style={{ width: `${(tv.count / profile.rows) * 100}%` }} />
                          </div>
                          <span className="text-slate-400 w-8 text-right">{tv.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {tab === 'Schema' && (
        <div className="card overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-slate-500">
                <th className="px-5 py-3 font-medium">Column</th>
                <th className="px-5 py-3 font-medium">Type</th>
                <th className="px-5 py-3 font-medium">Semantic Type</th>
                <th className="px-5 py-3 font-medium">Nulls</th>
                <th className="px-5 py-3 font-medium">Unique Values</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((c) => (
                <tr key={c.name} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-5 py-2.5 font-medium">{c.name}</td>
                  <td className="px-5 py-2.5 text-slate-500">{c.dtype}</td>
                  <td className="px-5 py-2.5">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${SEMANTIC_BADGE[c.semantic_type] ?? 'bg-slate-100'}`}>
                      {c.semantic_type}
                    </span>
                  </td>
                  <td className="px-5 py-2.5">{c.null_count}</td>
                  <td className="px-5 py-2.5">{c.unique_count.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

