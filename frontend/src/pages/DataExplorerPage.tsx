import { useEffect, useMemo, useState } from 'react'
import { getPreview, getSchema } from '../services/api'
import type { ColumnMeta, PreviewData } from '../types'
import DatasetPicker from '../components/DatasetPicker'

function fmt(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'number') return v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return String(v)
}

export default function DataExplorerPage() {
  const [datasetId, setDatasetId] = useState('')
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [columns, setColumns] = useState<ColumnMeta[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Server-side explorer controls
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [search, setSearch] = useState('')
  const [visibleCols, setVisibleCols] = useState<string[]>([])
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortAsc, setSortAsc] = useState(true)
  const [filterCol, setFilterCol] = useState('')
  const [filterVal, setFilterVal] = useState('')

  // Load schema once per dataset
  useEffect(() => {
    if (!datasetId) {
      setPreview(null)
      setColumns([])
      setVisibleCols([])
      return
    }
    setPage(1)
    setSortCol(null)
    setFilterCol('')
    setFilterVal('')
    setSearch('')
    getSchema(datasetId)
      .then((sc) => {
        setColumns(sc.columns)
        setVisibleCols(sc.columns.map((c) => c.name))
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [datasetId])

  // Fetch paginated preview from DuckDB
  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    setError(null)

    getPreview(datasetId, {
      page,
      page_size: pageSize,
      search: search.trim() || undefined,
      sort_by: sortCol || undefined,
      sort_order: sortAsc ? 'asc' : 'desc',
      filter_col: filterCol || undefined,
      filter_val: filterVal.trim() || undefined,
    })
      .then((pv) => {
        setPreview(pv)
        if (visibleCols.length === 0 && pv.columns.length > 0) {
          setVisibleCols(pv.columns)
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [datasetId, page, pageSize, search, sortCol, sortAsc, filterCol, filterVal])

  const activeStats = sortCol ?? filterCol
    ? columns.find((c) => c.name === (sortCol ?? filterCol))
    : undefined

  const toggleColumn = (c: string) => {
    setVisibleCols((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]))
  }

  const searchedCols = useMemo(() => {
    return visibleCols
  }, [visibleCols])

  const totalPages = preview?.total_pages ?? Math.ceil((preview?.total_rows ?? 0) / pageSize)

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight mb-1">Data Explorer</h1>
      <p className="text-sm text-slate-600 mb-4">
        Direct columnar exploration via DuckDB. Paginated, sorted, and filtered on the server.
      </p>

      <div className="mb-4">
        <DatasetPicker value={datasetId} onChange={setDatasetId} />
      </div>

      {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">{error}</div>}

      {preview && (
        <>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <input
              className="input max-w-48"
              placeholder="Search across rows…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
            <select
              className="input max-w-48"
              value={filterCol}
              onChange={(e) => {
                setFilterCol(e.target.value)
                setPage(1)
              }}
            >
              <option value="">Filter column…</option>
              {preview.columns.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input
              className="input max-w-48"
              placeholder="Filter value…"
              value={filterVal}
              disabled={!filterCol}
              onChange={(e) => {
                setFilterVal(e.target.value)
                setPage(1)
              }}
            />
            {(sortCol || filterVal || search) && (
              <button
                className="btn-secondary"
                onClick={() => {
                  setSortCol(null)
                  setFilterCol('')
                  setFilterVal('')
                  setSearch('')
                  setPage(1)
                }}
              >
                Clear Filters
              </button>
            )}

            <div className="ml-auto flex items-center gap-2 text-xs text-slate-600">
              <span>Page size:</span>
              <select
                className="input py-1 text-xs"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1)
                }}
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
              <span className="font-medium">
                {preview.total_rows.toLocaleString()} total rows
              </span>
            </div>
          </div>

          {activeStats && (
            <div className="card p-3 mb-4 text-xs text-slate-600 flex flex-wrap gap-4">
              <span className="font-medium text-slate-900">{activeStats.name}</span>
              <span>type: {activeStats.dtype}</span>
              <span className="font-semibold text-brand-600">{activeStats.semantic_type}</span>
              <span>role: {activeStats.business_role}</span>
              <span>{activeStats.unique_count.toLocaleString()} unique</span>
              <span>{activeStats.null_count} nulls</span>
              {activeStats.avg !== null && activeStats.avg !== undefined && (
                <span>avg {fmt(activeStats.avg)} · min {fmt(activeStats.min)} · max {fmt(activeStats.max)}</span>
              )}
            </div>
          )}

          <div className="flex gap-1 mb-2 overflow-x-auto pb-1">
            {preview.columns.map((c) => (
              <button
                key={c}
                onClick={() => toggleColumn(c)}
                className={`px-2 py-1 rounded text-[11px] border whitespace-nowrap ${
                  visibleCols.includes(c)
                    ? 'bg-brand-50 border-brand-200 text-brand-700 font-medium'
                    : 'bg-slate-50 border-slate-200 text-slate-400'
                }`}
              >
                {c.replace(/_/g, ' ')}
              </button>
            ))}
          </div>

          <div className="card overflow-auto max-h-[600px] relative">
            {loading && (
              <div className="absolute inset-0 bg-white/60 flex items-center justify-center z-10 text-xs font-medium text-slate-500">
                Loading rows from Parquet…
              </div>
            )}
            <table className="min-w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 z-0">
                <tr className="border-b border-slate-200 text-left text-slate-700 font-semibold">
                  {searchedCols.map((c) => (
                    <th
                      key={c}
                      className="px-4 py-2.5 font-semibold whitespace-nowrap cursor-pointer hover:text-brand-600 select-none"
                      onClick={() => {
                        if (sortCol === c) setSortAsc(!sortAsc)
                        else { setSortCol(c); setSortAsc(true) }
                        setPage(1)
                      }}
                    >
                      {c.replace(/_/g, ' ')}
                      {sortCol === c && (sortAsc ? ' ▲' : ' ▼')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                    {searchedCols.map((c) => (
                      <td key={c} className="px-4 py-2 whitespace-nowrap font-mono text-xs text-slate-800">{fmt(row[c])}</td>
                    ))}
                  </tr>
                ))}
                {preview.rows.length === 0 && !loading && (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-400" colSpan={searchedCols.length}>
                      No rows match the search/filter criteria
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Server-side Pagination Bar */}
          <div className="flex items-center justify-between mt-3 px-1 text-xs text-slate-500">
            <div>
              Showing {((page - 1) * pageSize + 1).toLocaleString()} – {Math.min(page * pageSize, preview.total_rows).toLocaleString()} of {preview.total_rows.toLocaleString()}
            </div>
            <div className="flex items-center gap-2">
              <button
                className="btn-secondary px-3 py-1 text-xs"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                ← Previous
              </button>
              <span className="font-medium">
                Page {page} of {Math.max(1, totalPages)}
              </span>
              <button
                className="btn-secondary px-3 py-1 text-xs"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
