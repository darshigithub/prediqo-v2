import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
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
import {
  getPredictionFeasibility,
  trainPredictionModel,
  listPredictionModels,
  predictSingle,
  getLocalExplanation,
  getGlobalExplanation,
} from '../services/api'
import type {
  FeasibilityResponse,
  TargetCandidate,
  TrainResponse,
  PredictResponse,
  ModelListItem,
  LocalExplanationResponse,
  GlobalExplanationResponse,
} from '../types'
import DataQualityCard from './business/DataQualityCard'
import BusinessMetricsCard from './business/BusinessMetricsCard'
import PredictionInsightCard from './business/PredictionInsightCard'
import HumanReadableXAICard from './business/HumanReadableXAICard'
import DecisionChecklistCard from './business/DecisionChecklistCard'
import AIExplanationCard from './business/AIExplanationCard'


interface PredictionTabProps {
  datasetId: string
}

export default function PredictionTab({ datasetId }: PredictionTabProps) {
  const [feasibility, setFeasibility] = useState<FeasibilityResponse | null>(null)
  const [loadingFeasibility, setLoadingFeasibility] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Configuration state
  const [selectedTarget, setSelectedTarget] = useState<string>('')
  const [targetCandidate, setTargetCandidate] = useState<TargetCandidate | null>(null)
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])
  const [excludedFeatures, setExcludedFeatures] = useState<string[]>([])
  const [cvFolds, setCvFolds] = useState<number>(5)
  const [validationStrategy, setValidationStrategy] = useState<string>('kfold')
  const [selectedGroupCol, setSelectedGroupCol] = useState<string>('')
  const [showAdvancedSetup, setShowAdvancedSetup] = useState<boolean>(false)

  // Training state
  const [training, setTraining] = useState<boolean>(false)
  const [trainResult, setTrainResult] = useState<TrainResponse | null>(null)
  const [modelsList, setModelsList] = useState<ModelListItem[]>([])

  // Inference state
  const [activeModelId, setActiveModelId] = useState<string>('')
  const [predictInputs, setPredictInputs] = useState<Record<string, any>>({})
  const [predicting, setPredicting] = useState<boolean>(false)
  const [predictResult, setPredictResult] = useState<PredictResponse | null>(null)

  // Explainability (XAI) state
  const [localExplanation, setLocalExplanation] = useState<LocalExplanationResponse | null>(null)
  const [loadingLocalExp, setLoadingLocalExp] = useState<boolean>(false)
  const [globalExplanation, setGlobalExplanation] = useState<GlobalExplanationResponse | null>(null)
  const [loadingGlobalExp, setLoadingGlobalExp] = useState<boolean>(false)
  const [showGlobalExp, setShowGlobalExp] = useState<boolean>(false)

  // View toggles
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false)

  // 1. Load feasibility when dataset changes
  useEffect(() => {
    if (!datasetId) {
      setFeasibility(null)
      setTrainResult(null)
      setPredictResult(null)
      return
    }

    setLoadingFeasibility(true)
    setError(null)
    setTrainResult(null)
    setPredictResult(null)

    getPredictionFeasibility(datasetId)
      .then((data) => {
        setFeasibility(data)
        const defaultTarget =
          data.recommended_targets[0] ||
          data.regression_targets[0]?.name ||
          data.classification_targets[0]?.name ||
          ''
        setSelectedTarget(defaultTarget)
      })
      .catch((err) => {
        setError(err.message || 'Failed to check prediction feasibility.')
      })
      .finally(() => {
        setLoadingFeasibility(false)
      })

    listPredictionModels(datasetId, true)
      .then((res) => setModelsList(res.models || []))
      .catch(() => setModelsList([]))
  }, [datasetId])

  // 2. Update target candidate & recommended features when target changes
  useEffect(() => {
    if (!feasibility || !selectedTarget) {
      setTargetCandidate(null)
      setSelectedFeatures([])
      setExcludedFeatures([])
      return
    }

    const allCandidates = [
      ...feasibility.regression_targets,
      ...feasibility.classification_targets,
    ]
    const cand = allCandidates.find((c) => c.name === selectedTarget) || null
    setTargetCandidate(cand)

    const allCandidateNames = allCandidates.map((c) => c.name)
    const availableFeatures = allCandidateNames.filter((name) => name !== selectedTarget)

    setSelectedFeatures(availableFeatures)
    setExcludedFeatures([selectedTarget])
  }, [feasibility, selectedTarget])

  const toggleFeature = (name: string) => {
    if (selectedFeatures.includes(name)) {
      setSelectedFeatures(selectedFeatures.filter((f) => f !== name))
    } else {
      setSelectedFeatures([...selectedFeatures, name])
    }
  }

  const selectAllFeatures = () => {
    if (!feasibility) return
    const all = [
      ...feasibility.regression_targets,
      ...feasibility.classification_targets,
    ]
      .map((c) => c.name)
      .filter((n) => n !== selectedTarget)
    setSelectedFeatures(all)
  }

  const deselectAllFeatures = () => {
    setSelectedFeatures([])
  }

  // 3. Train Model
  const handleTrain = async () => {
    if (!datasetId || !selectedTarget || !targetCandidate) return
    if (selectedFeatures.length === 0) {
      setError('Please select at least one feature column for training.')
      return
    }

    setTraining(true)
    setError(null)
    setPredictResult(null)
    setLocalExplanation(null)
    setGlobalExplanation(null)
    setShowGlobalExp(false)

    try {
      const res = await trainPredictionModel({
        dataset_id: datasetId,
        target_column: selectedTarget,
        problem_type: targetCandidate.problem_type,
        features: selectedFeatures,
        test_size: 0.2,
        random_state: 42,
        validation_strategy: validationStrategy,
        cv_folds: cvFolds,
        group_column: validationStrategy === 'group_kfold' ? selectedGroupCol || null : null,
      })
      setTrainResult(res)
      setActiveModelId(res.model_id)

      const initialInputs: Record<string, any> = {}
      res.selected_features.forEach((feat) => {
        initialInputs[feat] = ''
      })
      setPredictInputs(initialInputs)

      const updatedModels = await listPredictionModels(datasetId, true)
      setModelsList(updatedModels.models || [])
    } catch (err: any) {
      setError(err.message || 'Model training failed.')
    } finally {
      setTraining(false)
    }
  }

  // Fetch Global Explanations
  const handleLoadGlobalExplanation = async () => {
    if (!activeModelId) return
    setLoadingGlobalExp(true)
    try {
      const gRes = await getGlobalExplanation(activeModelId, 100)
      setGlobalExplanation(gRes)
      setShowGlobalExp(true)
    } catch (err: any) {
      console.warn('Global explanation fetch failed:', err)
    } finally {
      setLoadingGlobalExp(false)
    }
  }

  // 4. Run Prediction & Local XAI Decomposition
  const handlePredict = async () => {
    if (!activeModelId) return
    setPredicting(true)
    setError(null)
    setLocalExplanation(null)

    try {
      const processed: Record<string, any> = {}
      Object.entries(predictInputs).forEach(([k, v]) => {
        if (v === '' || v === null || v === undefined) {
          processed[k] = null
        } else if (!isNaN(Number(v)) && String(v).trim() !== '') {
          processed[k] = Number(v)
        } else {
          processed[k] = v
        }
      })

      const res = await predictSingle(activeModelId, processed)
      setPredictResult(res)

      // Fetch Local Additive Feature Decomposition (XAI)
      setLoadingLocalExp(true)
      try {
        const expRes = await getLocalExplanation({
          model_id: activeModelId,
          features: processed,
          target_class: res.prediction,
        })
        setLocalExplanation(expRes)
      } catch (expErr) {
        console.warn('Local prediction explanation failed:', expErr)
      } finally {
        setLoadingLocalExp(false)
      }
    } catch (err: any) {
      setError(err.message || 'Prediction failed.')
    } finally {
      setPredicting(false)
    }
  }

  // Actual vs Predicted points for holdout chart
  const actVsPredData =
    trainResult?.actual_vs_predicted?.map((pt, idx) => ({
      sample: idx + 1,
      actual: pt.actual,
      predicted: pt.predicted,
      residual: pt.residual,
    })) || []

  return (
    <div className="space-y-6">
      {/* Feasibility Summary Bar */}
      {feasibility && (
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs">
          <div className="flex items-center gap-3">
            <span className="text-slate-400">
              Rows: <strong className="text-white">{feasibility.row_count.toLocaleString()}</strong>
            </span>
            <span className="text-slate-400">
              Version: <strong className="text-brand-400">v{feasibility.dataset_version}</strong>
            </span>
          </div>
          <span
            className={`px-2.5 py-0.5 rounded font-semibold ${
              feasibility.prediction_possible
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
            }`}
          >
            {feasibility.prediction_possible ? '✓ ML Ready' : '✕ Not Feasible'}
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

      {feasibility?.warnings && feasibility.warnings.length > 0 && (
        <div className="space-y-1">
          {feasibility.warnings.map((w, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
              ⚠️ {w}
            </div>
          ))}
        </div>
      )}

      {loadingFeasibility && (
        <div className="p-8 text-center text-slate-400">
          <div className="inline-block animate-spin text-xl mb-2">⚙</div>
          <div>Checking prediction feasibility & assessing dataset readiness...</div>
        </div>
      )}

      {feasibility && feasibility.prediction_possible && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Target & Feature Configuration */}
          <div className="lg:col-span-1 space-y-6">
            <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-5">
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <span>🎯</span>
                <span>1. Prediction Setup</span>
              </h2>

              {/* Target Selection */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-200">
                  Target Variable to Predict
                </label>
                <select
                  value={selectedTarget}
                  onChange={(e) => setSelectedTarget(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
                >
                  <optgroup label="── Regression Targets (Numeric Measures) ──">
                    {feasibility.regression_targets.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.display_name || t.name} ({t.business_role})
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="── Classification Targets (Categories & Status) ──">
                    {feasibility.classification_targets.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.display_name || t.name} ({t.business_role})
                      </option>
                    ))}
                  </optgroup>
                </select>

                {/* Target Information Card */}
                {targetCandidate && (
                  <div className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/60 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Target Type:</span>
                      <span
                        className={`px-2 py-0.5 rounded font-semibold uppercase text-[10px] ${
                          targetCandidate.problem_type === 'regression'
                            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                            : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                        }`}
                      >
                        {targetCandidate.problem_type}
                      </span>
                    </div>
                    {targetCandidate.unit && (
                      <div className="flex items-center justify-between text-slate-400">
                        <span>Expected Unit:</span>
                        <strong className="text-white font-mono">{targetCandidate.unit}</strong>
                      </div>
                    )}
                    <div className="flex items-center justify-between text-slate-400">
                      <span>Missing Values:</span>
                      <span className={(targetCandidate.null_count ?? 0) > 0 ? 'text-amber-400 font-mono' : 'text-emerald-400 font-mono'}>
                        {targetCandidate.null_count ?? 0} ({targetCandidate.null_percentage ?? 0}%)
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 pt-1 border-t border-slate-700/60">
                      The model will learn patterns across historical rows to predict this variable for future cases.
                    </p>
                  </div>
                )}
              </div>

              {/* Feature Checklist */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-slate-300">
                    Input Features ({selectedFeatures.length} selected)
                  </label>
                  <div className="flex gap-2 text-[11px] text-brand-400">
                    <button type="button" onClick={selectAllFeatures} className="hover:underline">
                      All
                    </button>
                    <span>·</span>
                    <button type="button" onClick={deselectAllFeatures} className="hover:underline">
                      None
                    </button>
                  </div>
                </div>

                <div className="max-h-52 overflow-y-auto space-y-1.5 p-2 bg-slate-950/50 rounded-lg border border-slate-800">
                  {[...feasibility.regression_targets, ...feasibility.classification_targets]
                    .filter((c) => c.name !== selectedTarget)
                    .map((col) => {
                      const isChecked = selectedFeatures.includes(col.name)
                      return (
                        <label
                          key={col.name}
                          className="flex items-center gap-2.5 px-2 py-1.5 rounded hover:bg-slate-800/60 cursor-pointer text-xs"
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleFeature(col.name)}
                            className="rounded border-slate-700 bg-slate-800 text-brand-500 focus:ring-brand-500"
                          />
                          <span className={isChecked ? 'text-white font-medium' : 'text-slate-300'}>
                            {col.display_name || col.name}
                          </span>
                          <span className="ml-auto text-[10px] text-slate-400 font-mono">
                            {col.business_role}
                          </span>
                        </label>
                      )
                    })}
                </div>
              </div>

              {/* Advanced Validation Options Accordion */}
              <div className="pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAdvancedSetup(!showAdvancedSetup)}
                  className="text-xs text-slate-400 hover:text-white flex items-center justify-between w-full"
                >
                  <span className="font-medium">Advanced ML Validation Settings</span>
                  <span>{showAdvancedSetup ? '▴' : '▾'}</span>
                </button>

                {showAdvancedSetup && (
                  <div className="mt-3 space-y-3 p-3 bg-slate-950/40 rounded-lg border border-slate-800">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">
                        Splitting Strategy
                      </label>
                      <select
                        value={validationStrategy}
                        onChange={(e) => setValidationStrategy(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none"
                      >
                        <option value="kfold">K-Fold CV (Stratified for Classification)</option>
                        <option value="time_aware">Time-Aware (Chronological Holdout)</option>
                        <option value="group_kfold">Group-Aware K-Fold (Entity Grouping)</option>
                      </select>
                    </div>

                    {validationStrategy === 'group_kfold' && feasibility && (
                      <div>
                        <label className="block text-[11px] font-medium text-slate-400 mb-1">
                          Group Column (e.g. Customer, Order ID)
                        </label>
                        <select
                          value={selectedGroupCol}
                          onChange={(e) => setSelectedGroupCol(e.target.value)}
                          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none"
                        >
                          <option value="">-- Select Group Column --</option>
                          {[...feasibility.regression_targets, ...feasibility.classification_targets].map((c) => (
                            <option key={c.name} value={c.name}>
                              {c.display_name || c.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">
                        Cross-Validation Folds
                      </label>
                      <select
                        value={cvFolds}
                        onChange={(e) => setCvFolds(Number(e.target.value))}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none"
                      >
                        <option value={3}>3-Fold Cross-Validation</option>
                        <option value={5}>5-Fold K-Fold (Recommended)</option>
                        <option value={10}>10-Fold K-Fold</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>

              {/* Excluded Columns Notice */}
              {excludedFeatures.length > 0 && (
                <div className="pt-2 border-t border-slate-800/80">
                  <div className="text-[11px] font-medium text-slate-400 mb-1.5">
                    Excluded Columns (Target & Identifiers):
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {excludedFeatures.map((f) => (
                      <span key={f} className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-mono">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Train Button */}
              <button
                type="button"
                disabled={training || selectedFeatures.length === 0}
                onClick={handleTrain}
                className="w-full py-2.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-medium text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-brand-500/10 cursor-pointer"
              >
                {training ? (
                  <>
                    <span className="inline-block animate-spin">⚙</span>
                    <span>Training Candidate Models with CV...</span>
                  </>
                ) : (
                  <>
                    <span>⚡</span>
                    <span>Train Machine Learning Models</span>
                  </>
                )}
              </button>
            </div>

            {/* Existing Models List */}
            {modelsList.length > 0 && (
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Saved Models for this Dataset ({modelsList.length})
                </div>
                <div className="space-y-2 max-h-56 overflow-y-auto">
                  {modelsList.map((m) => (
                    <div
                      key={m.model_id}
                      className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                        activeModelId === m.model_id
                          ? 'bg-brand-900/20 border-brand-500/50 text-white'
                          : 'bg-slate-800/40 border-slate-800 text-slate-300 hover:bg-slate-800'
                      }`}
                      onClick={() => {
                        setActiveModelId(m.model_id)
                        setSelectedTarget(m.target_column)
                      }}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <strong className="text-white">{m.target_column}</strong>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-brand-300">
                          {m.algorithm}
                        </span>
                      </div>
                      <div className="flex justify-between text-[11px] text-slate-400">
                        <span>
                          {m.primary_metric.toUpperCase()}: <strong className="text-white">{m.primary_metric_value}</strong>
                        </span>
                        <span>v{m.dataset_version}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Columns: Structured Business Flow & Technical Deep-Dive */}
          <div className="lg:col-span-2 space-y-6">
            {trainResult ? (
              <div className="space-y-6">
                {/* Reliability Notes Banner */}
                {trainResult.best_model.reliability_notes && trainResult.best_model.reliability_notes.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-1">
                    <div className="font-semibold flex items-center gap-1.5">
                      <span>⚠️</span> Model Reliability Diagnostics:
                    </div>
                    <ul className="list-disc pl-5 space-y-0.5">
                      {trainResult.best_model.reliability_notes.map((note, idx) => (
                        <li key={idx}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 1. Best Model Executive Header */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                        <span>★</span> Winning Machine Learning Algorithm
                      </div>
                      <h3 className="text-xl font-bold text-white mt-0.5">
                        {trainResult.best_model.algorithm}
                      </h3>
                      {trainResult.best_model.selection_rationale && (
                        <p className="text-xs text-slate-300 mt-1">
                          {trainResult.best_model.selection_rationale}
                        </p>
                      )}
                    </div>
                    <div className="text-right text-xs text-slate-400">
                      <div>Trained on <strong className="text-white">{trainResult.training_row_count}</strong> rows</div>
                      <div>Tested on <strong className="text-white">{trainResult.test_row_count}</strong> holdout rows</div>
                    </div>
                  </div>
                </div>

                {/* 2. Business Performance & Plain-English Metrics */}
                <BusinessMetricsCard
                  type={trainResult.problem_type}
                  metrics={trainResult.best_model.metrics}
                  targetName={trainResult.target_column}
                  unit={targetCandidate?.unit}
                  classLabels={trainResult.best_model.class_labels}
                  vsBaselinePct={trainResult.best_model.vs_baseline_pct}
                />

                {/* 3. Live Interactive Prediction Form & Insight Card */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
                  <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                    <span>🎯</span> Make a Live Prediction
                  </h3>
                  <p className="text-xs text-slate-400">
                    Input scenario values to generate an instant prediction using the trained {trainResult.best_model.algorithm} model:
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {trainResult.selected_features.map((feat) => (
                      <div key={feat}>
                        <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                          {feat}
                        </label>
                        <input
                          type="text"
                          value={predictInputs[feat] ?? ''}
                          onChange={(e) =>
                            setPredictInputs({
                              ...predictInputs,
                              [feat]: e.target.value,
                            })
                          }
                          placeholder={`Enter ${feat}`}
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
                        />
                      </div>
                    ))}
                  </div>

                  <button
                    type="button"
                    disabled={predicting}
                    onClick={handlePredict}
                    className="py-2.5 px-5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium text-xs transition-all flex items-center gap-2 shadow-lg shadow-emerald-500/10 cursor-pointer"
                  >
                    {predicting ? (
                      <>
                        <span className="inline-block animate-spin">⚙</span>
                        <span>Calculating Prediction...</span>
                      </>
                    ) : (
                      <>
                        <span>▶</span>
                        <span>Generate Prediction</span>
                      </>
                    )}
                  </button>

                  {/* Prediction Output Result */}
                  {predictResult && (
                    <PredictionInsightCard
                      result={predictResult}
                      targetName={trainResult.target_column}
                      problemType={trainResult.problem_type}
                      unit={targetCandidate?.unit}
                      baselineValue={localExplanation?.baseline_reference_value}
                    />
                  )}

                  {/* Loading XAI indicator */}
                  {loadingLocalExp && (
                    <div className="p-3 text-xs text-slate-400 flex items-center gap-2">
                      <span className="animate-spin inline-block">⚙</span>
                      <span>Computing plain-language explanation of prediction drivers...</span>
                    </div>
                  )}

                  {/* 4. Human-Readable Explainable AI (XAI) Card */}
                  {localExplanation && (
                    <HumanReadableXAICard
                      localExplanation={localExplanation}
                      targetName={trainResult.target_column}
                      unit={targetCandidate?.unit}
                    />
                  )}

                  {/* 4.2 AI-Powered Business Explanation */}
                  {predictResult && (
                    <AIExplanationCard
                      type="prediction"
                      predictionPayload={{
                        model_id: activeModelId || trainResult.model_id,
                        dataset_id: datasetId,
                        target_name: trainResult.target_column,
                        problem_type: trainResult.problem_type,
                        unit: targetCandidate?.unit,
                        prediction: predictResult.prediction,
                        probabilities: predictResult.probabilities,
                        baseline_reference_value: localExplanation?.baseline_reference_value,
                        decomposition_space: localExplanation?.decomposition_space,
                        contributions: localExplanation?.contributions?.map((c) => ({
                          feature: c.feature,
                          contribution: c.contribution,
                          raw_value: c.raw_value,
                        })) || [],
                        metrics: trainResult.best_model.metrics,
                        model_metadata: {
                          algorithm: trainResult.best_model.algorithm,
                          model_id: trainResult.model_id,
                        },
                        data_quality: feasibility?.warnings ? { warnings: feasibility.warnings } : undefined,
                      }}
                    />
                  )}


                  {/* 4.5 Actionable Decision Layer Callout */}
                  {predictResult && (
                    <div className="p-4 rounded-xl bg-slate-900 border border-brand-500/30 flex flex-wrap items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-base">⚖️</span>
                          <span className="text-xs font-bold text-white uppercase tracking-wider">
                            Operational Decision Layer
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-brand-500/20 text-brand-300 font-medium">
                            Active Rules
                          </span>
                        </div>
                        <p className="text-xs text-slate-300">
                          Evaluate this prediction ({String(predictResult.prediction)} {targetCandidate?.unit || ''}) against configured inventory, churn, and operational business rules.
                        </p>
                      </div>
                      <Link
                        to="/decisions"
                        className="px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs whitespace-nowrap shadow-sm transition-colors flex items-center gap-1.5"
                      >
                        <span>Evaluate in Decision Center</span>
                        <span>→</span>
                      </Link>
                    </div>
                  )}
                </div>

                {/* 5. Pre-Decision Operational Checklist */}
                <DecisionChecklistCard type="prediction" />

                {/* 6. Collapsible Technical Deep-Dive (Diagnostics, Math & Tables) */}
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                    className="w-full py-3 px-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center justify-between transition-all"
                  >
                    <div className="flex items-center gap-2">
                      <span>⚙</span>
                      <span>Technical Deep-Dive: Cross-Validation, Fit Plots & Model Diagnostics</span>
                    </div>
                    <span className="text-brand-400">{showTechnicalDetails ? 'Collapse ▲' : 'Expand ▼'}</span>
                  </button>

                  {showTechnicalDetails && (
                    <div className="mt-4 space-y-6">
                      {/* Candidate Comparison Table */}
                      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                        <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                          Candidate Model Comparison (Cross-Validation & Holdout)
                        </div>
                        <div className="overflow-x-auto rounded-lg border border-slate-800">
                          <table className="w-full text-xs text-left text-slate-300">
                            <thead className="bg-slate-800/80 text-slate-400">
                              <tr>
                                <th className="py-2 px-3">Algorithm</th>
                                {trainResult.problem_type === 'regression' ? (
                                  <>
                                    <th className="py-2 px-3">CV MAE (Primary)</th>
                                    <th className="py-2 px-3">Holdout MAE</th>
                                    <th className="py-2 px-3">RMSE</th>
                                    <th className="py-2 px-3">R²</th>
                                  </>
                                ) : (
                                  <>
                                    <th className="py-2 px-3">CV F1 (Primary)</th>
                                    <th className="py-2 px-3">Accuracy</th>
                                    <th className="py-2 px-3">Precision</th>
                                    <th className="py-2 px-3">F1 Score</th>
                                  </>
                                )}
                                <th className="py-2 px-3">vs Baseline</th>
                                <th className="py-2 px-3">Time</th>
                                <th className="py-2 px-3">Status</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800">
                              {trainResult.candidate_models.map((cand) => (
                                <tr key={cand.algorithm} className={cand.is_best ? 'bg-emerald-500/10 font-semibold' : ''}>
                                  <td className="py-2 px-3 text-white">{cand.algorithm}</td>
                                  {trainResult.problem_type === 'regression' ? (
                                    <>
                                      <td className="py-2 px-3 text-brand-300 font-bold">
                                        {cand.cv_metrics?.cv_mae ?? '-'}
                                        {cand.cv_metrics?.cv_mae_std ? ` ± ${cand.cv_metrics.cv_mae_std}` : ''}
                                      </td>
                                      <td className="py-2 px-3">{cand.metrics.mae ?? '-'}</td>
                                      <td className="py-2 px-3">{cand.metrics.rmse ?? '-'}</td>
                                      <td className="py-2 px-3">{cand.metrics.r2 ?? '-'}</td>
                                    </>
                                  ) : (
                                    <>
                                      <td className="py-2 px-3 text-brand-300 font-bold">
                                        {cand.cv_metrics?.cv_f1 ?? '-'}
                                        {cand.cv_metrics?.cv_f1_std ? ` ± ${cand.cv_metrics.cv_f1_std}` : ''}
                                      </td>
                                      <td className="py-2 px-3">{cand.metrics.accuracy ?? '-'}</td>
                                      <td className="py-2 px-3">{cand.metrics.precision ?? '-'}</td>
                                      <td className="py-2 px-3">{cand.metrics.f1 ?? '-'}</td>
                                    </>
                                  )}
                                  <td className="py-2 px-3 font-mono text-[11px]">
                                    {cand.vs_baseline_pct !== null && cand.vs_baseline_pct !== undefined ? (
                                      <span className={cand.vs_baseline_pct > 0 ? 'text-emerald-400 font-bold' : 'text-slate-400'}>
                                        {cand.vs_baseline_pct > 0 ? `+${cand.vs_baseline_pct}%` : `${cand.vs_baseline_pct}%`}
                                      </span>
                                    ) : (
                                      <span className="text-slate-500">Baseline</span>
                                    )}
                                  </td>
                                  <td className="py-2 px-3 text-slate-400 font-mono text-[11px]">
                                    {cand.training_time_ms ? `${cand.training_time_ms}ms` : '-'}
                                  </td>
                                  <td className="py-2 px-3">
                                    {cand.is_best ? (
                                      <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px]">
                                        Best
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

                      {/* Actual vs Predicted Holdout Chart (Regression) */}
                      {actVsPredData.length > 0 && trainResult.problem_type === 'regression' && (
                        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                          <div className="text-xs font-semibold text-slate-300">
                            Holdout Actual vs Predicted Fit ({actVsPredData.length} evaluation points)
                          </div>
                          <div className="h-56 w-full rounded-lg border border-slate-800 p-2 bg-slate-950/40">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={actVsPredData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                <XAxis dataKey="sample" stroke="#94a3b8" fontSize={10} />
                                <YAxis stroke="#94a3b8" fontSize={10} />
                                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: 8, fontSize: 11 }} />
                                <Legend wrapperStyle={{ fontSize: 11 }} />
                                <Line type="monotone" dataKey="actual" stroke="#0ea5e9" strokeWidth={2} dot={{ r: 2 }} name="Actual" />
                                <Line type="monotone" dataKey="predicted" stroke="#f59e0b" strokeWidth={2} strokeDasharray="3 3" dot={{ r: 2 }} name="Predicted" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      )}

                      {/* Classification Diagnostics: Confusion Matrix & Per-Class Metrics */}
                      {trainResult.problem_type === 'classification' && trainResult.best_model.confusion_matrix && trainResult.best_model.class_labels && (
                        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
                          <div className="text-xs font-semibold text-slate-300">
                            Holdout Confusion Matrix ({trainResult.best_model.class_labels.length} Classes)
                          </div>
                          <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/60 overflow-x-auto">
                            <table className="w-full text-xs text-center border-collapse">
                              <thead>
                                <tr className="border-b border-slate-800 text-[11px] text-slate-400">
                                  <th className="p-2 text-left font-semibold text-slate-500">Actual \ Predicted</th>
                                  {trainResult.best_model.class_labels.map((lbl) => (
                                    <th key={lbl} className="p-2 font-mono text-brand-300">{lbl}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {trainResult.best_model.confusion_matrix.map((row, rIdx) => {
                                  const actualLabel = trainResult.best_model.class_labels?.[rIdx] || `Class ${rIdx}`
                                  return (
                                    <tr key={rIdx} className="border-b border-slate-800/40">
                                      <td className="p-2 text-left font-mono font-medium text-slate-300">{actualLabel}</td>
                                      {row.map((val, cIdx) => (
                                        <td
                                          key={cIdx}
                                          className={`p-2 font-mono font-bold ${
                                            rIdx === cIdx ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-400'
                                          }`}
                                        >
                                          {val}
                                        </td>
                                      ))}
                                    </tr>
                                  )
                                })}
                              </tbody>
                            </table>
                          </div>

                          {/* Per-Class Metrics Table */}
                          {trainResult.best_model.per_class_metrics && (
                            <div className="pt-1">
                              <div className="text-[11px] font-medium text-slate-400 mb-1.5">Per-Class Holdout Metrics:</div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                                {Object.entries(trainResult.best_model.per_class_metrics).map(([cls, metrics]) => (
                                  <div key={cls} className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-800 text-xs">
                                    <div className="font-semibold text-white mb-1 truncate">{cls}</div>
                                    <div className="grid grid-cols-3 gap-1 text-[11px] text-slate-400 font-mono">
                                      <div>Prec: <strong className="text-slate-200">{metrics.precision ?? '-'}</strong></div>
                                      <div>Rec: <strong className="text-slate-200">{metrics.recall ?? '-'}</strong></div>
                                      <div>F1: <strong className="text-brand-300">{metrics.f1 ?? '-'}</strong></div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Feature Importance & Global Explainability */}
                      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="text-xs font-semibold text-slate-300">
                            {showGlobalExp ? 'Global Attribution (Grouped Original Features)' : 'Feature Importance'}
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              if (!showGlobalExp && !globalExplanation) {
                                handleLoadGlobalExplanation()
                              } else {
                                setShowGlobalExp(!showGlobalExp)
                              }
                            }}
                            className="text-[10px] text-brand-400 hover:text-brand-300 bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20"
                          >
                            {loadingGlobalExp ? 'Calculating XAI...' : showGlobalExp ? 'Show Standard Importance' : 'View Global XAI'}
                          </button>
                        </div>

                        {showGlobalExp && globalExplanation ? (
                          <div className="space-y-3">
                            <div className="text-[11px] text-slate-400">
                              Evaluated mean absolute contribution across {globalExplanation.sample_rows_evaluated} dataset records:
                            </div>
                            {globalExplanation.correlation_warnings.length > 0 && (
                              <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[10px] text-amber-300 space-y-1">
                                {globalExplanation.correlation_warnings.map((w, idx) => (
                                  <div key={idx}>⚠️ {w}</div>
                                ))}
                              </div>
                            )}
                            <div className="space-y-2">
                              {globalExplanation.feature_importances.map((gi) => (
                                <div key={gi.feature} className="space-y-1">
                                  <div className="flex justify-between items-center text-[11px] text-slate-300">
                                    <span className="font-medium text-white">{gi.feature}</span>
                                    <div className="flex items-center gap-2 font-mono text-[10px]">
                                      {gi.correlated_with && gi.correlated_with.length > 0 && (
                                        <span className="text-amber-400">collinear</span>
                                      )}
                                      <span className="text-slate-400">{gi.relative_share_pct}%</span>
                                      <span className="text-slate-500">|avg|: {gi.mean_absolute_contribution.toFixed(3)}</span>
                                    </div>
                                  </div>
                                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                      className="h-full bg-indigo-500 rounded-full"
                                      style={{ width: `${Math.min(100, Math.max(2, gi.relative_share_pct))}%` }}
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {trainResult.feature_importance.slice(0, 5).map((fi) => (
                              <div key={fi.feature} className="space-y-1">
                                <div className="flex justify-between text-[11px] text-slate-300">
                                  <span>{fi.feature}</span>
                                  <span className="font-mono text-slate-400">{Math.round(fi.importance * 100)}%</span>
                                </div>
                                <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-brand-500 rounded-full"
                                    style={{ width: `${Math.round(fi.importance * 100)}%` }}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-12 rounded-xl bg-slate-900 border border-slate-800 text-center text-slate-400 space-y-3">
                <div className="text-4xl">⚡</div>
                <h3 className="text-base font-semibold text-white">Ready to Train</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Select your target and features on the left, then click <strong>Train Machine Learning Models</strong> to evaluate candidate algorithms and make real-time predictions.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
