import { useState } from 'react'
import type { DataQualitySummary, ColumnInfoItem } from '../../types'

interface DataQualityCardProps {
  dataQuality?: DataQualitySummary | null
  columnsInfo?: ColumnInfoItem[] | null
  rowCount?: number
  className?: string
}

export default function DataQualityCard({
  dataQuality,
  columnsInfo,
  rowCount,
  className = '',
}: DataQualityCardProps) {
  const [showColumns, setShowColumns] = useState(false)

  if (!dataQuality) return null

  const gradeColors: Record<string, { bg: string; text: string; border: string }> = {
    Excellent: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
    Good: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
    'Needs Attention': { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
    Insufficient: { bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/30' },
  }

  const gradeStyle = gradeColors[dataQuality.quality_grade] || gradeColors.Good
  const colsWithNulls = (columnsInfo || []).filter((c) => c.null_count > 0)

  return (
    <div className={`p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3 ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">Data Quality & Health</span>
          <span
            className={`px-2 py-0.5 rounded text-[11px] font-bold border ${gradeStyle.bg} ${gradeStyle.text} ${gradeStyle.border}`}
          >
            {dataQuality.quality_grade} Quality ({dataQuality.complete_rows_pct}% Complete)
          </span>
        </div>
        {colsWithNulls.length > 0 && (
          <button
            type="button"
            onClick={() => setShowColumns(!showColumns)}
            className="text-[11px] text-brand-400 hover:text-brand-300 transition-colors cursor-pointer"
          >
            {showColumns ? 'Hide Details' : `View Missing Columns (${colsWithNulls.length})`}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <div className="p-2.5 rounded-lg bg-slate-800/50 border border-slate-800">
          <span className="text-[10px] text-slate-400 block uppercase">Completeness</span>
          <strong className="text-white text-sm font-bold">{dataQuality.complete_rows_pct}%</strong>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-800/50 border border-slate-800">
          <span className="text-[10px] text-slate-400 block uppercase">Total Rows</span>
          <strong className="text-white text-sm font-bold">
            {(rowCount || dataQuality.total_rows).toLocaleString()}
          </strong>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-800/50 border border-slate-800">
          <span className="text-[10px] text-slate-400 block uppercase">Total Columns</span>
          <strong className="text-white text-sm font-bold">{dataQuality.total_columns}</strong>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-800/50 border border-slate-800">
          <span className="text-[10px] text-slate-400 block uppercase">Cols with Nulls</span>
          <strong className={dataQuality.columns_with_nulls > 0 ? 'text-amber-400 text-sm font-bold' : 'text-emerald-400 text-sm font-bold'}>
            {dataQuality.columns_with_nulls}
          </strong>
        </div>
      </div>

      {dataQuality.quality_notes && dataQuality.quality_notes.length > 0 && (
        <div className="text-[11px] text-slate-400 space-y-0.5">
          {dataQuality.quality_notes.map((note: string, idx: number) => (
            <div key={idx} className="flex items-start gap-1.5">
              <span className="text-slate-500">•</span>
              <span>{note}</span>
            </div>
          ))}
        </div>
      )}

      {showColumns && colsWithNulls.length > 0 && (
        <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
          <div className="text-[11px] font-semibold text-slate-300">Columns with Missing Values:</div>
          <div className="max-h-40 overflow-y-auto space-y-1 text-[11px]">
            {colsWithNulls.map((col) => (
              <div
                key={col.name}
                className="flex items-center justify-between p-1.5 rounded bg-slate-950/50 border border-slate-800/80"
              >
                <div className="flex items-center gap-2">
                  <span className="text-slate-200 font-medium">{col.display_name}</span>
                  <span className="text-[10px] text-slate-500 font-mono">({col.dtype || col.semantic_type})</span>
                </div>
                <div className="text-amber-400 font-mono text-[10px]">
                  {col.null_count.toLocaleString()} missing ({col.null_percentage}%)
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
