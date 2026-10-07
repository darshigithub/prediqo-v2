import { useEffect, useState } from 'react'
import DatasetPicker from '../components/DatasetPicker'
import {
  getPredictionFeasibility,
  trainPredictionModel,
  listPredictionModels,
  predictSingle,
} from '../services/api'
import type {
  FeasibilityResponse,
  TargetCandidate,
  TrainResponse,
  PredictResponse,
  ModelListItem,
} from '../types'

export default function PredictionPage() {
  const [datasetId, setDatasetId] = useState<string>('')
  const [feasibility, setFeasibility] = useState<FeasibilityResponse | null>(null)
  const [loadingFeasibility, setLoadingFeasibility] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Configuration state
  const [selectedTarget, setSelectedTarget] = useState<string>('')
  const [targetCandidate, setTargetCandidate] = useState<TargetCandidate | null>(null)
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])
  const [excludedFeatures, setExcludedFeatures] = useState<string[]>([])

  // Training state
  const [training, setTraining] = useState<boolean>(false)
  const [trainResult, setTrainResult] = useState<TrainResponse | null>(null)
  const [modelsList, setModelsList] = useState<ModelListItem[]>([])

  // Inference state
  const [activeModelId, setActiveModelId] = useState<string>('')
  const [predictInputs, setPredictInputs] = useState<Record<string, any>>({})
  const [predicting, setPredicting] = useState<boolean>(false)
  const [predictResult, setPredictResult] = useState<PredictResponse | null>(null)

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
        // Select recommended target by default
        const defaultTarget = data.recommended_targets[0] ||
          data.regression_targets[0]?.name ||
          data.classification_targets[0]?.name || ''
        setSelectedTarget(defaultTarget)
      })
      .catch((err) => {
        setError(err.message || 'Failed to check prediction feasibility.')
      })
      .finally(() => {
        setLoadingFeasibility(false)
      })

    // Fetch existing models for this dataset
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

    // All columns from candidates + excluded
    // Exclude target and obvious identifiers by default
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
    ].map((c) => c.name).filter((n) => n !== selectedTarget)
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

    try {
      const res = await trainPredictionModel({
        dataset_id: datasetId,
        target_column: selectedTarget,
        problem_type: targetCandidate.problem_type,
        features: selectedFeatures,
      })
      setTrainResult(res)
      setActiveModelId(res.model_id)

      // Initialize predict inputs with empty/default values
      const initialInputs: Record<string, any> = {}
      res.selected_features.forEach((feat) => {
        initialInputs[feat] = ''
      })
      setPredictInputs(initialInputs)

      // Refresh model list
      const updatedModels = await listPredictionModels(datasetId, true)
      setModelsList(updatedModels.models || [])
    } catch (err: any) {
      setError(err.message || 'Model training failed.')
    } finally {
      setTraining(false)
    }
  }

  // 4. Run Prediction
  const handlePredict = async () => {
    if (!activeModelId) return
    setPredicting(true)
    setError(null)

    try {
      // Coerce inputs if numeric
      const processed: Record<string, any> = {}
      Object.entries(predictInputs).forEach(([k, v]) => {
        if (v === '' || v === null || v === undefined) {
          processed[k] = null
        } else if (!isNaN(Number(v)) && v.trim?.() !== '') {
          processed[k] = Number(v)
        } else {
          processed[k] = v
        }
      })

      const res = await predictSingle(activeModelId, processed)
      setPredictResult(res)
    } catch (err: any) {
      setError(err.message || 'Prediction failed.')
    } finally {
      setPredicting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-black flex items-center gap-2">
          <span>⚡</span> ML Prediction
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Automated supervised machine learning: train candidate models, compare metrics, and make instant predictions.
        </p>
      </div>

      {/* Dataset Picker */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Dataset:</span>
          <DatasetPicker value={datasetId} onChange={setDatasetId} />
        </div>

        {feasibility && (
          <div className="flex items-center gap-3 text-xs">
            <span className="text-slate-400">Rows: <strong className="text-white">{feasibility.row_count.toLocaleString()}</strong></span>
            <span className="text-slate-400">Version: <strong className="text-brand-400">v{feasibility.dataset_version}</strong></span>
            <span className={`px-2 py-0.5 rounded font-medium ${
              feasibility.prediction_possible
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
            }`}>
              {feasibility.prediction_possible ? '✓ ML Ready' : '✕ Not Feasible'}
            </span>
          </div>
        )}
      </div>

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
          <div>Checking prediction feasibility...</div>
        </div>
      )}

      {feasibility && feasibility.prediction_possible && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Target & Feature Configuration */}
          <div className="lg:col-span-1 space-y-6">
            <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-5">
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                1. Prediction Configuration
              </h2>

              {/* Target Selection */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  What do you want to predict?
                </label>
                <select
                  value={selectedTarget}
                  onChange={(e) => setSelectedTarget(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
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

                {targetCandidate && (
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                    <span>Problem Type:</span>
                    <span className={`px-2 py-0.5 rounded font-semibold uppercase text-[10px] ${
                      targetCandidate.problem_type === 'regression'
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    }`}>
                      {targetCandidate.problem_type}
                    </span>
                  </div>
                )}
              </div>

              {/* Feature Checklist */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-slate-300">
                    Recommended Features ({selectedFeatures.length} selected)
                  </label>
                  <div className="flex gap-2 text-[11px] text-brand-400">
                    <button type="button" onClick={selectAllFeatures} className="hover:underline">All</button>
                    <span>·</span>
                    <button type="button" onClick={deselectAllFeatures} className="hover:underline">None</button>
                  </div>
                </div>

                <div className="max-h-56 overflow-y-auto space-y-1.5 p-2 bg-slate-950/50 rounded-lg border border-slate-800">
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
                          <span className={isChecked ? 'text-white' : 'text-slate-400'}>
                            {col.display_name || col.name}
                          </span>
                          <span className="ml-auto text-[10px] text-slate-500 font-mono">
                            {col.business_role}
                          </span>
                        </label>
                      )
                    })}
                </div>
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
                className="w-full py-2.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-medium text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-brand-500/10"
              >
                {training ? (
                  <>
                    <span className="inline-block animate-spin">⚙</span>
                    <span>Training Candidate Models...</span>
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
                <div className="space-y-2">
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
                        <span>{m.primary_metric.toUpperCase()}: <strong className="text-white">{m.primary_metric_value}</strong></span>
                        <span>v{m.dataset_version}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Columns: Performance & Interactive Inference */}
          <div className="lg:col-span-2 space-y-6">
            {/* Model Evaluation & Performance */}
            {trainResult ? (
              <div className="space-y-6">
                {/* Best Model Summary Card */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                        <span>★</span> Best Performing Model
                      </div>
                      <h3 className="text-lg font-bold text-white mt-0.5">
                        {trainResult.best_model.algorithm}
                      </h3>
                    </div>
                    <div className="text-right text-xs text-slate-400">
                      <div>Train: <strong className="text-white">{trainResult.training_row_count}</strong> rows</div>
                      <div>Test: <strong className="text-white">{trainResult.test_row_count}</strong> rows</div>
                    </div>
                  </div>

                  {/* Primary Metrics */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {Object.entries(trainResult.best_model.metrics)
                      .filter(([k]) => k !== 'averaging')
                      .map(([key, val]) => (
                        <div key={key} className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/50">
                          <div className="text-[10px] font-semibold text-slate-400 uppercase">{key}</div>
                          <div className="text-lg font-bold text-white mt-0.5">{String(val)}</div>
                        </div>
                      ))}
                  </div>

                  {/* Candidate Comparison Table */}
                  <div className="pt-2">
                    <div className="text-xs font-semibold text-slate-300 mb-2">
                      Candidate Model Comparison
                    </div>
                    <div className="overflow-x-auto rounded-lg border border-slate-800">
                      <table className="w-full text-xs text-left text-slate-300">
                        <thead className="bg-slate-800/80 text-slate-400">
                          <tr>
                            <th className="py-2 px-3">Algorithm</th>
                            {trainResult.problem_type === 'regression' ? (
                              <>
                                <th className="py-2 px-3">MAE (Lower is better)</th>
                                <th className="py-2 px-3">RMSE</th>
                                <th className="py-2 px-3">R²</th>
                              </>
                            ) : (
                              <>
                                <th className="py-2 px-3">Accuracy</th>
                                <th className="py-2 px-3">Precision</th>
                                <th className="py-2 px-3">Recall</th>
                                <th className="py-2 px-3">F1 Score</th>
                              </>
                            )}
                            <th className="py-2 px-3">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {trainResult.candidate_models.map((cand) => (
                            <tr key={cand.algorithm} className={cand.is_best ? 'bg-emerald-500/10 font-semibold' : ''}>
                              <td className="py-2 px-3 text-white">{cand.algorithm}</td>
                              {trainResult.problem_type === 'regression' ? (
                                <>
                                  <td className="py-2 px-3">{cand.metrics.mae ?? '-'}</td>
                                  <td className="py-2 px-3">{cand.metrics.rmse ?? '-'}</td>
                                  <td className="py-2 px-3">{cand.metrics.r2 ?? '-'}</td>
                                </>
                              ) : (
                                <>
                                  <td className="py-2 px-3">{cand.metrics.accuracy ?? '-'}</td>
                                  <td className="py-2 px-3">{cand.metrics.precision ?? '-'}</td>
                                  <td className="py-2 px-3">{cand.metrics.recall ?? '-'}</td>
                                  <td className="py-2 px-3">{cand.metrics.f1 ?? '-'}</td>
                                </>
                              )}
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

                  {/* Feature Importance */}
                  {trainResult.feature_importance.length > 0 && (
                    <div className="pt-2">
                      <div className="text-xs font-semibold text-slate-300 mb-2">
                        Feature Importance
                      </div>
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
                    </div>
                  )}
                </div>

                {/* Interactive Prediction Form */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
                  <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                    <span>🎯</span> Make a Live Prediction
                  </h3>
                  <p className="text-xs text-slate-400">
                    Input custom values to test the trained model ({trainResult.best_model.algorithm}):
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {trainResult.selected_features.map((feat) => (
                      <div key={feat}>
                        <label className="block text-[11px] font-medium text-slate-400 mb-1">
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
                          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-brand-500"
                        />
                      </div>
                    ))}
                  </div>

                  <button
                    type="button"
                    disabled={predicting}
                    onClick={handlePredict}
                    className="py-2 px-5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium text-xs transition-all flex items-center gap-2 shadow-lg shadow-emerald-500/10"
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
                    <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 space-y-2">
                      <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                        Predicted Result
                      </div>
                      <div className="text-2xl font-bold text-white">
                        {String(predictResult.prediction)}
                        {predictResult.unit ? ` ${predictResult.unit}` : ''}
                      </div>

                      {predictResult.probabilities && (
                        <div className="pt-2 border-t border-emerald-500/20 space-y-1.5">
                          <div className="text-[11px] font-medium text-slate-300">Class Probabilities:</div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                            {Object.entries(predictResult.probabilities).map(([cls, prob]) => (
                              <div key={cls} className="p-2 rounded bg-slate-900/60 border border-slate-800 text-xs">
                                <div className="text-slate-400 truncate">{cls}</div>
                                <div className="font-bold text-emerald-300">{Math.round(prob * 100)}%</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <p className="text-xs text-slate-300 pt-1">
                        {predictResult.explanation}
                      </p>
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
