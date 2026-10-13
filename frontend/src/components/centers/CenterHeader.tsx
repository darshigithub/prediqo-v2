import { Link } from 'react-router-dom'
import DatasetPicker from '../DatasetPicker'

export type CenterType = 'prediction' | 'forecasting'

interface CenterHeaderProps {
  currentCenter: CenterType
  title: string
  subtitle: string
  datasetId: string
  onDatasetChange: (id: string) => void
  activeModelLabel?: string | null
  badgeColor?: 'brand' | 'emerald' | 'amber'
  actionSlot?: React.ReactNode
}

export default function CenterHeader({
  currentCenter,
  title,
  subtitle,
  datasetId,
  onDatasetChange,
  activeModelLabel,
  badgeColor = 'brand',
  actionSlot,
}: CenterHeaderProps) {
  const badgeClasses = {
    brand: 'bg-brand-50 text-brand-700 border-brand-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
  }[badgeColor]

  return (
    <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
      {/* Top Title & Center Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-600 text-lg font-bold shadow-sm">
              {currentCenter === 'prediction' ? '⚡' : '📈'}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                  {title}
                </h1>
                {activeModelLabel && (
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badgeClasses}`}
                  >
                    {activeModelLabel}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
            </div>
          </div>
        </div>

        {/* Center Switcher Buttons */}
        <div className="flex items-center gap-2">
          <div className="inline-flex p-1 bg-slate-100 rounded-lg border border-slate-200 text-xs font-medium">
            <Link
              to="/prediction"
              className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                currentCenter === 'prediction'
                  ? 'bg-white text-brand-700 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>⚡</span>
              <span>Prediction Center</span>
            </Link>
            <Link
              to="/forecasting"
              className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                currentCenter === 'forecasting'
                  ? 'bg-white text-brand-700 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>📈</span>
              <span>Forecasting Center</span>
            </Link>
          </div>

          <Link
            to="/decisions"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-colors shadow-sm"
            title="Open Decision Center"
          >
            <span>⚖️</span>
            <span>Decisions</span>
          </Link>
        </div>
      </div>

      {/* Dataset Picker Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
        <div className="flex items-center gap-2.5 flex-1 min-w-[280px]">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            Active Dataset:
          </span>
          <DatasetPicker
            value={datasetId}
            onChange={onDatasetChange}
            theme="light"
            className="max-w-md text-xs font-semibold"
          />
        </div>

        {actionSlot && <div className="flex items-center gap-2">{actionSlot}</div>}
      </div>
    </div>
  )
}
