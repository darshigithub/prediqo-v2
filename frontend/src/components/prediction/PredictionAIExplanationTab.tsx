import type {
  TrainResponse,
  PredictResponse,
  LocalExplanationResponse,
  FeasibilityResponse,
  TargetCandidate,
} from '../../types'
import AIExplanationCard from '../business/AIExplanationCard'

interface PredictionAIExplanationTabProps {
  datasetId: string
  trainResult: TrainResponse | null
  targetCandidate: TargetCandidate | null
  feasibility: FeasibilityResponse | null
  predictResult: PredictResponse | null
  localExplanation: LocalExplanationResponse | null
  activeModelId?: string
  className?: string
}

export default function PredictionAIExplanationTab({
  datasetId,
  trainResult,
  targetCandidate,
  feasibility,
  predictResult,
  localExplanation,
  activeModelId,
  className = '',
}: PredictionAIExplanationTabProps) {
  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-3 ${className}`}>
        <div className="w-12 h-12 mx-auto rounded-2xl bg-brand-50 flex items-center justify-center text-2xl">
          ✦
        </div>
        <h3 className="text-sm font-bold text-slate-800">No Model Trained for AI Explanation</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Please select a prediction target and train a machine learning model first to generate natural-language business explanations.
        </p>
      </div>
    )
  }

  const unit = targetCandidate?.unit || undefined

  // Construct structured prediction evidence payload
  // If user has run a live prediction, explain that specific prediction scenario.
  // Otherwise, explain the best model's holdout baseline.
  const predictionValue =
    predictResult !== null
      ? predictResult.prediction
      : trainResult.problem_type === 'regression'
      ? localExplanation?.baseline_reference_value ?? 0
      : trainResult.best_model.class_labels?.[0] ?? 'Default'

  const contributions =
    localExplanation?.contributions?.map((c) => ({
      feature: c.feature,
      contribution: c.contribution,
      raw_value: c.raw_value,
    })) || []

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Intro Header */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-brand-500 animate-pulse" />
              <span className="text-xs font-bold text-brand-700 uppercase tracking-wider">
                Audited Business Narrative Layer
              </span>
            </div>
            <h2 className="text-lg font-bold text-slate-900 mt-1">
              AI-Powered Explanation for {trainResult.target_column}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5 max-w-2xl">
              Generates executive-ready explanations grounded strictly in validated mathematical evidence. No hallucinated metrics, causal leaps, or unverified claims.
            </p>
          </div>

          <div className="text-right text-xs text-slate-500">
            <div>Model: <strong className="text-slate-800">{trainResult.best_model.algorithm}</strong></div>
            <div>Dataset Version: <strong className="font-mono text-slate-800">v{trainResult.dataset_version}</strong></div>
          </div>
        </div>
      </div>

      {/* Main AI Explanation Card Component */}
      <AIExplanationCard
        type="prediction"
        predictionPayload={{
          model_id: activeModelId || trainResult.model_id,
          dataset_id: datasetId,
          target_name: trainResult.target_column,
          problem_type: trainResult.problem_type,
          unit: unit,
          prediction: predictionValue,
          probabilities: predictResult?.probabilities ?? undefined,
          baseline_reference_value: localExplanation?.baseline_reference_value,
          decomposition_space: localExplanation?.decomposition_space,
          contributions: contributions,
          metrics: trainResult.best_model.metrics,
          model_metadata: {
            algorithm: trainResult.best_model.algorithm,
            model_id: trainResult.model_id,
          },
          data_quality: feasibility?.warnings ? { warnings: feasibility.warnings } : undefined,
        }}
      />
    </div>
  )
}
