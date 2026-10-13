import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export const PALETTE = ['#4f46e5', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']

function formatNumber(v: unknown): string {
  if (typeof v === 'number') {
    return Number.isInteger(v) ? v.toLocaleString('en-US') : v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  return String(v ?? '')
}

interface ChartProps {
  chartType: string
  data: Record<string, unknown>[]
  dimension?: string | null
  metric?: string | null
  height?: number
}

export default function Chart({ chartType, data, dimension, metric, height = 300 }: ChartProps) {
  const dim = dimension ?? (data.length > 0 ? Object.keys(data[0])[0] : null)
  const met = metric ?? (data.length > 0 ? Object.keys(data[0]).slice(-1)[0] : null)

  if (!data || data.length === 0 || !met) {
    return <div className="text-sm text-slate-400 py-10 text-center">No data to display</div>
  }

  if (chartType === 'kpi') {
    const value = data[0]?.[met] ?? data[0]?.metric
    return (
      <div className="flex items-center justify-center py-8" style={{ height }}>
        <span className="text-4xl font-bold text-brand-600">{formatNumber(value)}</span>
      </div>
    )
  }

  if (chartType === 'table') {
    return (
      <div className="overflow-auto max-h-80">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-left text-slate-500">
              {data[0] && Object.keys(data[0]).map((k) => (
                <th key={k} className="px-3 py-2 font-medium whitespace-nowrap">{k.replace(/_/g, ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                {Object.values(row).map((v, j) => (
                  <td key={j} className="px-3 py-2 whitespace-nowrap">{formatNumber(v)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const chartData = data.map((r) => ({
    ...r,
    [met]: typeof r[met] === 'number' ? r[met] : Number(r[met]) || 0,
  }))

  const axisStyle = { fontSize: 12, fill: '#64748b' }
  const tooltipFormatter = (v: unknown) => [formatNumber(v), met.replace(/_/g, ' ')]
  const tooltipContentStyle = {
    backgroundColor: '#0f172a',
    borderColor: '#334155',
    color: '#f8fafc',
    borderRadius: 8,
    fontSize: 12,
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  }

  if (chartType === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie data={chartData} dataKey={met} nameKey={dim ?? undefined} outerRadius="80%" innerRadius="45%">
            {chartData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
          </Pie>
          <Tooltip formatter={tooltipFormatter} contentStyle={tooltipContentStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (chartType === 'scatter') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey={dim ?? undefined} tick={axisStyle} />
          <YAxis tick={axisStyle} />
          <Tooltip formatter={tooltipFormatter} contentStyle={tooltipContentStyle} />
          <Scatter data={chartData} fill={PALETTE[0]} />
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  if (chartType === 'line') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey={dim ?? undefined} tick={axisStyle} />
          <YAxis tick={axisStyle} tickFormatter={(v) => formatNumber(v)} />
          <Tooltip formatter={tooltipFormatter} contentStyle={tooltipContentStyle} />
          <Line type="monotone" dataKey={met} stroke={PALETTE[0]} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (chartType === 'area') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={PALETTE[0]} stopOpacity={0.4} />
              <stop offset="95%" stopColor={PALETTE[0]} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey={dim ?? undefined} tick={axisStyle} />
          <YAxis tick={axisStyle} tickFormatter={(v) => formatNumber(v)} />
          <Tooltip formatter={tooltipFormatter} contentStyle={tooltipContentStyle} />
          <Area type="monotone" dataKey={met} stroke={PALETTE[0]} fill="url(#areaFill)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  // default: bar
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey={dim ?? undefined} tick={axisStyle} interval={0} angle={chartData.length > 6 ? -20 : 0}
          textAnchor={chartData.length > 6 ? 'end' : 'middle'} height={chartData.length > 6 ? 55 : 30} />
        <YAxis tick={axisStyle} tickFormatter={(v) => formatNumber(v)} />
        <Tooltip formatter={tooltipFormatter} contentStyle={tooltipContentStyle} />
        <Bar dataKey={met} fill={PALETTE[0]} radius={[6, 6, 0, 0]}>
          {chartData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
