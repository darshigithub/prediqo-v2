import { useEffect, useState } from 'react'
import {
  getForecastFeasibility,
  trainForecastModel,
  listForecastModels,
  getForecastExplanation,
} from '../services/api'
import type {
  ForecastFeasibilityResponse,
  ForecastTrainResponse,
  ForecastModelListItem,
  ForecastExplanationResponse,
} from '../types'
import CenterHeader from '../components/centers/CenterHeader'
import CenterNavTabs, { type CenterTabId } from '../components/centers/CenterNavTabs'
import ForecastingConfigPanel from '../components/forecasting/ForecastingConfigPanel'
import ForecastingOverviewTab from '../components/forecasting/ForecastingOverviewTab'
import ForecastingAnalyticsTab from '../components/forecasting/ForecastingAnalyticsTab'
import ForecastingAIExplanationTab from '../components/forecasting/ForecastingAIExplanationTab'
import ForecastingTechnicalTab from '../components/forecasting/ForecastingTechnicalTab'

export default function ForecastingPage() {
  const [datasetId, setDatasetId] = useState<string>('')
  const [activeTab, setActiveTab] = useState<CenterTabId>('overview')
  const [isConfigOpen, setIsConfigOpen] = useState<boolean>(true)

  // Feasibility & Configuration
  const [feasibility, setFeasibility] = useState<ForecastFeasibilityResponse | null>(null)
  const [loadingFeasibility, setLoadingFeasibility] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const [selectedDate, setSelectedDate] = useState<string>('')
  const [selectedMetric, setSelectedMetric] = useState<string>('')
  const [frequency, setFrequency] = useState<string>('daily')
  const [aggregation, setAggregation] = useState<string>('SUM')
  const [horizon, setHorizon] = useState<number>(14)
  const [imputationMethod, setImputationMethod] = useState<string>('auto')

  // Training & Model state
  const [training, setTraining] = useState<boolean>(false)
  const [trainResult, setTrainResult] = useState<ForecastTrainResponse | null>(null)
  const [savedModels, setSavedModels] = useState<ForecastModelListItem[]>([])
  const [activeModelId, setActiveModelId] = useState<string>('')

  // Explainability state
  const [explanation, setExplanation] = useState<ForecastExplanationResponse | null>(null)
  const [loadingExplanation, setLoadingExplanation] = useState<boolean>(false)

  // 1. Load feasibility & saved models on dataset change
  useEffect(() => {
    if (!datasetId) {
      setFeasibility(null)
      setTrainResult(null)
      setExplanation(null)
      setSavedModels([])
      return
    }

    setLoadingFeasibility(true)
    setError(null)
    setTrainResult(null)
    setExplanation(null)

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
        setLoadingFeasibility(false)
      })

    listForecastModels(datasetId)
      .then((res) => setSavedModels(res.models || []))
      .catch(() => setSavedModels([]))
  }, [datasetId])

  // 2. Update aggregation recommendation when metric changes
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

  // 3. Train Forecast Action
  const handleTrainForecast = async () => {
    if (!datasetId || !selectedDate || !selectedMetric) return
    setTraining(true)
    setError(null)
    setExplanation(null)

    try {
      const res = await trainForecastModel({
        dataset_id: datasetId,
        date_column: selectedDate,
        metric_column: selectedMetric,
        frequency,
        aggregation,
        horizon,
        imputation_method: imputationMethod,
      })

      setTrainResult(res)
      setActiveModelId(res.model_id)

      // Automatically fetch forecast explanation & trajectory
      setLoadingExplanation(true)
      try {
        const exp = await getForecastExplanation(res.model_id)
        setExplanation(exp)
      } catch (expErr: any) {
        console.warn('Forecast explanation skipped or failed:', expErr)
      } finally {
        setLoadingExplanation(false)
      }

      // Refresh saved models
      const updatedList = await listForecastModels(datasetId)
      setSavedModels(updatedList.models || [])
    } catch (err: any) {
      setError(err.message || 'Forecasting failed.')
    } finally {
      setTraining(false)
    }
  }

  // 4. Select Saved Model Action
  const handleSelectSavedModel = async (modelId: string) => {
    setActiveModelId(modelId)
    // When selecting saved model, we can trigger details fetch if needed
  }

  const activeModelLabel = trainResult
    ? `${trainResult.best_model.algorithm} · ${trainResult.horizon} Periods (${trainResult.frequency})`
    : savedModels.length > 0
    ? `${savedModels.length} Saved Forecasters Available`
    : null

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Shared Enterprise Header */}
      <CenterHeader
        currentCenter="forecasting"
        title="Forecasting Center"
        subtitle="Understand historical patterns and explore future business outcomes."
        datasetId={datasetId}
        onDatasetChange={setDatasetId}
        activeModelLabel={activeModelLabel}
        badgeColor="brand"
        actionSlot={
          trainResult && (
            <button
              type="button"
              onClick={() => setIsConfigOpen(!isConfigOpen)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 transition-colors shadow-2xs flex items-center gap-1.5 cursor-pointer"
            >
              <span>{isConfigOpen ? '◀ Hide Setup' : '⚙ Show Setup Panel'}</span>
            </button>
          )
        }
      />

      {/* Error Alert Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs shadow-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-rose-500 hover:text-rose-700 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. Top 4-Tab Navigation */}
      <CenterNavTabs
        activeTab={activeTab}
        onChange={setActiveTab}
        disabledTabs={!trainResult ? ['analytics', 'explanation', 'technical'] : []}
      />

      {/* 3. Main Center Workspace */}
      {datasetId ? (
        <div className={`grid grid-cols-1 ${isConfigOpen ? 'lg:grid-cols-12' : 'lg:grid-cols-1'} gap-6 items-start`}>
          {/* Left Configuration Panel (Collapsible) */}
          {isConfigOpen && (
            <div className="lg:col-span-4 xl:col-span-3">
              <ForecastingConfigPanel
                feasibility={feasibility}
                loadingFeasibility={loadingFeasibility}
                selectedDate={selectedDate}
                onDateChange={setSelectedDate}
                selectedMetric={selectedMetric}
                onMetricChange={setSelectedMetric}
                selectedMetricCandidate={selectedMetricCandidate}
                aggregation={aggregation}
                onAggregationChange={setAggregation}
                frequency={frequency}
                onFrequencyChange={setFrequency}
                horizon={horizon}
                onHorizonChange={setHorizon}
                imputationMethod={imputationMethod}
                onImputationChange={setImputationMethod}
                training={training}
                onTrain={handleTrainForecast}
                savedModels={savedModels}
                activeModelId={activeModelId}
                onSelectSavedModel={handleSelectSavedModel}
              />
            </div>
          )}

          {/* Right Main Content Tabs (Preserves State) */}
          <div className={isConfigOpen ? 'lg:col-span-8 xl:col-span-9' : 'lg:col-span-1'}>
            {activeTab === 'overview' && (
              <ForecastingOverviewTab
                trainResult={trainResult}
                explanation={explanation}
                loadingExplanation={loadingExplanation}
                selectedMetricCandidate={selectedMetricCandidate}
                onNavigateTab={(tab) => setActiveTab(tab)}
              />
            )}

            {activeTab === 'analytics' && (
              <ForecastingAnalyticsTab
                trainResult={trainResult}
                explanation={explanation}
                selectedMetricCandidate={selectedMetricCandidate}
              />
            )}

            {activeTab === 'explanation' && (
              <ForecastingAIExplanationTab
                datasetId={datasetId}
                trainResult={trainResult}
                explanation={explanation}
                selectedMetricCandidate={selectedMetricCandidate}
                activeModelId={activeModelId}
              />
            )}

            {activeTab === 'technical' && (
              <ForecastingTechnicalTab
                trainResult={trainResult}
                explanation={explanation}
                selectedMetricCandidate={selectedMetricCandidate}
              />
            )}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200/80 p-16 text-center shadow-sm space-y-3">
          <div className="text-4xl">📂</div>
          <h3 className="text-base font-bold text-slate-900">No Dataset Selected</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Please choose a standardized dataset with date and numeric columns to configure and extrapolate time-series forecasts.
          </p>
        </div>
      )}
    </div>
  )
}
