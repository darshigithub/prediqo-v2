import type {
  ForecastTrainResponse,
  ForecastExplanationResponse,
  ForecastCandidateMetric,
} from '../../types'
import AIExplanationCard from '../business/AIExplanationCard'

interface ForecastingAIExplanationTabProps {
  datasetId: string
  trainResult: ForecastTrainResponse | null
  explanation: ForecastExplanationResponse | null
  selectedMetricCandidate?: ForecastCandidateMetric
  activeModelId?: string
  className?: string
}

export default function ForecastingAIExplanationTab({
  datasetId,
  trainResult,
  explanation,
  selectedMetricCandidate,
  activeModelId,
  className = '',
}: ForecastingAIExplanationTabProps) {
  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-3 ${className}`}>
        <div className="w-12 h-12 mx-auto rounded-2xl bg-brand-50 flex items-center justify-center text-2xl">
          ✦
        </div>
        <h3 className="text-sm font-bold text-slate-800">No Forecast Model Trained for AI Explanation</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Please configure and generate a time-series forecast first to produce an audited business narrative.
        </p>
      </div>
    )
  }

  const unit = selectedMetricCandidate?.unit || undefined

  // Calculate aggregates for structured forecast evidence payload
  const totalForecast = trainResult.forecast_data.reduce(
    (acc, curr) => acc + (curr.forecast || 0),
    0
  )
  const avgForecast =
    trainResult.forecast_data.length > 0 ? totalForecast / trainResult.forecast_data.length : 0

  const lowerBoundMean =
    trainResult.forecast_data.reduce(
      (acc, p) => acc + (p.lower_95 ?? p.lower_80 ?? p.forecast),
      0
    ) / (trainResult.forecast_data.length || 1)

  const upperBoundMean =
    trainResult.forecast_data.reduce(
      (acc, p) => acc + (p.upper_95 ?? p.upper_80 ?? p.forecast),
      0
    ) / (trainResult.forecast_data.length || 1)

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Intro Header */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-brand-500 animate-pulse" />
              <span className="text-xs font-bold text-brand-700 uppercase tracking-wider">
                Audited Forecast Narrative Layer
              </span>
            </div>
            <h2 className="text-lg font-bold text-slate-900 mt-1">
              AI-Powered Explanation for {trainResult.metric_column} Forecast
            </h2>
            <p className="text-xs text-slate-500 mt-0.5 max-w-2xl">
              Translates historical trend momentum, baseline uplift, and uncertainty bounds into plain business language. Grounded in authoritative metrics.
            </p>
          </div>

          <div className="text-right text-xs text-slate-500">
            <div>Algorithm: <strong className="text-slate-800">{trainResult.best_model.algorithm}</strong></div>
            <div>Dataset Version: <strong className="font-mono text-slate-800">v{trainResult.dataset_version}</strong></div>
          </div>
        </div>
      </div>

      {/* Main AI Explanation Card Component */}
      <AIExplanationCard
        type="forecast"
        forecastPayload={{
          model_id: activeModelId || trainResult.model_id,
          dataset_id: datasetId,
          metric_column: trainResult.metric_column,
          date_column: trainResult.date_column,
          frequency: trainResult.frequency,
          horizon: trainResult.horizon,
          aggregation: trainResult.aggregation,
          unit: unit,
          historical_summary: explanation
            ? {
                mean_value: explanation.recent_observation_reference,
                trend: explanation.historical_trend,
              }
            : {},
          forecast_summary: {
            forecast_mean: avgForecast,
            forecast_total: totalForecast,
            trajectory: explanation?.historical_trend || 'stable',
          },
          backtest_metrics: trainResult.best_model.metrics,
          intervals: {
            lower_bound_mean: lowerBoundMean,
            upper_bound_mean: upperBoundMean,
            nominal_coverage_pct: 95,
          },
          limitations: explanation?.limitations || [],
        }}
      />
    </div>
  )
}
