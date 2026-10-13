import { useState } from 'react'
import type {
  FeasibilityResponse,
  TargetCandidate,
  ModelListItem,
} from '../../types'

interface PredictionConfigPanelProps {
  feasibility: FeasibilityResponse | null
  loadingFeasibility: boolean
  selectedTarget: string
  onTargetChange: (target: string) => void
  targetCandidate: TargetCandidate | null
  selectedFeatures: string[]
  onFeaturesChange: (features: string[]) => void
  excludedFeatures: string[]
  cvFolds: number
  onCvFoldsChange: (folds: number) => void
  validationStrategy: string
  onValidationStrategyChange: (strategy: string) => void
  selectedGroupCol: string
  onGroupColChange: (col: string) => void
  training: boolean
  onTrain: () => void
  savedModels: ModelListItem[]
  activeModelId: string
  onSelectSavedModel: (modelId: string, targetCol: string) => void
  className?: string
}

export default function PredictionConfigPanel({
  feasibility,
  loadingFeasibility,
  selectedTarget,
  onTargetChange,
  targetCandidate,
  selectedFeatures,
  onFeaturesChange,
  excludedFeatures,
  cvFolds,
  onCvFoldsChange,
  validationStrategy,
  onValidationStrategyChange,
  selectedGroupCol,
  onGroupColChange,
  training,
  onTrain,
  savedModels,
  activeModelId,
  onSelectSavedModel,
  className = '',
}: PredictionConfigPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  if (loadingFeasibility) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4 ${className}`}>
        <div className="flex items-center gap-2 text-slate-500 text-xs">
          <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Analyzing dataset features and target compatibility...</span>
        </div>
      </div>
    )
  }

  if (!feasibility || !feasibility.prediction_possible) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3 ${className}`}>
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs">
          <strong>Cannot Configure Prediction:</strong>
          <p className="mt-1">
            {feasibility?.warnings?.[0] || 'Dataset does not meet minimum row or feature requirements.'}
          </p>
        </div>
      </div>
    )
  }

  const allTargets = [
    ...feasibility.regression_targets,
    ...feasibility.classification_targets,
  ]

  const featureCandidates: TargetCandidate[] = allTargets.filter((t) => t.name !== selectedTarget)

  const toggleFeature = (feat: string) => {
    if (selectedFeatures.includes(feat)) {
      onFeaturesChange(selectedFeatures.filter((f) => f !== feat))
    } else {
      onFeaturesChange([...selectedFeatures, feat])
    }
  }

  const selectAllFeatures = () => {
    onFeaturesChange(featureCandidates.map((f: TargetCandidate) => f.name))
  }

  const clearAllFeatures = () => {
    onFeaturesChange([])
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Model Setup Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
            <span>⚙️</span>
            <span>Target & Feature Setup</span>
          </h2>
          <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
            v{feasibility.dataset_version}
          </span>
        </div>

        {/* 1. Target Selector */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700">
            Prediction Target Column <span className="text-rose-500">*</span>
          </label>
          <select
            value={selectedTarget}
            onChange={(e) => onTargetChange(e.target.value)}
            className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium text-slate-800 shadow-sm focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
          >
            {allTargets.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name} ({t.problem_type === 'regression' ? 'Numeric / Regression' : 'Categorical / Classification'})
              </option>
            ))}
          </select>
          {targetCandidate && (
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className="px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 font-semibold border border-brand-200 text-[10px]">
                {targetCandidate.problem_type.toUpperCase()}
              </span>
              {targetCandidate.unit && (
                <span>Unit: <strong className="text-slate-700">{targetCandidate.unit}</strong></span>
              )}
              {targetCandidate.classes && targetCandidate.classes.length > 0 && (
                <span>{targetCandidate.classes.length} distinct classes</span>
              )}
            </div>
          )}
        </div>

        {/* 2. Feature Selection */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-700">
              Features for Training ({selectedFeatures.length}/{featureCandidates.length})
            </label>
            <div className="flex gap-2 text-[11px]">
              <button
                type="button"
                onClick={selectAllFeatures}
                className="text-brand-600 hover:text-brand-800 font-medium cursor-pointer"
              >
                Select All
              </button>
              <span className="text-slate-300">|</span>
              <button
                type="button"
                onClick={clearAllFeatures}
                className="text-slate-500 hover:text-slate-700 font-medium cursor-pointer"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="max-h-44 overflow-y-auto rounded-lg border border-slate-200 p-2 space-y-1 bg-slate-50/50">
            {featureCandidates.map((f: TargetCandidate) => {
              const isChecked = selectedFeatures.includes(f.name)
              return (
                <label
                  key={f.name}
                  className={`flex items-center justify-between p-1.5 rounded cursor-pointer text-xs transition-colors ${
                    isChecked ? 'bg-brand-50/60 text-slate-900 font-medium' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleFeature(f.name)}
                      className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                    />
                    <span className="truncate">{f.display_name || f.name}</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400 shrink-0 ml-2">
                    {f.dtype}
                  </span>
                </label>
              )
            })}
          </div>
        </div>

        {/* Excluded Features notice */}
        {excludedFeatures.length > 0 && (
          <div className="pt-2 border-t border-slate-100">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Protected / Excluded Columns (Target & IDs):
            </span>
            <div className="flex flex-wrap gap-1">
              {excludedFeatures.map((f) => (
                <span key={f} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-[10px] font-mono">
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 3. Advanced CV Settings Accordion */}
        <div className="pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center justify-between w-full text-xs font-semibold text-slate-600 hover:text-slate-900 cursor-pointer"
          >
            <span>Advanced Cross-Validation Options</span>
            <span className="text-slate-400">{showAdvanced ? '▲' : '▼'}</span>
          </button>

          {showAdvanced && (
            <div className="mt-3 space-y-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">
                  Validation Strategy
                </label>
                <select
                  value={validationStrategy}
                  onChange={(e) => onValidationStrategyChange(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-brand-500"
                >
                  <option value="kfold">K-Fold Cross-Validation</option>
                  <option value="stratified">Stratified K-Fold (Classification)</option>
                  <option value="group">Group K-Fold</option>
                </select>
              </div>

              {validationStrategy === 'group' && (
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">
                    Group Column
                  </label>
                  <select
                    value={selectedGroupCol}
                    onChange={(e) => onGroupColChange(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
                  >
                    <option value="">Select Group Identifier</option>
                    {featureCandidates.map((f: TargetCandidate) => (
                      <option key={f.name} value={f.name}>
                        {f.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">
                  Cross-Validation Folds
                </label>
                <select
                  value={cvFolds}
                  onChange={(e) => onCvFoldsChange(Number(e.target.value))}
                  className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
                >
                  <option value={3}>3-Fold Cross-Validation</option>
                  <option value={5}>5-Fold K-Fold (Recommended)</option>
                  <option value={10}>10-Fold K-Fold</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* 4. Train Action Button */}
        <button
          type="button"
          disabled={training || selectedFeatures.length === 0}
          onClick={onTrain}
          className="w-full py-2.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-xs transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer"
        >
          {training ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <span>Training & Benchmarking Models...</span>
            </>
          ) : (
            <>
              <span>⚡</span>
              <span>Train Machine Learning Models</span>
            </>
          )}
        </button>
      </div>

      {/* Saved Models List Card */}
      {savedModels.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              Saved Models ({savedModels.length})
            </span>
            <span className="text-[10px] text-slate-400 font-mono">Joblib Store</span>
          </div>

          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {savedModels.map((m) => {
              const isActive = activeModelId === m.model_id
              return (
                <div
                  key={m.model_id}
                  onClick={() => onSelectSavedModel(m.model_id, m.target_column)}
                  className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                    isActive
                      ? 'bg-brand-50 border-brand-400 text-brand-900 shadow-sm'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300'
                  }`}
                >
                  <div className="flex justify-between items-center mb-0.5">
                    <strong className="text-slate-900 font-semibold">{m.target_column}</strong>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-brand-700 font-medium">
                      {m.algorithm}
                    </span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-500">
                    <span>
                      {m.primary_metric.toUpperCase()}:{' '}
                      <strong className="text-slate-700">{m.primary_metric_value}</strong>
                    </span>
                    <span className="font-mono">v{m.dataset_version}</span>
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
