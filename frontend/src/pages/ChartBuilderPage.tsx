import { useEffect, useState } from 'react'
import { addToDashboard, getDefaultDashboard, getSchema, runChartSpec } from '../services/api'
import type { ChartSpec, ChartSpecResponse, ColumnMeta } from '../types'
import ChartCard from '../components/ChartCard'
import DatasetPicker from '../components/DatasetPicker'

const CHART_TYPES = ['bar', 'line', 'pie', 'area', 'scatter', 'kpi', 'table'] as const
const AGGS = ['sum', 'avg', 'count', 'min', 'max'] as const

export default function ChartBuilderPage() {
  const [datasetId, setDatasetId] = useState('')
  const [columns, setColumns] = useState<ColumnMeta[]>([])
  const [chartType, setChartType] = useState<string>('bar')
  const [dimension, setDimension] = useState('')
  const [metric, setMetric] = useState('')
  const [aggregation, setAggregation] = useState<string>('sum')
  const [sort, setSort] = useState('desc')
  const [topN, setTopN] = useState<string>('')
  const [filterCol, setFilterCol] = useState('')
  const [filterOp, setFilterOp] = useState('=')
  const [filterVal, setFilterVal] = useState('')
  const [result, setResult] = useState<ChartSpecResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [added, setAdded] = useState(false)

  useEffect(() => {
    if (!datasetId) return
    getSchema(datasetId)
      .then((s) => {
        setColumns(s.columns)
        const dims = s.columns.filter((c) => ['CATEGORY', 'DIMENSION', 'TEXT', 'DATE'].includes(c.semantic_type))
        const measures = s.columns.filter((c) => c.semantic_type === 'MEASURE')
        setDimension(dims[0]?.name ?? s.columns[0]?.name ?? '')
        setMetric(measures[0]?.name ?? s.columns[0]?.name ?? '')
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [datasetId])

  const dimensions = columns.filter((c) => ['CATEGORY', 'DIMENSION', 'TEXT', 'DATE', 'ID'].includes(c.semantic_type))
  const measures = columns.filter((c) => c.semantic_type === 'MEASURE')

  const buildSpec = (): ChartSpec => ({
    dataset_id: datasetId,
    type: chartType as ChartSpec['type'],
    dimension: dimension || null,
    metric: metric || null,
    aggregation,
    filters: filterCol && filterVal
      ? [{ column: filterCol, op: filterOp, value: Number.isNaN(Number(filterVal)) ? filterVal : Number(filterVal) }]
      : [],
    sort,
    top_n: topN ? Number(topN) : null,
  })

  const render = async () => {
    setBusy(true)
    setError(null)
    setAdded(false)
    try {
      setResult(await runChartSpec(buildSpec()))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const handleAddToDashboard = async () => {
    if (!result || !datasetId) return
    try {
      const dash = await getDefaultDashboard()
      await addToDashboard(dash.id, {
        dataset_id: datasetId,
        chart_type: result.chart_type,
        result: result.result.data,
        insight: result.insight,
        chart_spec: buildSpec(),
      })
      setAdded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Chart Builder</h1>
      <p className="text-sm text-slate-500 mb-4">Build a chart manually from any dataset.</p>

      <div className="mb-4">
        <DatasetPicker value={datasetId} onChange={setDatasetId} />
      </div>

      <div className="card p-4 mb-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 items-end">
        <label className="text-xs text-slate-500">Chart Type
          <select className="input mt-1" value={chartType} onChange={(e) => setChartType(e.target.value)}>
            {CHART_TYPES.map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-500">Dimension
          <select className="input mt-1" value={dimension} onChange={(e) => setDimension(e.target.value)}>
            <option value="">— none —</option>
            {dimensions.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-500">Metric
          <select className="input mt-1" value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="">— count rows —</option>
            {measures.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-500">Aggregation
          <select className="input mt-1" value={aggregation} onChange={(e) => setAggregation(e.target.value)}>
            {AGGS.map((a) => <option key={a} value={a}>{a.toUpperCase()}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-500">Filter
          <div className="flex gap-1 mt-1">
            <select className="input" value={filterCol} onChange={(e) => setFilterCol(e.target.value)}>
              <option value="">— none —</option>
              {columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <select className="input w-20" value={filterOp} onChange={(e) => setFilterOp(e.target.value)}>
              {['=', '!=', '>', '<', 'contains'].map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        </label>
        <label className="text-xs text-slate-500">Value / Sort / Top N
          <div className="flex gap-1 mt-1">
            <input className="input" placeholder="value" value={filterVal}
              disabled={!filterCol} onChange={(e) => setFilterVal(e.target.value)} />
            <select className="input w-20" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="desc">DESC</option>
              <option value="asc">ASC</option>
            </select>
            <input className="input w-16" placeholder="N" value={topN} onChange={(e) => setTopN(e.target.value)} />
          </div>
        </label>
        <button className="btn-primary justify-center" disabled={!datasetId || busy} onClick={render}>
          {busy ? 'Rendering…' : 'Render Chart'}
        </button>
      </div>

      {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 mb-4">{error}</div>}

      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <ChartCard
              title={result.spec.title || `${result.chart_type.toUpperCase()} — ${result.spec.metric ?? 'count'} by ${result.spec.dimension ?? '—'}`}
              chartType={result.chart_type}
              data={result.result.data}
              dimension={result.result.dimension}
              metric={result.result.metric}
              insight={result.insight}
            />
          </div>
          <div className="card p-5 flex flex-col">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Query result</h3>
            <div className="overflow-auto max-h-72 flex-1">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left text-slate-500">
                    {result.result.data[0] && Object.keys(result.result.data[0]).map((k) => (
                      <th key={k} className="px-3 py-2 font-medium">{k.replace(/_/g, ' ')}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.result.data.map((row, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      {Object.values(row).map((v, j) => (
                        <td key={j} className="px-3 py-2 whitespace-nowrap">
                          {typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : String(v ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button className="btn-secondary mt-3" disabled={added} onClick={handleAddToDashboard}>
              {added ? '✓ Added to Dashboard' : '+ Add to Dashboard'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
