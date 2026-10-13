import { useState, useEffect } from 'react'
import type { EvaluationRequest, DecisionEvaluation } from '../../types/decisionTypes'
import { evaluateDecision } from '../../services/decisionApi'
import { listDatasets, listPredictionModels, listForecastModels } from '../../services/api'
import type { DatasetListItem, ModelListItem, ForecastModelListItem } from '../../types'

interface DecisionEvaluateModalProps {
  onClose: () => void
  onEvaluationCompleted: (evaluation: DecisionEvaluation) => void
}

interface KeyVal {
  key: string
  value: string
}

export default function DecisionEvaluateModal({
  onClose,
  onEvaluationCompleted,
}: DecisionEvaluateModalProps) {
  const [scenario, setScenario] = useState('inventory')
  const [datasetId, setDatasetId] = useState<string>('')
  const [predictionModelId, setPredictionModelId] = useState<string>('')
  const [forecastModelId, setForecastModelId] = useState<string>('')

  // Available options from backend
  const [datasets, setDatasets] = useState<DatasetListItem[]>([])
  const [predictionModels, setPredictionModels] = useState<ModelListItem[]>([])
  const [forecastModels, setForecastModels] = useState<ForecastModelListItem[]>([])
  const [loadingDatasets, setLoadingDatasets] = useState(false)

  // Operational facts as key-value pairs
  const [operationalFacts, setOperationalFacts] = useState<KeyVal[]>([
    { key: 'available_inventory', value: '150' },
    { key: 'safety_stock', value: '50' },
    { key: 'lead_time_days', value: '7' },
  ])

  // Prediction inputs
  const [predictionInputsRaw, setPredictionInputsRaw] = useState<string>('')

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<DecisionEvaluation | null>(null)

  // Load datasets on mount
  useEffect(() => {
    let active = true
    setLoadingDatasets(true)
    listDatasets()
      .then((res) => {
        if (active) setDatasets(res.datasets || [])
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoadingDatasets(false)
      })
    return () => {
      active = false
    }
  }, [])

  // Load models when dataset changes
  useEffect(() => {
    if (!datasetId) {
      setPredictionModels([])
      setForecastModels([])
      setPredictionModelId('')
      setForecastModelId('')
      return
    }

    listPredictionModels(datasetId)
      .then((res) => setPredictionModels(res.models || []))
      .catch(() => setPredictionModels([]))

    listForecastModels(datasetId)
      .then((res) => setForecastModels(res.models || []))
      .catch(() => setForecastModels([]))
  }, [datasetId])

  // Update operational fact defaults when scenario changes
  const handleScenarioChange = (newScenario: string) => {
    setScenario(newScenario)
    if (newScenario === 'inventory') {
      setOperationalFacts([
        { key: 'available_inventory', value: '150' },
        { key: 'safety_stock', value: '50' },
        { key: 'lead_time_days', value: '7' },
      ])
    } else if (newScenario === 'demand') {
      setOperationalFacts([
        { key: 'available_capacity', value: '500' },
        { key: 'lead_time_days', value: '14' },
      ])
    } else if (newScenario === 'churn') {
      setOperationalFacts([
        { key: 'tenure_months', value: '6' },
        { key: 'monthly_spend', value: '85' },
      ])
    } else if (newScenario === 'data_quality') {
      setOperationalFacts([
        { key: 'missing_threshold', value: '0.15' },
      ])
    } else {
      setOperationalFacts([{ key: 'operational_budget', value: '10000' }])
    }
  }

  const handleAddFact = () => {
    setOperationalFacts([...operationalFacts, { key: '', value: '' }])
  }

  const handleRemoveFact = (index: number) => {
    setOperationalFacts(operationalFacts.filter((_, i) => i !== index))
  }

  const handleUpdateFact = (index: number, field: 'key' | 'value', val: string) => {
    const updated = [...operationalFacts]
    updated[index][field] = val
    setOperationalFacts(updated)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)

    // Build operational facts dictionary
    const factsObj: Record<string, any> = {}
    for (const item of operationalFacts) {
      if (item.key.trim()) {
        const num = Number(item.value.trim())
        factsObj[item.key.trim()] = isNaN(num) || item.value.trim() === '' ? item.value.trim() : num
      }
    }

    // Parse prediction inputs JSON if provided
    let parsedPredInputs: Record<string, any> | undefined = undefined
    if (predictionInputsRaw.trim()) {
      try {
        parsedPredInputs = JSON.parse(predictionInputsRaw.trim())
      } catch (err: any) {
        setError('Prediction inputs must be a valid JSON object.')
        setIsSubmitting(false)
        return
      }
    }

    const payload: EvaluationRequest = {
      scenario,
      dataset_id: datasetId || null,
      prediction_model_id: predictionModelId || null,
      forecast_model_id: forecastModelId || null,
      operational_facts: factsObj,
      prediction_inputs: parsedPredInputs || null,
      actor: 'user',
    }

    try {
      const evaluation = await evaluateDecision(payload)
      setResult(evaluation)
      onEvaluationCompleted(evaluation)
    } catch (err: any) {
      setError(err.message || 'Decision evaluation failed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white border border-slate-200 rounded-2xl shadow-2xl p-6 sm:p-7 space-y-6 text-slate-800 my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <span>▶ Run Decision Evaluation</span>
            </h3>
            <p className="text-xs text-slate-600 mt-0.5">
              Evaluate active deterministic rules against predictions, forecasts, and operational context.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs">
            {error}
          </div>
        )}

        {/* Results Screen if already evaluated */}
        {result ? (
          <div className="space-y-5 py-2">
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-950 space-y-2">
              <div className="font-bold text-sm flex items-center gap-2">
                <span>✓ Evaluation Completed Successfully</span>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                  {result.evaluation_id.slice(0, 8)}...
                </span>
              </div>
              <p className="text-xs text-emerald-800">
                Processed {result.total_rules_evaluated} rules for scenario <strong>{result.scenario.toUpperCase()}</strong>.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-[10px] text-slate-600 uppercase font-semibold block">Triggered</span>
                <span className="text-2xl font-extrabold text-emerald-700 font-mono">
                  {result.triggered_rules_count}
                </span>
              </div>
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-[10px] text-slate-600 uppercase font-semibold block">Not Triggered</span>
                <span className="text-2xl font-extrabold text-slate-500 font-mono">
                  {result.not_triggered_rules_count}
                </span>
              </div>
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-[10px] text-slate-600 uppercase font-semibold block">Not Evaluable</span>
                <span className={`text-2xl font-extrabold font-mono ${result.not_evaluable_rules_count > 0 ? 'text-amber-700' : 'text-slate-500'}`}>
                  {result.not_evaluable_rules_count}
                </span>
              </div>
            </div>

            {result.missing_evidence.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
                <span className="font-bold block">Missing Operational Facts / Evidence Disclosures:</span>
                <p className="text-[11px] text-amber-800">
                  Rules requiring the following evidence fields could not be evaluated:
                </p>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {result.missing_evidence.map((me, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-mono text-[10px] border border-amber-300">
                      {me}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <span className="text-xs font-bold text-slate-800 block">
                Generated Recommendations ({result.recommendations.length}):
              </span>
              {result.recommendations.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No business rules triggered. No action required.</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {result.recommendations.map((rec) => (
                    <div key={rec.recommendation_id} className="p-2.5 rounded-lg bg-white border border-slate-200 text-xs flex items-center justify-between gap-3 shadow-sm">
                      <div>
                        <div className="font-bold text-slate-900">{rec.title}</div>
                        <div className="text-[11px] text-emerald-800 font-medium">{rec.recommended_action}</div>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold bg-slate-100 text-slate-700 border border-slate-200">
                        {rec.priority}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors cursor-pointer"
              >
                Close & View Decision Center
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Scenario Picker */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Business Scenario
              </label>
              <select
                value={scenario}
                onChange={(e) => handleScenarioChange(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white"
              >
                <option value="inventory">Inventory Management (Safety stock, reorder points, shortages)</option>
                <option value="demand">Demand Planning (Capacity limits, spike alerts, forecast trends)</option>
                <option value="churn">Customer Churn & Retention (High risk probability interventions)</option>
                <option value="data_quality">Data Quality & Readiness (Missingness & drift thresholds)</option>
                <option value="general">General Operations / Multi-factor Policy</option>
              </select>
            </div>

            {/* Dataset Link (Optional) */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Link Existing Dataset (Optional)
              </label>
              <select
                value={datasetId}
                onChange={(e) => setDatasetId(e.target.value)}
                disabled={loadingDatasets}
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white disabled:opacity-50"
              >
                <option value="">None / Manual operational facts only</option>
                {datasets.map((ds) => (
                  <option key={ds.dataset_id} value={ds.dataset_id}>
                    {ds.dataset_name} ({ds.rows?.toLocaleString() ?? 0} rows)
                  </option>
                ))}
              </select>
            </div>

            {/* If Dataset is Selected: Model Links */}
            {datasetId && (
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    Prediction Model
                  </label>
                  <select
                    value={predictionModelId}
                    onChange={(e) => setPredictionModelId(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-brand-500"
                  >
                    <option value="">None</option>
                    {predictionModels.map((m) => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.target_column} ({m.algorithm || m.problem_type})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    Forecast Model
                  </label>
                  <select
                    value={forecastModelId}
                    onChange={(e) => setForecastModelId(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-brand-500"
                  >
                    <option value="">None</option>
                    {forecastModels.map((f) => (
                      <option key={f.model_id} value={f.model_id}>
                        {f.metric_column} ({f.frequency}, {f.algorithm})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Prediction Inputs JSON if prediction model selected */}
            {predictionModelId && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Prediction Features / Single Record Inputs (JSON)
                </label>
                <textarea
                  rows={2}
                  value={predictionInputsRaw}
                  onChange={(e) => setPredictionInputsRaw(e.target.value)}
                  placeholder='{"feature_1": 42, "category": "retail"}'
                  className="w-full px-3 py-2 text-xs font-mono bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:bg-white"
                />
              </div>
            )}

            {/* Operational Facts Key-Value Editor */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-semibold text-slate-700">
                  Operational Facts & Threshold Inputs
                </label>
                <button
                  type="button"
                  onClick={handleAddFact}
                  className="text-[11px] text-brand-600 hover:text-brand-800 font-semibold cursor-pointer"
                >
                  + Add Fact
                </button>
              </div>

              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {operationalFacts.map((fact, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={fact.key}
                      onChange={(e) => handleUpdateFact(idx, 'key', e.target.value)}
                      placeholder="field_name (e.g. available_inventory)"
                      className="flex-1 px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 font-mono placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:bg-white"
                    />
                    <input
                      type="text"
                      value={fact.value}
                      onChange={(e) => handleUpdateFact(idx, 'value', e.target.value)}
                      placeholder="value (e.g. 150)"
                      className="flex-1 px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 font-mono placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:bg-white"
                    />
                    <button
                      type="button"
                      onClick={() => handleRemoveFact(idx)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 rounded hover:bg-slate-100 transition-colors cursor-pointer"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Non-causal disclosure badge */}
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-[11px] text-slate-600 leading-relaxed">
              <span className="font-semibold text-slate-800">Governance Notice:</span> Recommendations are synthesized deterministically based on configured business thresholds. They reflect correlation and operational risk boundaries, not guaranteed causal outcomes.
            </div>

            {/* Modal Actions */}
            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors disabled:opacity-50 flex items-center gap-2 cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Evaluating Rules...</span>
                  </>
                ) : (
                  <span>Run Deterministic Evaluation</span>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
