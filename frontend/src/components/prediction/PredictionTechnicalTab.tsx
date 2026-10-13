import type { TrainResponse, TargetCandidate } from '../../types'

interface PredictionTechnicalTabProps {
  trainResult: TrainResponse | null
  targetCandidate: TargetCandidate | null
  className?: string
}

export default function PredictionTechnicalTab({
  trainResult,
  targetCandidate,
  className = '',
}: PredictionTechnicalTabProps) {
  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-3 ${className}`}>
        <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center text-2xl">
          ⚙️
        </div>
        <h3 className="text-sm font-bold text-slate-800">No Technical Details Available</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Train a machine learning model to inspect candidate algorithm benchmarks, cross-validation variance, and model metadata.
        </p>
      </div>
    )
  }

  const isRegression = trainResult.problem_type === 'regression'

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. Candidate Model Comparison Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>🔬</span> Candidate Model Benchmarks & Cross-Validation
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Comparative holdout and K-Fold cross-validation metrics across evaluated algorithms.
            </p>
          </div>
          <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded">
            {trainResult.candidate_models.length} Candidates Evaluated
          </span>
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-xs text-left text-slate-700">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Algorithm</th>
                {isRegression ? (
                  <>
                    <th className="py-2.5 px-3">CV MAE (Primary)</th>
                    <th className="py-2.5 px-3">Holdout MAE</th>
                    <th className="py-2.5 px-3">RMSE</th>
                    <th className="py-2.5 px-3">R²</th>
                  </>
                ) : (
                  <>
                    <th className="py-2.5 px-3">CV F1 (Primary)</th>
                    <th className="py-2.5 px-3">Holdout Accuracy</th>
                    <th className="py-2.5 px-3">Precision</th>
                    <th className="py-2.5 px-3">F1 Score</th>
                  </>
                )}
                <th className="py-2.5 px-3">vs Baseline</th>
                <th className="py-2.5 px-3">Duration</th>
                <th className="py-2.5 px-3">Selection</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {trainResult.candidate_models.map((cand) => (
                <tr
                  key={cand.algorithm}
                  className={cand.is_best ? 'bg-emerald-50/50 font-semibold' : 'hover:bg-slate-50/80'}
                >
                  <td className="py-2.5 px-3 text-slate-900">
                    {cand.algorithm}
                  </td>
                  {isRegression ? (
                    <>
                      <td className="py-2.5 px-3 text-brand-700 font-bold">
                        {cand.cv_metrics?.cv_mae ?? '-'}
                        {cand.cv_metrics?.cv_mae_std ? ` ± ${cand.cv_metrics.cv_mae_std}` : ''}
                      </td>
                      <td className="py-2.5 px-3">{cand.metrics.mae ?? '-'}</td>
                      <td className="py-2.5 px-3">{cand.metrics.rmse ?? '-'}</td>
                      <td className="py-2.5 px-3">{cand.metrics.r2 ?? '-'}</td>
                    </>
                  ) : (
                    <>
                      <td className="py-2.5 px-3 text-brand-700 font-bold">
                        {cand.cv_metrics?.cv_f1 ?? '-'}
                        {cand.cv_metrics?.cv_f1_std ? ` ± ${cand.cv_metrics.cv_f1_std}` : ''}
                      </td>
                      <td className="py-2.5 px-3">{cand.metrics.accuracy ?? '-'}</td>
                      <td className="py-2.5 px-3">{cand.metrics.precision ?? '-'}</td>
                      <td className="py-2.5 px-3">{cand.metrics.f1 ?? '-'}</td>
                    </>
                  )}
                  <td className="py-2.5 px-3 font-mono text-[11px]">
                    {cand.vs_baseline_pct !== null && cand.vs_baseline_pct !== undefined ? (
                      <span
                        className={
                          cand.vs_baseline_pct > 0
                            ? 'text-emerald-700 font-bold'
                            : 'text-slate-500'
                        }
                      >
                        {cand.vs_baseline_pct > 0 ? `+${cand.vs_baseline_pct}%` : `${cand.vs_baseline_pct}%`}
                      </span>
                    ) : (
                      <span className="text-slate-400">Baseline</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px]">
                    {cand.training_time_ms ? `${cand.training_time_ms}ms` : '-'}
                  </td>
                  <td className="py-2.5 px-3">
                    {cand.is_best ? (
                      <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                        ★ Best Model
                      </span>
                    ) : (
                      <span className="text-slate-400 text-[11px]">Evaluated</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 2. Architecture & Pipeline Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>⚙️</span> Training & Validation Configuration
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Validation Strategy:</span>
              <strong className="text-slate-800 capitalize">{trainResult.validation_strategy || 'K-Fold CV'}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Cross-Validation Folds:</span>
              <strong className="text-slate-800">{trainResult.cv_folds || 5} Folds</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Training Sample Count:</span>
              <strong className="text-slate-800">{trainResult.training_row_count.toLocaleString()} rows</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Holdout Evaluation Sample:</span>
              <strong className="text-slate-800">{trainResult.test_row_count.toLocaleString()} rows</strong>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Total Training Duration:</span>
              <strong className="text-slate-800 font-mono">{trainResult.training_time_ms ? `${trainResult.training_time_ms}ms` : 'N/A'}</strong>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-3">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>📦</span> Model Store & Artifact Metadata
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Model Identifier:</span>
              <strong className="text-slate-800 font-mono text-[11px] truncate max-w-[200px]" title={trainResult.model_id}>
                {trainResult.model_id}
              </strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Dataset Version:</span>
              <strong className="text-slate-800 font-mono">v{trainResult.dataset_version}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Winning Algorithm:</span>
              <strong className="text-slate-800">{trainResult.best_model.algorithm}</strong>
            </div>
            {targetCandidate && (
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Target Column Metadata:</span>
                <strong className="text-slate-800">
                  {targetCandidate.dtype} · {targetCandidate.business_role}
                </strong>
              </div>
            )}
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Selected Feature Count:</span>
              <strong className="text-slate-800">{trainResult.selected_features.length} columns</strong>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Serialization Engine:</span>
              <strong className="text-slate-800 font-mono">Joblib + Scikit-Learn Pipeline</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
