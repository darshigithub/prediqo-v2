import type { ReactNode } from 'react'
import Chart from '../charts/Chart'

interface ChartCardProps {
  title: string
  chartType: string
  data: Record<string, unknown>[]
  dimension?: string | null
  metric?: string | null
  insight?: string | null
  height?: number
  actions?: ReactNode
}

export default function ChartCard({
  title, chartType, data, dimension, metric, insight, height, actions,
}: ChartCardProps) {
  return (
    <div className="card p-5 flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
        {actions}
      </div>
      <div className="flex-1">
        <Chart chartType={chartType} data={data} dimension={dimension} metric={metric} height={height ?? 300} />
      </div>
      {insight && (
        <p className="mt-3 text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2 border border-slate-100">
          💡 {insight}
        </p>
      )}
    </div>
  )
}
