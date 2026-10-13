import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type {
  ForecastTrainResponse,
  ForecastExplanationResponse,
  ForecastCandidateMetric,
} from '../../types'
import BusinessMetricsCard from '../business/BusinessMetricsCard'

interface ForecastingAnalyticsTabProps {
  trainResult: ForecastTrainResponse | null
  explanation: ForecastExplanationResponse | null
  selectedMetricCandidate?: ForecastCandidateMetric
  className?: string
}

export default function ForecastingAnalyticsTab({
  trainResult,
  explanation,
  selectedMetricCandidate,
  className = '',
}: ForecastingAnalyticsTabProps) {
  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-3 ${className}`}>
        <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center text-2xl">
          📊
        </div>
        <h3 className="text-sm font-bold text-slate-800">No Forecasting Evaluation Available</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Generate a time-series forecast from the Overview tab to view historical backtest validation, model comparisons, and empirical interval coverage.
        </p>
      </div>
    )
  }

  const unit = selectedMetricCandidate?.unit || null

  // Backtest chart data
  const backtestChartData = (trainResult.backtest_data || []).map((b) => ({
    date: b.date,
    actual: b.actual,
    predicted: b.predicted,
    residual: b.residual,
  }))

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. Chronological Backtest Evaluation Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>⏮️</span> Chronological Backtesting & Holdout Fit
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Strict chronological out-of-sample evaluation: models train only on past data to predict future test points.
            </p>
          </div>
          <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded">
            {backtestChartData.length} Backtest Evaluation Windows
          </span>
        </div>

        {/* Business Metrics Grid */}
        <BusinessMetricsCard
          type="forecasting"
          metrics={trainResult.best_model.metrics}
          targetName={trainResult.metric_column}
          unit={unit}
          frequency={trainResult.frequency}
          vsBaselinePct={trainResult.best_model.vs_naive_pct}
        />

        {/* Backtest Line Chart */}
        {backtestChartData.length > 0 && (
          <div className="space-y-3 pt-3 border-t border-slate-100">
            <h4 className="text-xs font-bold text-slate-800">
              Holdout Actual vs Model Predicted Fit
            </h4>

            <div className="h-64 w-full rounded-lg border border-slate-200 p-2 bg-slate-50/50">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={backtestChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#64748b" fontSize={10} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      borderColor: '#cbd5e1',
                      borderRadius: 8,
                      fontSize: 11,
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Actual Holdout"
                  />
                  <Line
                    type="monotone"
                    dataKey="predicted"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    strokeDasharray="3 3"
                    dot={{ r: 3 }}
                    name="Model Predicted"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-900 leading-relaxed">
              <strong>What to notice:</strong> The model tracks actual historical values without data leakage from future periods. Lower deviation reflects higher predictive stability. MAE is ±{trainResult.best_model.metrics.mae} {unit || ''}.
            </div>
          </div>
        )}
      </div>

      {/* 2. Time-Series Decomposition & Trajectory Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="border-b border-slate-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>🔍</span> Time-Series Trajectory & Extrapolation Strategy
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Underlying pattern analysis, historical trend momentum, and algorithmic selection rationale.
          </p>
        </div>

        {explanation ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
              <span className="text-[11px] font-bold text-brand-700 uppercase tracking-wider block">
                Extrapolation Methodology
              </span>
              <p className="text-slate-700 leading-relaxed">
                {explanation.selection_reason}
              </p>
              <div className="pt-2 border-t border-slate-200 flex justify-between text-[11px] text-slate-500">
                <span>Historical Trend: <strong className="text-slate-800 capitalize">{explanation.historical_trend}</strong></span>
                <span>Reference Baseline: <strong className="text-slate-800">{explanation.recent_observation_reference != null ? explanation.recent_observation_reference.toLocaleString() : '—'} {unit || ''}</strong></span>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
              <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider block">
                Interpretability Disclosures
              </span>
              <ul className="space-y-1.5 text-slate-600">
                {explanation.limitations.map((lim, idx) => (
                  <li key={idx} className="flex items-start gap-1.5">
                    <span className="text-slate-400 mt-0.5">•</span>
                    <span>{lim}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600">
            <strong>Model Extrapolation:</strong> {trainResult.best_model.selection_reason || `Using ${trainResult.best_model.algorithm} for forward extrapolation.`}
          </div>
        )}
      </div>

      {/* 3. Forecast Intervals & Empirical Coverage Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="border-b border-slate-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>🛡️</span> Forecast Uncertainty Intervals & Coverage Evaluation
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Empirical validation of prediction intervals against backtest holdout observations.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1">
            <span className="text-[10px] text-slate-500 uppercase font-medium block">
              80% Nominal Interval
            </span>
            <div className="text-xl font-bold text-slate-900">
              {trainResult.best_model.empirical_coverage_80 !== null && trainResult.best_model.empirical_coverage_80 !== undefined
                ? `${trainResult.best_model.empirical_coverage_80}% Empirical`
                : '80% Theoretical Band'}
            </div>
            <span className="text-[10px] text-slate-500">
              {trainResult.best_model.coverage_sample_size
                ? `Evaluated on ${trainResult.best_model.coverage_sample_size} samples`
                : 'Residual dispersion'}
            </span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1">
            <span className="text-[10px] text-slate-500 uppercase font-medium block">
              95% Nominal Interval
            </span>
            <div className="text-xl font-bold text-slate-900">
              {trainResult.best_model.empirical_coverage_95 !== null && trainResult.best_model.empirical_coverage_95 !== undefined
                ? `${trainResult.best_model.empirical_coverage_95}% Empirical`
                : '95% Theoretical Band'}
            </div>
            <span className="text-[10px] text-slate-500">
              Wide conservative bounds
            </span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1">
            <span className="text-[10px] text-slate-500 uppercase font-medium block">
              Evaluation Methodology
            </span>
            <div className="text-sm font-bold text-slate-900 truncate">
              {trainResult.best_model.backtest_strategy || 'Rolling-Origin Backtest'}
            </div>
            <span className="text-[10px] text-slate-500">
              Out-of-sample residual variance
            </span>
          </div>
        </div>

        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 leading-relaxed">
          <strong>Important Limitation:</strong> Empirical interval coverage demonstrates how often historical test observations fell inside the uncertainty bands. Historical coverage does not guarantee future coverage under shifting market or operational conditions.
        </div>
      </div>
    </div>
  )
}
