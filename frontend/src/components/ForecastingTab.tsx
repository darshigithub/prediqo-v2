import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  getForecastFeasibility,
  trainForecastModel,
  listForecastModels,
  getForecastModel,
  getForecastExplanation,
} from '../services/api'
import type {
  ForecastFeasibilityResponse,
  ForecastTrainResponse,
  ForecastModelListItem,
  ForecastExplanationResponse,
} from '../types'
import DataQualityCard from './business/DataQualityCard'
import BusinessMetricsCard from './business/BusinessMetricsCard'
import ForecastInsightCard from './business/ForecastInsightCard'
import DecisionChecklistCard from './business/DecisionChecklistCard'
import AIExplanationCard from './business/AIExplanationCard'


interface ForecastingTabProps {
  datasetId: string
}

export default function ForecastingTab({ datasetId }: ForecastingTabProps) {
  const [feasibility, setFeasibility] = useState<ForecastFeasibilityResponse | null>(null)
  const [loadingFeas, setLoadingFeas] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Configuration
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [selectedMetric, setSelectedMetric] = useState<string>('')
  const [frequency, setFrequency] = useState<string>('daily')
  const [aggregation, setAggregation] = useState<string>('SUM')
  const [horizon, setHorizon] = useState<number>(14)
  const [imputationMethod, setImputationMethod] = useState<string>('auto')
  const [showAdvancedConfig, setShowAdvancedConfig] = useState<boolean>(false)

  // Training state
  const [training, setTraining] = useState<boolean>(false)
  const [trainResult, setTrainResult] = useState<ForecastTrainResponse | null>(null)
  const [savedModels, setSavedModels] = useState<ForecastModelListItem[]>([])
  const [activeModelId, setActiveModelId] = useState<string>('')

  // Explainability state
  const [forecastExplanation, setForecastExplanation] = useState<ForecastExplanationResponse | null>(null)
  const [loadingForecastExp, setLoadingForecastExp] = useState<boolean>(false)

  // View toggles
  const [chartView, setChartView] = useState<'forecast' | 'backtest'>('forecast')
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false)

  // Load feasibility and saved models on dataset change
  useEffect(() => {
    if (!datasetId) {
      setFeasibility(null)
      setTrainResult(null)
      return
    }

    setLoadingFeas(true)
    setError(null)
    setTrainResult(null)

    getForecastFeasibility(datasetId)
      .then((res) => {
        setFeasibility(res)
        if (res.recommended_date_columns.length > 0) {
          setSelectedDate(res.recommended_date_columns[0].name)
        }
        if (res.recommended_metrics.length > 0) {
          setSelectedMetric(res.recommended_metrics[0].name)
          setAggregation(res.recommended_metrics[0].recommended_aggregation || 'SUM')
        }
      })
      .catch((err) => {
        setError(err.message || 'Failed to check forecasting feasibility.')
      })
      .finally(() => {
        setLoadingFeas(false)
      })

    listForecastModels(datasetId)
      .then((res) => setSavedModels(res.models || []))
      .catch(() => setSavedModels([]))
  }, [datasetId])

  // Update aggregation recommendation when metric changes
  useEffect(() => {
    if (!feasibility || !selectedMetric) return
    const m = feasibility.recommended_metrics.find((x) => x.name === selectedMetric)
    if (m) {
      setAggregation(m.recommended_aggregation || 'SUM')
    }
  }, [selectedMetric, feasibility])

  const selectedMetricCandidate = feasibility?.recommended_metrics.find(
    (x) => x.name === selectedMetric
  )

  const handleTrainForecast = async () => {
    if (!datasetId || !selectedDate || !selectedMetric) return
    setTraining(true)
    setError(null)
    setForecastExplanation(null)

    try {
      const res = await trainForecastModel({
        dataset_id: datasetId,
        date_column: selectedDate,
        metric_column: selectedMetric,
        frequency,
        aggregation,
        horizon: Number(horizon) || 14,
        imputation_method: imputationMethod === 'auto' ? undefined : imputationMethod,
      })
      setTrainResult(res)
      setActiveModelId(res.model_id)

      // Refresh saved models
      const updated = await listForecastModels(datasetId)
      setSavedModels(updated.models || [])

      // Fetch forecast explanation
      setLoadingForecastExp(true)
      try {
        const exp = await getForecastExplanation(res.model_id)
        setForecastExplanation(exp)
      } catch (expErr) {
        console.warn('Forecast explanation failed:', expErr)
      } finally {
        setLoadingForecastExp(false)
      }
    } catch (err: any) {
      setError(err.message || 'Forecasting failed.')
    } finally {
      setTraining(false)
    }
  }

  // Combined chart data: historical actuals + future forecast with uncertainty interval
  const chartData = (() => {
    if (!trainResult) return []
    const combined: Array<{
      date: string
      actual?: number | null
      forecast?: number | null
      lower_80?: number | null
      upper_80?: number | null
      lower_95?: number | null
      upper_95?: number | null
    }> = []

    // Historical tail (up to 40 points)
    const histTail = trainResult.historical_data.slice(-40)
    histTail.forEach((h) => {
      combined.push({
        date: h.date,
        actual: h.value,
        forecast: null,
      })
    })

    // Connect last historical point to first forecast point
    if (histTail.length > 0 && trainResult.forecast_data.length > 0) {
      const lastHist = histTail[histTail.length - 1]
      combined[combined.length - 1].forecast = lastHist.value
    }

    // Future forecast points
    trainResult.forecast_data.forEach((f) => {
      combined.push({
        date: f.date,
        actual: null,
        forecast: f.forecast,
        lower_80: f.lower_80,
        upper_80: f.upper_80,
        lower_95: f.lower_95,
        upper_95: f.upper_95,
      })
    })

    return combined
  })()

  // Backtest chart data
  const backtestChartData =
    trainResult?.backtest_data.map((b) => ({
      date: b.date,
      actual: b.actual,
      predicted: b.predicted,
      residual: b.residual,
    })) || []

  return (
    <div className="space-y-6">
      {/* Feasibility Summary Bar */}
      {feasibility && (
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs">
          <div className="flex items-center gap-3">
            <span className="text-slate-400">
              Total Observations: <strong className="text-white">{feasibility.row_count.toLocaleString()}</strong>
            </span>
            <span className="text-slate-400">
              Distinct Dates: <strong className="text-white">{feasibility.distinct_periods_estimate}</strong>
            </span>
            {feasibility.data_start_date && (
              <span className="text-slate-400">
                Range: <strong className="text-white">{feasibility.data_start_date}</strong> to{' '}
                <strong className="text-white">{feasibility.data_end_date}</strong>
              </span>
            )}
          </div>
          <span
            className={`px-2.5 py-1 rounded font-semibold ${
              feasibility.forecasting_possible
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
            }`}
          >
            {feasibility.forecasting_possible ? '✓ Forecasting Eligible' : '✕ Ineligible'}
          </span>
        </div>
      )}

      {/* Data Quality & Health Card */}
      {feasibility?.data_quality && (
        <DataQualityCard
          dataQuality={feasibility.data_quality}
          columnsInfo={feasibility.columns_info}
          rowCount={feasibility.row_count}
        />
      )}

      {/* Warnings & Errors */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}

      {feasibility?.stale_warning && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2">
          <span className="text-base">⚠️</span>
          <span>{feasibility.stale_warning}</span>
        </div>
      )}

      {feasibility?.missing_requirements && feasibility.missing_requirements.length > 0 && (
        <div className="space-y-1.5">
          {feasibility.missing_requirements.map((req, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
              ✕ {req}
            </div>
          ))}
        </div>
      )}

      {loadingFeas && (
        <div className="p-12 text-center text-slate-400">
          <div className="inline-block animate-spin text-xl mb-2">⚙</div>
          <div>Evaluating time-series properties & feasibility...</div>
        </div>
      )}

      {feasibility && feasibility.forecasting_possible && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Forecast Configuration */}
          <div className="lg:col-span-1 space-y-6">
            <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <span>⏱</span> Forecast Configuration
              </h2>

              {/* Date Column */}
              <div>
                <label className="block text-xs font-semibold text-slate-200 mb-1.5">
                  Date / Timestamp Column
                </label>
                <select
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
                >
                  {feasibility.recommended_date_columns.map((d) => (
                    <option key={d.name} value={d.name}>
                      {d.display_name || d.name} ({d.distinct_dates} periods)
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-slate-400 mt-1">
                  Required to sequence observations chronologically.
                </p>
              </div>

              {/* Numeric Metric */}
              <div>
                <label className="block text-xs font-semibold text-slate-200 mb-1.5">
                  Target Numeric Measure
                </label>
                <select
                  value={selectedMetric}
                  onChange={(e) => setSelectedMetric(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
                >
                  {feasibility.recommended_metrics.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.display_name || m.name} ({m.business_role})
                    </option>
                  ))}
                </select>

                {selectedMetricCandidate && (
                  <div className="mt-2 p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/60 text-xs space-y-1">
                    {selectedMetricCandidate.unit && (
                      <div className="flex justify-between text-slate-400">
                        <span>Unit:</span>
                        <strong className="text-white font-mono">{selectedMetricCandidate.unit}</strong>
                      </div>
                    )}
                    <div className="flex justify-between text-slate-400">
                      <span>Missing Values:</span>
                      <span className={selectedMetricCandidate.null_count ? 'text-amber-400' : 'text-emerald-400'}>
                        {selectedMetricCandidate.null_count || 0} ({selectedMetricCandidate.null_percentage || 0}%)
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Frequency & Aggregation */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-200 mb-1.5">
                    Time Frequency
                  </label>
                  <select
                    value={frequency}
                    onChange={(e) => setFrequency(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-200 mb-1.5">
                    Aggregation
                  </label>
                  <select
                    value={aggregation}
                    onChange={(e) => setAggregation(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
                  >
                    <option value="SUM">SUM (Total)</option>
                    <option value="AVG">AVG (Mean)</option>
                    <option value="COUNT">COUNT (Volume)</option>
                    <option value="DISTINCT_COUNT">DISTINCT_COUNT</option>
                  </select>
                </div>
              </div>

              {/* Forecast Horizon */}
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-xs font-medium text-slate-300">
                    Forecast Horizon ({frequency === 'daily' ? 'days' : frequency === 'weekly' ? 'weeks' : 'months'})
                  </label>
                  <span className="text-xs font-bold text-brand-400 font-mono">{horizon}</span>
                </div>
                <input
                  type="range"
                  min="3"
                  max="60"
                  value={horizon}
                  onChange={(e) => setHorizon(Number(e.target.value))}
                  className="w-full accent-brand-500 cursor-pointer"
                />
                <div className="flex gap-2 mt-2">
                  {[7, 14, 30, 60].map((hVal) => (
                    <button
                      key={hVal}
                      type="button"
                      onClick={() => setHorizon(hVal)}
                      className={`px-2.5 py-1 rounded text-[11px] border cursor-pointer ${
                        horizon === hVal
                          ? 'bg-brand-600 border-brand-500 text-white'
                          : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      {hVal} {frequency === 'daily' ? 'd' : frequency === 'weekly' ? 'w' : 'm'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Advanced Settings Accordion */}
              <div className="pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAdvancedConfig(!showAdvancedConfig)}
                  className="text-xs text-slate-400 hover:text-white flex items-center justify-between w-full"
                >
                  <span className="font-medium">Advanced Imputation Settings</span>
                  <span>{showAdvancedConfig ? '▴' : '▾'}</span>
                </button>

                {showAdvancedConfig && (
                  <div className="mt-3 p-3 bg-slate-950/40 rounded-lg border border-slate-800">
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Missing Periods Imputation
                    </label>
                    <select
                      value={imputationMethod}
                      onChange={(e) => setImputationMethod(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none"
                    >
                      <option value="auto">Auto (Zero for totals, FFill for rates)</option>
                      <option value="zero">Zero Fill (0.0 for inactivity)</option>
                      <option value="ffill">Forward Fill (Carry forward last value)</option>
                      <option value="bfill">Backward Fill (Backfill subsequent value)</option>
                      <option value="interpolate">Linear Interpolation</option>
                    </select>
                  </div>
                )}
              </div>

              {/* Action Button */}
              <button
                type="button"
                disabled={training || !selectedDate || !selectedMetric}
                onClick={handleTrainForecast}
                className="w-full py-2.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-medium text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-brand-500/10 cursor-pointer"
              >
                {training ? (
                  <>
                    <span className="inline-block animate-spin">⚙</span>
                    <span>Backtesting & Generating Forecast...</span>
                  </>
                ) : (
                  <>
                    <span>📈</span>
                    <span>Generate Time-Series Forecast</span>
                  </>
                )}
              </button>
            </div>

            {/* Saved Forecast Models */}
            {savedModels.length > 0 && (
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Saved Forecast Models ({savedModels.length})
                </div>
                <div className="space-y-2 max-h-56 overflow-y-auto">
                  {savedModels.map((m) => (
                    <div
                      key={m.model_id}
                      className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                        activeModelId === m.model_id
                          ? 'bg-brand-900/20 border-brand-500/50 text-white'
                          : 'bg-slate-800/40 border-slate-800 text-slate-300 hover:bg-slate-800'
                      }`}
                      onClick={async () => {
                        setActiveModelId(m.model_id)
                        try {
                          const details = await getForecastModel(m.model_id)
                          setSelectedDate(details.date_column)
                          setSelectedMetric(details.metric_column)
                          setFrequency(details.frequency)
                          setAggregation(details.aggregation)
                          setHorizon(details.horizon)

                          setLoadingForecastExp(true)
                          const exp = await getForecastExplanation(m.model_id)
                          setForecastExplanation(exp)
                        } catch (err) {
                          console.error(err)
                        } finally {
                          setLoadingForecastExp(false)
                        }
                      }}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <strong className="text-white">{m.metric_column}</strong>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-brand-300">
                          {m.algorithm}
                        </span>
                      </div>
                      <div className="flex justify-between text-[11px] text-slate-400">
                        <span>MAE: <strong className="text-white">{m.mae}</strong></span>
                        <span className="capitalize">{m.frequency}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Visualization, Backtest, Metrics, Table */}
          <div className="lg:col-span-2 space-y-6">
            {trainResult ? (
              <div className="space-y-6">
                {loadingForecastExp && (
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                    <span className="animate-spin inline-block">⚙</span>
                    <span>Analyzing time-series trajectory and generating forecast narrative...</span>
                  </div>
                )}

                {/* 1. Executive Forecast Summary Card */}
                <ForecastInsightCard
                  trainResult={trainResult}
                  explanation={forecastExplanation}
                  unit={selectedMetricCandidate?.unit}
                />

                {/* 1.5 AI Business Explanation Card */}
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
                    unit: selectedMetricCandidate?.unit,
                    historical_summary: forecastExplanation
                      ? {
                          mean_value: forecastExplanation.recent_observation_reference,
                          trend: forecastExplanation.historical_trend,
                        }
                      : {},
                    forecast_summary: {
                      forecast_mean:
                        trainResult.forecast_data.reduce((acc, p) => acc + p.forecast, 0) /
                        (trainResult.forecast_data.length || 1),
                      forecast_total: trainResult.forecast_data.reduce((acc, p) => acc + p.forecast, 0),
                      trajectory: forecastExplanation?.historical_trend || 'stable',
                    },
                    backtest_metrics: trainResult.best_model.metrics,
                    intervals: {
                      lower_bound_mean:
                        trainResult.forecast_data.reduce((acc, p) => acc + (p.lower_95 ?? p.lower_80 ?? p.forecast), 0) /
                        (trainResult.forecast_data.length || 1),
                      upper_bound_mean:
                        trainResult.forecast_data.reduce((acc, p) => acc + (p.upper_95 ?? p.upper_80 ?? p.forecast), 0) /
                        (trainResult.forecast_data.length || 1),
                      nominal_coverage_pct: 95,
                    },

                    limitations: forecastExplanation?.limitations || [],
                  }}
                />


                {/* 2. Business Performance & Backtest Translation Card */}
                <BusinessMetricsCard
                  type="forecasting"
                  metrics={trainResult.best_model.metrics}
                  targetName={trainResult.metric_column}
                  unit={selectedMetricCandidate?.unit}
                  frequency={trainResult.frequency}
                  vsBaselinePct={trainResult.best_model.vs_naive_pct}
                />

                {/* 3. Main Chart Container (Historical vs Forecast & Confidence Interval) */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                      <span>📊</span>
                      <span>{chartView === 'forecast' ? 'Historical Observations & Future Forecast' : 'Chronological Backtest Validation'}</span>
                    </div>

                    <div className="flex gap-1.5 p-1 rounded-lg bg-slate-800 border border-slate-700 text-xs">
                      <button
                        type="button"
                        onClick={() => setChartView('forecast')}
                        className={`px-3 py-1 rounded font-medium cursor-pointer ${
                          chartView === 'forecast' ? 'bg-brand-600 text-white' : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        Forecast & Confidence Interval
                      </button>
                      <button
                        type="button"
                        onClick={() => setChartView('backtest')}
                        className={`px-3 py-1 rounded font-medium cursor-pointer ${
                          chartView === 'backtest' ? 'bg-brand-600 text-white' : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        Actual vs Predicted Holdout
                      </button>
                    </div>
                  </div>

                  {chartView === 'forecast' ? (
                    <div className="h-80 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                          <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                          <YAxis stroke="#94a3b8" fontSize={11} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: 8, fontSize: 12 }}
                          />
                          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
                          {/* 95% Confidence Interval Band */}
                          <Area
                            type="monotone"
                            dataKey="upper_95"
                            stroke="none"
                            fill="#6366f1"
                            fillOpacity={0.15}
                            name="95% Interval Upper"
                          />
                          <Area
                            type="monotone"
                            dataKey="lower_95"
                            stroke="none"
                            fill="#0f172a"
                            fillOpacity={1.0}
                            name="95% Interval Lower"
                          />
                          {/* Historical Actuals */}
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
                            dot={{ r: 3.5, fill: '#10b981' }}
                            name="Projected Forecast"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-80 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={backtestChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                          <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                          <YAxis stroke="#94a3b8" fontSize={11} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: 8, fontSize: 12 }}
                          />
                          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
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
                  )}
                </div>

                {/* 3.5 Actionable Decision Layer Callout */}
                <div className="p-4 rounded-xl bg-slate-900 border border-brand-500/30 flex flex-wrap items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-base">⚖️</span>
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        Operational Decision Layer
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-brand-500/20 text-brand-300 font-medium">
                        Demand & Inventory Rules
                      </span>
                    </div>
                    <p className="text-xs text-slate-300">
                      Evaluate this {trainResult.horizon}-period forecast trajectory against capacity limits, spike alerts, and demand planning rules.
                    </p>
                  </div>
                  <Link
                    to="/decisions"
                    className="px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs whitespace-nowrap shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    <span>Evaluate Forecast in Decision Center</span>
                    <span>→</span>
                  </Link>
                </div>

                {/* 4. Pre-Decision Operational Checklist */}
                <DecisionChecklistCard type="forecasting" />

                {/* 5. Collapsible Technical Deep-Dive */}
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                    className="w-full py-3 px-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center justify-between transition-all cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span>⚙</span>
                      <span>Technical Deep-Dive: Algorithm Benchmarks, Empirical Coverage & Full Schedule</span>
                    </div>
                    <span className="text-brand-400">{showTechnicalDetails ? 'Collapse ▲' : 'Expand ▼'}</span>
                  </button>

                  {showTechnicalDetails && (
                    <div className="mt-4 space-y-6">
                      {/* Candidate Models Comparison Table */}
                      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                        <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                          Candidate Forecasting Models Backtested
                        </div>
                        <div className="overflow-x-auto rounded-lg border border-slate-800">
                          <table className="w-full text-xs text-left text-slate-300">
                            <thead className="bg-slate-800/80 text-slate-400">
                              <tr>
                                <th className="py-2.5 px-3">Algorithm</th>
                                <th className="py-2.5 px-3">MAE (Holdout)</th>
                                <th className="py-2.5 px-3">RMSE</th>
                                <th className="py-2.5 px-3">WAPE</th>
                                <th className="py-2.5 px-3">vs Naive Baseline</th>
                                <th className="py-2.5 px-3">Status</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800">
                              {trainResult.candidate_models.map((cand) => (
                                <tr key={cand.algorithm} className={cand.is_best ? 'bg-emerald-500/10 font-semibold' : ''}>
                                  <td className="py-2 px-3 text-white">
                                    {cand.algorithm}
                                    {cand.is_baseline && <span className="ml-2 text-[10px] text-slate-400">(Baseline)</span>}
                                  </td>
                                  <td className="py-2 px-3">{cand.metrics.mae}</td>
                                  <td className="py-2 px-3">{cand.metrics.rmse}</td>
                                  <td className="py-2 px-3">{cand.metrics.wape !== null ? `${cand.metrics.wape}%` : '-'}</td>
                                  <td className="py-2 px-3">
                                    {cand.vs_naive_pct !== null && cand.vs_naive_pct !== undefined ? (
                                      <span className={cand.vs_naive_pct > 0 ? 'text-emerald-400' : 'text-slate-400'}>
                                        {cand.vs_naive_pct > 0 ? `+${cand.vs_naive_pct}%` : `${cand.vs_naive_pct}%`}
                                      </span>
                                    ) : (
                                      'Baseline'
                                    )}
                                  </td>
                                  <td className="py-2 px-3">
                                    {cand.is_best ? (
                                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px]">
                                        Selected Best
                                      </span>
                                    ) : (
                                      <span className="text-slate-500">Evaluated</span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Forecast Detailed Explanation Card */}
                      {forecastExplanation && (
                        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
                          <div className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                            <span>🔍</span>
                            <span>Detailed Time-Series Decomposition</span>
                          </div>

                          <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 space-y-1">
                            <div className="text-[11px] font-semibold text-brand-300">Extrapolation Strategy:</div>
                            <p className="text-xs text-slate-300 leading-relaxed">
                              {forecastExplanation.selection_reason}
                            </p>
                          </div>

                          <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-[10px] text-slate-400 space-y-1">
                            <div className="font-semibold text-slate-400">Interpretability & Non-Causality Disclosures:</div>
                            {forecastExplanation.limitations.map((lim, idx) => (
                              <div key={idx} className="text-slate-500">• {lim}</div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Full Projected Values Table */}
                      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                        <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex justify-between items-center">
                          <span>Full Forecast Projection Schedule ({trainResult.forecast_data.length} periods)</span>
                          <span className="text-slate-500 font-normal">Starting from {trainResult.historical_end_date}</span>
                        </div>

                        {trainResult.interval_notes && (
                          <div className="text-[11px] text-slate-400 italic bg-slate-800/40 p-2.5 rounded-lg border border-slate-700/50">
                            ℹ {trainResult.interval_notes}
                          </div>
                        )}

                        <div className="overflow-x-auto max-h-64 rounded-lg border border-slate-800">
                          <table className="w-full text-xs text-left text-slate-300">
                            <thead className="bg-slate-800/80 text-slate-400 sticky top-0">
                              <tr>
                                <th className="py-2 px-3">Date</th>
                                <th className="py-2 px-3">Point Forecast</th>
                                <th className="py-2 px-3">80% Interval</th>
                                <th className="py-2 px-3">95% Interval</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800 font-mono">
                              {trainResult.forecast_data.map((fp) => (
                                <tr key={fp.date} className="hover:bg-slate-800/40">
                                  <td className="py-1.5 px-3 text-white font-sans">{fp.date}</td>
                                  <td className="py-1.5 px-3 text-emerald-300 font-bold">{fp.forecast.toLocaleString()}</td>
                                  <td className="py-1.5 px-3 text-slate-400">
                                    [{fp.lower_80 ?? '-'} – {fp.upper_80 ?? '-'}]
                                  </td>
                                  <td className="py-1.5 px-3 text-slate-400">
                                    [{fp.lower_95 ?? '-'} – {fp.upper_95 ?? '-'}]
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-16 rounded-xl bg-slate-900 border border-slate-800 text-center text-slate-400 space-y-3">
                <div className="text-4xl">📈</div>
                <h3 className="text-base font-semibold text-white">Ready for Time-Series Forecasting</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Configure your date column, numeric measure, frequency, and forecast horizon on the left, then click <strong>Generate Time-Series Forecast</strong>.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
