import { useState } from 'react'
import type {
  ForecastFeasibilityResponse,
  ForecastCandidateMetric,
  ForecastModelListItem,
} from '../../types'

interface ForecastingConfigPanelProps {
  feasibility: ForecastFeasibilityResponse | null
  loadingFeasibility: boolean
  selectedDate: string
  onDateChange: (col: string) => void
  selectedMetric: string
  onMetricChange: (metric: string) => void
  selectedMetricCandidate?: ForecastCandidateMetric
  aggregation: string
  onAggregationChange: (agg: string) => void
  frequency: string
  onFrequencyChange: (freq: string) => void
  horizon: number
  onHorizonChange: (h: number) => void
  imputationMethod: string
  onImputationChange: (imp: string) => void
  training: boolean
  onTrain: () => void
  savedModels: ForecastModelListItem[]
  activeModelId: string
  onSelectSavedModel: (modelId: string) => void
  className?: string
}

export default function ForecastingConfigPanel({
  feasibility,
  loadingFeasibility,
  selectedDate,
  onDateChange,
  selectedMetric,
  onMetricChange,
  selectedMetricCandidate,
  aggregation,
  onAggregationChange,
  frequency,
  onFrequencyChange,
  horizon,
  onHorizonChange,
  imputationMethod,
  onImputationChange,
  training,
  onTrain,
  savedModels,
  activeModelId,
  onSelectSavedModel,
  className = '',
}: ForecastingConfigPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  if (loadingFeasibility) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4 ${className}`}>
        <div className="flex items-center gap-2 text-slate-500 text-xs">
          <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Assessing time-series continuity, dates, and metric aggregations...</span>
        </div>
      </div>
    )
  }

  if (!feasibility || !feasibility.forecasting_possible) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3 ${className}`}>
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs">
          <strong>Forecasting Not Feasible:</strong>
          <p className="mt-1">
            {feasibility?.missing_requirements?.[0] || 'Dataset lacks sufficient chronological date records or continuous numeric measures.'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Forecasting Setup Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
            <span>📈</span>
            <span>Forecasting Setup</span>
          </h2>
          <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
            v{feasibility.dataset_version}
          </span>
        </div>

        {/* 1. Date Column */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">
            Timeline / Date Column <span className="text-rose-500">*</span>
          </label>
          <select
            value={selectedDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium text-slate-800 shadow-sm focus:outline-none focus:border-brand-500"
          >
            {feasibility.recommended_date_columns.map((d) => (
              <option key={d.name} value={d.name}>
                {d.name} ({d.distinct_dates} distinct timestamps)
              </option>
            ))}
          </select>
        </div>

        {/* 2. Metric Column */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">
            Forecast Target Metric <span className="text-rose-500">*</span>
          </label>
          <select
            value={selectedMetric}
            onChange={(e) => onMetricChange(e.target.value)}
            className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium text-slate-800 shadow-sm focus:outline-none focus:border-brand-500"
          >
            {feasibility.recommended_metrics.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name} {m.unit ? `(${m.unit})` : ''} — {m.business_role}
              </option>
            ))}
          </select>
          {selectedMetricCandidate && (
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className="px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 font-semibold border border-brand-200 text-[10px]">
                {selectedMetricCandidate.business_role}
              </span>
              {selectedMetricCandidate.unit && (
                <span>Unit: <strong className="text-slate-700">{selectedMetricCandidate.unit}</strong></span>
              )}
            </div>
          )}
        </div>

        {/* 3. Aggregation & Frequency */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">
              Aggregation
            </label>
            <select
              value={aggregation}
              onChange={(e) => onAggregationChange(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
            >
              {(selectedMetricCandidate?.allowed_aggregations || ['SUM', 'AVG']).map((agg) => (
                <option key={agg} value={agg}>
                  {agg}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">
              Frequency Grain
            </label>
            <select
              value={frequency}
              onChange={(e) => onFrequencyChange(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
            >
              {feasibility.available_frequencies.map((freq) => (
                <option key={freq} value={freq}>
                  {freq.charAt(0).toUpperCase() + freq.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* 4. Forecast Horizon */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center text-xs">
            <label className="font-semibold text-slate-700">Forecast Horizon</label>
            <span className="font-mono text-brand-700 font-bold">
              {horizon} {frequency} periods
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={60}
            value={horizon}
            onChange={(e) => onHorizonChange(Number(e.target.value))}
            className="w-full accent-brand-600 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-slate-400">
            <span>1 period</span>
            <span>14 periods</span>
            <span>30 periods</span>
            <span>60 periods</span>
          </div>
        </div>

        {/* 5. Advanced Config Accordion */}
        <div className="pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center justify-between w-full text-xs font-semibold text-slate-600 hover:text-slate-900 cursor-pointer"
          >
            <span>Advanced Imputation Options</span>
            <span className="text-slate-400">{showAdvanced ? '▲' : '▼'}</span>
          </button>

          {showAdvanced && (
            <div className="mt-3 space-y-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">
                  Missing Period Imputation
                </label>
                <select
                  value={imputationMethod}
                  onChange={(e) => onImputationChange(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
                >
                  <option value="auto">Automatic (Linear Interpolate)</option>
                  <option value="forward_fill">Forward Fill (Last Known Value)</option>
                  <option value="zero">Zero Fill (Demand Gaps)</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* 6. Train/Forecast Action Button */}
        <button
          type="button"
          disabled={training || !selectedDate || !selectedMetric}
          onClick={onTrain}
          className="w-full py-2.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-xs transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer"
        >
          {training ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <span>Backtesting & Forecasting...</span>
            </>
          ) : (
            <>
              <span>📈</span>
              <span>Generate Time-Series Forecast</span>
            </>
          )}
        </button>
      </div>

      {/* Saved Forecasting Models */}
      {savedModels.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              Saved Forecasters ({savedModels.length})
            </span>
            <span className="text-[10px] text-slate-400 font-mono">Backtested</span>
          </div>

          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {savedModels.map((m) => {
              const isActive = activeModelId === m.model_id
              return (
                <div
                  key={m.model_id}
                  onClick={() => onSelectSavedModel(m.model_id)}
                  className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                    isActive
                      ? 'bg-brand-50 border-brand-400 text-brand-900 shadow-sm'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300'
                  }`}
                >
                  <div className="flex justify-between items-center mb-0.5">
                    <strong className="text-slate-900 font-semibold">{m.metric_column}</strong>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-brand-700 font-medium">
                      {m.algorithm}
                    </span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-500">
                    <span>
                      MAE: <strong className="text-slate-700">{m.mae}</strong>
                    </span>
                    <span className="capitalize">{m.frequency}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
