import type {
  ForecastTrainResponse,
  ForecastExplanationResponse,
  ForecastCandidateMetric,
} from '../../types'

interface ForecastingTechnicalTabProps {
  trainResult: ForecastTrainResponse | null
  explanation: ForecastExplanationResponse | null
  selectedMetricCandidate?: ForecastCandidateMetric
  className?: string
}

export default function ForecastingTechnicalTab({
  trainResult,
  explanation,
  selectedMetricCandidate,
  className = '',
}: ForecastingTechnicalTabProps) {
  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-3 ${className}`}>
        <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center text-2xl">
          ⚙️
        </div>
        <h3 className="text-sm font-bold text-slate-800">No Forecasting Technical Details Available</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Generate a time-series forecast to audit candidate algorithms, full projection schedules, and empirical intervals.
        </p>
      </div>
    )
  }

  const unit = selectedMetricCandidate?.unit || ''

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. Candidate Forecasting Models Comparison Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>🔬</span> Candidate Forecaster Benchmarks
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Holdout error metrics evaluated on historical test splits against naive benchmarks.
            </p>
          </div>
          <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded">
            {trainResult.candidate_models.length} Forecasters Backtested
          </span>
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-xs text-left text-slate-700">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Algorithm</th>
                <th className="py-2.5 px-3">Holdout MAE</th>
                <th className="py-2.5 px-3">RMSE</th>
                <th className="py-2.5 px-3">WAPE</th>
                <th className="py-2.5 px-3">vs Naive Baseline</th>
                <th className="py-2.5 px-3">Duration</th>
                <th className="py-2.5 px-3">Selection</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {trainResult.candidate_models.map((cand) => (
                <tr
                  key={cand.algorithm}
                  className={cand.is_best ? 'bg-emerald-50/50 font-semibold' : 'hover:bg-slate-50/80'}
                >
                  <td className="py-2.5 px-3 text-slate-900">
                    {cand.algorithm}
                    {cand.is_baseline && (
                      <span className="ml-1.5 text-[10px] text-slate-500 font-normal">
                        (Baseline)
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 font-mono">
                    {cand.metrics.mae?.toLocaleString() ?? '-'}
                  </td>
                  <td className="py-2.5 px-3 font-mono">
                    {cand.metrics.rmse?.toLocaleString() ?? '-'}
                  </td>
                  <td className="py-2.5 px-3 font-mono">
                    {cand.metrics.wape !== null && cand.metrics.wape !== undefined
                      ? `${cand.metrics.wape}%`
                      : '-'}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[11px]">
                    {cand.vs_naive_pct !== null && cand.vs_naive_pct !== undefined ? (
                      <span
                        className={
                          cand.vs_naive_pct > 0
                            ? 'text-emerald-700 font-bold'
                            : 'text-slate-500'
                        }
                      >
                        {cand.vs_naive_pct > 0 ? `+${cand.vs_naive_pct}%` : `${cand.vs_naive_pct}%`}
                      </span>
                    ) : (
                      <span className="text-slate-400">Baseline</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px]">
                    {cand.training_time_ms ? `${cand.training_time_ms}ms` : '-'}
                  </td>
                  <td className="py-2.5 px-3">
                    {cand.is_best ? (
                      <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                        ★ Selected Best
                      </span>
                    ) : (
                      <span className="text-slate-400 text-[11px]">Evaluated</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 1.5 Time-Series Decomposition Details */}
      {explanation && (
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>🔍</span> Algorithmic Extrapolation & Trajectory Rationale
          </h2>
          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-2">
            <span className="font-bold text-brand-700 block">Extrapolation Strategy:</span>
            <p className="text-slate-700 leading-relaxed">{explanation.selection_reason}</p>
            {explanation.limitations.length > 0 && (
              <div className="pt-2 border-t border-slate-200 text-[11px] text-slate-500 space-y-0.5">
                <span className="font-semibold text-slate-600 block">Technical Disclosures:</span>
                {explanation.limitations.map((lim, idx) => (
                  <div key={idx}>• {lim}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. Full Forecast Projection Schedule Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>📅</span> Full Forecast Projection Schedule
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Exact point estimates and uncertainty bands for all {trainResult.forecast_data.length} future periods. Starting from {trainResult.historical_end_date}.
            </p>
          </div>
          <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded">
            {trainResult.horizon} {trainResult.frequency} intervals
          </span>
        </div>

        {trainResult.interval_notes && (
          <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200">
            ℹ {trainResult.interval_notes}
          </div>
        )}

        <div className="overflow-x-auto max-h-72 rounded-lg border border-slate-200">
          <table className="w-full text-xs text-left text-slate-700">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200 sticky top-0">
              <tr>
                <th className="py-2 px-3">Period Date</th>
                <th className="py-2 px-3">Point Forecast</th>
                <th className="py-2 px-3">80% Interval [Lower – Upper]</th>
                <th className="py-2 px-3">95% Interval [Lower – Upper]</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {trainResult.forecast_data.map((fp) => (
                <tr key={fp.date} className="hover:bg-slate-50/80">
                  <td className="py-2 px-3 text-slate-900 font-sans font-medium">{fp.date}</td>
                  <td className="py-2 px-3 text-emerald-700 font-bold">
                    {fp.forecast.toLocaleString()} {unit}
                  </td>
                  <td className="py-2 px-3 text-slate-600">
                    [{fp.lower_80?.toLocaleString() ?? '-'} – {fp.upper_80?.toLocaleString() ?? '-'}]
                  </td>
                  <td className="py-2 px-3 text-slate-600">
                    [{fp.lower_95?.toLocaleString() ?? '-'} – {fp.upper_95?.toLocaleString() ?? '-'}]
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. Model Architecture & Pipeline Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>⚙️</span> Backtest & Aggregation Configuration
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Backtest Strategy:</span>
              <strong className="text-slate-800">{trainResult.best_model.backtest_strategy || 'Rolling-Origin Backtest'}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Evaluation Windows:</span>
              <strong className="text-slate-800">{trainResult.evaluation_windows || trainResult.backtest_data.length} Windows</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Frequency Grain:</span>
              <strong className="text-slate-800 capitalize">{trainResult.frequency}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Aggregation Method:</span>
              <strong className="text-slate-800">{trainResult.aggregation}</strong>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Total Historical Periods:</span>
              <strong className="text-slate-800 font-mono">{trainResult.total_historical_periods}</strong>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>📦</span> Model Store & Artifact Metadata
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Model Identifier:</span>
              <strong className="text-slate-800 font-mono text-[11px] truncate max-w-[200px]" title={trainResult.model_id}>
                {trainResult.model_id}
              </strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Dataset Version:</span>
              <strong className="text-slate-800 font-mono">v{trainResult.dataset_version}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Winning Algorithm:</span>
              <strong className="text-slate-800">{trainResult.best_model.algorithm}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Historical Anchor Date:</span>
              <strong className="text-slate-800 font-mono">{trainResult.historical_end_date}</strong>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Persistence Store:</span>
              <strong className="text-slate-800 font-mono">DuckDB Aggregates + Scikit-Learn Model</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
