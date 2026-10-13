import { Link } from 'react-router-dom'
import type {
  TrainResponse,
  PredictResponse,
  LocalExplanationResponse,
  TargetCandidate,
  FeasibilityResponse,
} from '../../types'
import PredictionInsightCard from '../business/PredictionInsightCard'
import HumanReadableXAICard from '../business/HumanReadableXAICard'
import BusinessMetricsCard from '../business/BusinessMetricsCard'
import DecisionChecklistCard from '../business/DecisionChecklistCard'

interface PredictionOverviewTabProps {
  trainResult: TrainResponse | null
  targetCandidate: TargetCandidate | null
  feasibility: FeasibilityResponse | null
  predictInputs: Record<string, any>
  onInputChange: (field: string, value: any) => void
  predicting: boolean
  onPredict: () => void
  onResetInputs: () => void
  predictResult: PredictResponse | null
  localExplanation: LocalExplanationResponse | null
  loadingLocalExp: boolean
  onNavigateTab: (tab: 'analytics' | 'explanation' | 'technical') => void
  className?: string
}

export default function PredictionOverviewTab({
  trainResult,
  targetCandidate,
  feasibility,
  predictInputs,
  onInputChange,
  predicting,
  onPredict,
  onResetInputs,
  predictResult,
  localExplanation,
  loadingLocalExp,
  onNavigateTab,
  className = '',
}: PredictionOverviewTabProps) {
  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-4 ${className}`}>
        <div className="w-14 h-14 mx-auto rounded-2xl bg-brand-50 border border-brand-100 flex items-center justify-center text-3xl">
          ⚡
        </div>
        <div>
          <h3 className="text-base font-bold text-slate-900">Configure & Train a Prediction Model</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            Select your prediction target and features in the configuration panel on the left, then click <strong>Train Machine Learning Models</strong> to benchmark algorithms and start generating predictions.
          </p>
        </div>
      </div>
    )
  }

  const isRegression = trainResult.problem_type === 'regression'
  const taskLabel = isRegression ? 'Continuous Regression' : 'Discrete Classification'
  const unit = targetCandidate?.unit || null

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. Best Model Executive Ribbon */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
                Production Model Active
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                {trainResult.best_model.algorithm}
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700">
                {taskLabel}
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 mt-1">
              Target: {trainResult.target_column}{' '}
              {unit ? <span className="text-sm font-normal text-slate-500">({unit})</span> : ''}
            </h2>
            {trainResult.best_model.selection_rationale && (
              <p className="text-xs text-slate-600 mt-1 max-w-2xl leading-relaxed">
                {trainResult.best_model.selection_rationale}
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right text-xs text-slate-500 border-r border-slate-200 pr-4">
              <div>Trained on <strong className="text-slate-800">{trainResult.training_row_count.toLocaleString()}</strong> rows</div>
              <div>Tested on <strong className="text-slate-800">{trainResult.test_row_count.toLocaleString()}</strong> holdout rows</div>
            </div>

            <div className="flex flex-col gap-1.5">
              <button
                type="button"
                onClick={() => onNavigateTab('technical')}
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors flex items-center gap-1.5"
              >
                <span>Compare {trainResult.candidate_models.length} Models</span>
                <span>→</span>
              </button>
            </div>
          </div>
        </div>

        {/* Dataset Health Note from feasibility */}
        {feasibility?.warnings && feasibility.warnings.length > 0 && (
          <div className="mt-3 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-700 text-[11px] flex items-center gap-1.5">
            <span className="font-semibold text-slate-900">Dataset Note:</span>
            <span>{feasibility.warnings[0]}</span>
          </div>
        )}

        {/* Reliability Warnings banner if present */}
        {trainResult.best_model.reliability_notes && trainResult.best_model.reliability_notes.length > 0 && (
          <div className="mt-3 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs space-y-1">
            <div className="font-semibold flex items-center gap-1.5">
              <span>⚠️</span> Model Reliability Diagnostics:
            </div>
            <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
              {trainResult.best_model.reliability_notes.map((note, idx) => (
                <li key={idx}>{note}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 2. Interactive Prediction Scenario Form & Result */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>🎯</span> Make a Live Prediction
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Enter scenario values below to compute a real-time prediction using the validated {trainResult.best_model.algorithm} model:
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onResetInputs}
              className="text-xs text-slate-500 hover:text-slate-800 font-medium px-2.5 py-1 rounded hover:bg-slate-100 transition-colors cursor-pointer"
            >
              Reset Inputs
            </button>
          </div>
        </div>

        {/* Form Inputs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {trainResult.selected_features.map((feat) => (
            <div key={feat} className="space-y-1">
              <label className="block text-[11px] font-semibold text-slate-700 truncate" title={feat}>
                {feat}
              </label>
              <input
                type="text"
                value={predictInputs[feat] ?? ''}
                onChange={(e) => onInputChange(feat, e.target.value)}
                placeholder={`Enter ${feat}`}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all"
              />
            </div>
          ))}
        </div>

        {/* Generate Prediction Action */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="button"
            disabled={predicting}
            onClick={onPredict}
            className="py-2.5 px-6 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs transition-all flex items-center gap-2 shadow-sm cursor-pointer"
          >
            {predicting ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Computing Prediction...</span>
              </>
            ) : (
              <>
                <span>▶</span>
                <span>Generate Prediction</span>
              </>
            )}
          </button>
          <span className="text-[11px] text-slate-400">
            Validated against {trainResult.selected_features.length} required features
          </span>
        </div>

        {/* Prediction Result Display */}
        {predictResult && (
          <div className="pt-2 space-y-4">
            <PredictionInsightCard
              result={predictResult}
              targetName={trainResult.target_column}
              problemType={trainResult.problem_type}
              unit={unit}
              baselineValue={localExplanation?.baseline_reference_value}
            />

            {/* Input Summary Pill List */}
            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1.5">
              <div className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
                Scenario Inputs Supplied for this Prediction:
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(predictInputs).map(([k, v]) => (
                  <span
                    key={k}
                    className="px-2 py-1 rounded bg-white border border-slate-200 text-slate-700 text-[11px] font-mono shadow-2xs"
                  >
                    <strong className="text-slate-900">{k}</strong>: {String(v || '—')}
                  </span>
                ))}
              </div>
            </div>

            {/* Loading XAI indicator */}
            {loadingLocalExp && (
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-500 flex items-center gap-2">
                <div className="w-3.5 h-3.5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                <span>Computing mathematically verified feature contributions...</span>
              </div>
            )}

            {/* Local Explainable AI (XAI) Waterfall/Drivers */}
            {localExplanation && (
              <HumanReadableXAICard
                localExplanation={localExplanation}
                targetName={trainResult.target_column}
                unit={unit}
              />
            )}
          </div>
        )}
      </div>

      {/* 3. Reliability Summary & Baseline Comparison */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>📊</span> Evaluation Reliability & Baseline Uplift
          </h3>
          <button
            type="button"
            onClick={() => onNavigateTab('analytics')}
            className="text-xs text-brand-600 hover:text-brand-800 font-semibold cursor-pointer"
          >
            View Complete Performance Analytics →
          </button>
        </div>

        <BusinessMetricsCard
          type={trainResult.problem_type}
          metrics={trainResult.best_model.metrics}
          targetName={trainResult.target_column}
          unit={unit}
          classLabels={trainResult.best_model.class_labels}
          vsBaselinePct={trainResult.best_model.vs_baseline_pct}
        />
      </div>

      {/* 4. Actionable Next Steps Bar */}
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
            Inspect holdout actual vs predicted fit, confusion matrices, and global driver attributions.
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
            Generate audited executive summaries and plain-language interpretations using local Ollama or cloud LLMs.
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
            Pass this prediction to configured operational rules for automated action recommendations.
          </p>
        </Link>
      </div>

      {/* 5. Pre-Decision Operational Checklist */}
      <DecisionChecklistCard type="prediction" />
    </div>
  )
}
