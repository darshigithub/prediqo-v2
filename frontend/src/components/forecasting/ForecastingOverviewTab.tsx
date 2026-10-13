import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
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
import { formatBusinessValue } from '../../utils/businessMetrics'
import ForecastInsightCard from '../business/ForecastInsightCard'
import BusinessMetricsCard from '../business/BusinessMetricsCard'
import DecisionChecklistCard from '../business/DecisionChecklistCard'

interface ForecastingOverviewTabProps {
  trainResult: ForecastTrainResponse | null
  explanation: ForecastExplanationResponse | null
  loadingExplanation: boolean
  selectedMetricCandidate?: ForecastCandidateMetric
  onNavigateTab: (tab: 'analytics' | 'explanation' | 'technical') => void
  className?: string
}

export default function ForecastingOverviewTab({
  trainResult,
  explanation,
  loadingExplanation,
  selectedMetricCandidate,
  onNavigateTab,
  className = '',
}: ForecastingOverviewTabProps) {
  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-4 ${className}`}>
        <div className="w-14 h-14 mx-auto rounded-2xl bg-brand-50 border border-brand-100 flex items-center justify-center text-3xl">
          📈
        </div>
        <div>
          <h3 className="text-base font-bold text-slate-900">Configure & Generate a Time-Series Forecast</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            Choose your timestamp column, numeric measure, frequency grain, and horizon in the configuration panel on the left, then click <strong>Generate Time-Series Forecast</strong>.
          </p>
        </div>
      </div>
    )
  }

  const unit = selectedMetricCandidate?.unit || null

  // Calculate metrics for summary cards
  const totalForecast = trainResult.forecast_data.reduce(
    (acc, curr) => acc + (curr.forecast || 0),
    0
  )
  const avgForecast =
    trainResult.forecast_data.length > 0 ? totalForecast / trainResult.forecast_data.length : 0
  const endForecast =
    trainResult.forecast_data.length > 0
      ? trainResult.forecast_data[trainResult.forecast_data.length - 1].forecast
      : 0

  // Combine historical and future forecast points for timeline chart
  const historicalSliced = trainResult.historical_data.slice(-40)
  const chartData = [
    ...historicalSliced.map((h) => ({
      date: h.date,
      actual: h.value,
      forecast: null,
      lower_95: null,
      upper_95: null,
      is_future: false,
    })),
    ...trainResult.forecast_data.map((f) => ({
      date: f.date,
      actual: null,
      forecast: f.forecast,
      lower_95: f.lower_95 ?? f.lower_80 ?? null,
      upper_95: f.upper_95 ?? f.upper_80 ?? null,
      is_future: true,
    })),
  ]

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. Stale-Data Alert Banner if data is historical */}
      {trainResult.is_stale && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 shadow-sm flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⏳</span>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-amber-800">
                Historical Data Freshness Notice
              </div>
              <p className="text-xs text-amber-700 mt-0.5 leading-relaxed">
                {trainResult.stale_warning ||
                  `The last observed timestamp in this dataset is ${trainResult.historical_end_date}. Projections extrapolate from this historical anchor point. For real-time operational forecasting, refresh or ingest latest records.`}
              </p>
            </div>
          </div>
          <Link
            to="/sources"
            className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs shadow-sm transition-colors whitespace-nowrap"
          >
            Refresh Dataset
          </Link>
        </div>
      )}

      {/* 2. Forecast Configuration Summary Banner */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
                Active Forecast Projection
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                {trainResult.best_model.algorithm}
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 mt-1">
              {trainResult.metric_column}{' '}
              {unit ? <span className="text-sm font-normal text-slate-500">({unit})</span> : ''} ·{' '}
              <span className="capitalize">{trainResult.frequency}</span> Forecast
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onNavigateTab('technical')}
              className="px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors flex items-center gap-1.5"
            >
              <span>Compare Models</span>
              <span>→</span>
            </button>
          </div>
        </div>

        {/* Configuration Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2 pt-3 border-t border-slate-100 text-xs">
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-[10px] text-slate-500 block uppercase font-medium">Timeline Column</span>
            <strong className="text-slate-800 font-mono truncate block">{trainResult.date_column}</strong>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-[10px] text-slate-500 block uppercase font-medium">Aggregation</span>
            <strong className="text-slate-800">{trainResult.aggregation}</strong>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-[10px] text-slate-500 block uppercase font-medium">Horizon</span>
            <strong className="text-slate-800 font-mono">{trainResult.horizon} periods</strong>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-[10px] text-slate-500 block uppercase font-medium">Historical Points</span>
            <strong className="text-slate-800 font-mono">{trainResult.total_historical_periods}</strong>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-[10px] text-slate-500 block uppercase font-medium">Historical Start</span>
            <strong className="text-slate-800 font-mono text-[11px] truncate block">{trainResult.historical_start_date}</strong>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-[10px] text-slate-500 block uppercase font-medium">Last Observed Date</span>
            <strong className="text-slate-800 font-mono text-[11px] truncate block">{trainResult.historical_end_date}</strong>
          </div>
        </div>
      </div>

      {/* 3. Executive Forecast Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm space-y-1">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
            Projected Average
          </span>
          <div className="text-2xl font-extrabold text-slate-900">
            {formatBusinessValue(avgForecast, unit)}
          </div>
          <span className="text-[11px] text-slate-500">
            per {trainResult.frequency} period
          </span>
        </div>

        {trainResult.aggregation === 'SUM' && (
          <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
              Projected Total ({trainResult.horizon} Periods)
            </span>
            <div className="text-2xl font-extrabold text-brand-700">
              {formatBusinessValue(totalForecast, unit)}
            </div>
            <span className="text-[11px] text-slate-500">
              cumulative horizon volume
            </span>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm space-y-1">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
            End-of-Horizon Projection
          </span>
          <div className="text-2xl font-extrabold text-slate-900">
            {formatBusinessValue(endForecast, unit)}
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            at period +{trainResult.horizon}
          </span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm space-y-1">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
            Holdout Backtest Error (MAE)
          </span>
          <div className="text-2xl font-extrabold text-slate-900">
            ±{trainResult.best_model.metrics.mae?.toLocaleString() || '-'} {unit || ''}
          </div>
          <span className="text-[11px] text-emerald-700 font-semibold">
            {trainResult.best_model.vs_naive_pct
              ? `${trainResult.best_model.vs_naive_pct > 0 ? '+' : ''}${trainResult.best_model.vs_naive_pct}% vs Naive Baseline`
              : 'Evaluated vs Naive Baseline'}
          </span>
        </div>
      </div>

      {/* 4. Main Historical and Future Timeline Chart */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>📊</span> Historical Observations & Future Horizon Projection
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Historical actuals shown in solid cyan. Projected future forecast shown in dashed emerald with 95% uncertainty band.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-100 text-slate-700 font-medium">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500" /> Historical Anchor: {trainResult.historical_end_date}
            </span>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
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
              <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
              {/* 95% Interval Band */}
              <Area
                type="monotone"
                dataKey="upper_95"
                stroke="none"
                fill="#6366f1"
                fillOpacity={0.12}
                name="95% Upper Bound"
              />
              <Area
                type="monotone"
                dataKey="lower_95"
                stroke="none"
                fill="#ffffff"
                fillOpacity={1.0}
                name="95% Lower Bound"
              />
              {/* Historical Observations */}
              <Line
                type="monotone"
                dataKey="actual"
                stroke="#0ea5e9"
                strokeWidth={2.5}
                dot={{ r: 2.5 }}
                name="Historical Actual"
              />
              {/* Future Forecast */}
              <Line
                type="monotone"
                dataKey="forecast"
                stroke="#10b981"
                strokeWidth={2.5}
                strokeDasharray="4 4"
                dot={{ r: 3, fill: '#10b981' }}
                name="Projected Forecast"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {trainResult.interval_notes && (
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600">
            ℹ <strong>Uncertainty Bounds:</strong> {trainResult.interval_notes}. Forecast intervals represent statistical distribution bounds under historical assumptions, not guaranteed future ranges.
          </div>
        )}
      </div>

      {/* 5. Executive Interpretation & Backtest Metrics */}
      <div className="space-y-4">
        {loadingExplanation && (
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-500 flex items-center gap-2">
            <div className="w-3.5 h-3.5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            <span>Analyzing time-series trajectory and generating executive forecast summary...</span>
          </div>
        )}

        <ForecastInsightCard
          trainResult={trainResult}
          explanation={explanation}
          unit={unit}
        />

        <BusinessMetricsCard
          type="forecasting"
          metrics={trainResult.best_model.metrics}
          targetName={trainResult.metric_column}
          unit={unit}
          frequency={trainResult.frequency}
          vsBaselinePct={trainResult.best_model.vs_naive_pct}
        />
      </div>

      {/* 6. Actionable Next Steps Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <button
          type="button"
          onClick={() => onNavigateTab('analytics')}
          className="p-4 rounded-xl bg-white border border-slate-200/80 hover:border-brand-300 hover:shadow-sm text-left transition-all space-y-1 group cursor-pointer"
        >
          <div className="flex items-center justify-between text-xs font-bold text-slate-900 group-hover:text-brand-600">
            <span>Explore Analytics</span>
            <span>→</span>
          </div>
          <p className="text-[11px] text-slate-500">
            Inspect backtest holdout fit, candidate model benchmarks, and interval coverage.
          </p>
        </button>

        <button
          type="button"
          onClick={() => onNavigateTab('explanation')}
          className="p-4 rounded-xl bg-white border border-slate-200/80 hover:border-brand-300 hover:shadow-sm text-left transition-all space-y-1 group cursor-pointer"
        >
          <div className="flex items-center justify-between text-xs font-bold text-slate-900 group-hover:text-brand-600">
            <span>Read AI Explanation</span>
            <span>→</span>
          </div>
          <p className="text-[11px] text-slate-500">
            Generate executive summaries and plain-language trajectory analysis with Ollama or Cloud LLMs.
          </p>
        </button>

        <Link
          to="/decisions"
          className="p-4 rounded-xl bg-gradient-to-br from-brand-50 to-indigo-50 border border-brand-200/80 hover:border-brand-300 hover:shadow-sm text-left transition-all space-y-1 group"
        >
          <div className="flex items-center justify-between text-xs font-bold text-brand-900">
            <span>Evaluate in Decision Center</span>
            <span>⚖️ →</span>
          </div>
          <p className="text-[11px] text-brand-700">
            Apply automated inventory, spike detection, and operational capacity rules to this forecast.
          </p>
        </Link>
      </div>

      {/* 7. Operational Checklist */}
      <DecisionChecklistCard type="forecasting" />
    </div>
  )
}
