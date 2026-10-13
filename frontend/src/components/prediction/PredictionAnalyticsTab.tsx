import { useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
} from 'recharts'
import type {
  TrainResponse,
  LocalExplanationResponse,
  GlobalExplanationResponse,
  FeasibilityResponse,
  TargetCandidate,
} from '../../types'
import DataQualityCard from '../business/DataQualityCard'
import BusinessMetricsCard from '../business/BusinessMetricsCard'

interface PredictionAnalyticsTabProps {
  trainResult: TrainResponse | null
  feasibility: FeasibilityResponse | null
  targetCandidate: TargetCandidate | null
  localExplanation: LocalExplanationResponse | null
  globalExplanation: GlobalExplanationResponse | null
  loadingGlobalExp: boolean
  onLoadGlobalExplanation: () => void
  className?: string
}

export default function PredictionAnalyticsTab({
  trainResult,
  feasibility,
  targetCandidate,
  localExplanation,
  globalExplanation,
  loadingGlobalExp,
  onLoadGlobalExplanation,
  className = '',
}: PredictionAnalyticsTabProps) {
  const [showGlobalExp, setShowGlobalExp] = useState(false)

  if (!trainResult) {
    return (
      <div className={`bg-white rounded-xl border border-slate-200/80 p-12 text-center shadow-sm space-y-3 ${className}`}>
        <div className="w-12 h-12 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center text-2xl">
          📊
        </div>
        <h3 className="text-sm font-bold text-slate-800">No Model Evaluation Available</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Train a predictive machine learning model from the Overview tab to view holdout fit plots, confusion matrices, and feature attribution diagnostics.
        </p>
      </div>
    )
  }

  const isRegression = trainResult.problem_type === 'regression'
  const unit = targetCandidate?.unit || null

  // Prepare regression actual vs predicted data for Recharts
  const actVsPredData =
    trainResult.actual_vs_predicted?.map((pt, idx) => ({
      sample: idx + 1,
      actual: pt.actual,
      predicted: pt.predicted,
      residual: Number((pt.actual - pt.predicted).toFixed(2)),
    })) || []

  // Top feature importances
  const featureImportanceData = (trainResult.feature_importance || [])
    .slice(0, 10)
    .map((fi) => ({
      feature: fi.feature,
      importance: Number((fi.importance * 100).toFixed(1)),
    }))

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. Model Performance Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>📈</span> Model Performance & Fit Evaluation
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Authoritative holdout evaluation metrics comparing {trainResult.best_model.algorithm} against baseline models.
            </p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-100 text-slate-700">
            {trainResult.problem_type === 'regression' ? 'Regression Fit' : 'Classification Matrix'}
          </span>
        </div>

        {/* Business Metrics Grid */}
        <BusinessMetricsCard
          type={trainResult.problem_type}
          metrics={trainResult.best_model.metrics}
          targetName={trainResult.target_column}
          unit={unit}
          classLabels={trainResult.best_model.class_labels}
          vsBaselinePct={trainResult.best_model.vs_baseline_pct}
        />

        {/* Regression Fit Plot */}
        {isRegression && actVsPredData.length > 0 && (
          <div className="space-y-3 pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-slate-800">
                  Holdout Fit: Actual vs Predicted ({actVsPredData.length} Evaluation Points)
                </h4>
                <p className="text-[11px] text-slate-500">
                  Ideal predictions track the actual curve closely. Discrepancies indicate residual error.
                </p>
              </div>
            </div>

            <div className="h-64 w-full rounded-lg border border-slate-200 p-2 bg-slate-50/50">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={actVsPredData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="sample" stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#64748b" fontSize={10} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      borderColor: '#cbd5e1',
                      borderRadius: 8,
                      fontSize: 11,
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    dot={{ r: 2.5 }}
                    name="Actual Value"
                  />
                  <Line
                    type="monotone"
                    dataKey="predicted"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    strokeDasharray="3 3"
                    dot={{ r: 2.5 }}
                    name="Model Predicted"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-900 leading-relaxed">
              <strong>What to notice:</strong> Points where the gold dashed line deviates significantly from the cyan line represent outlier prediction errors. Residual MAE is {trainResult.best_model.metrics.mae ?? 'N/A'} {unit || ''}.
            </div>
          </div>
        )}

        {/* Classification Confusion Matrix */}
        {!isRegression && trainResult.best_model.confusion_matrix && trainResult.best_model.class_labels && (
          <div className="space-y-4 pt-3 border-t border-slate-100">
            <div>
              <h4 className="text-xs font-bold text-slate-800">
                Holdout Confusion Matrix ({trainResult.best_model.class_labels.length} Classes)
              </h4>
              <p className="text-[11px] text-slate-500">
                Diagonal cells represent correctly predicted cases. Off-diagonal cells represent misclassifications.
              </p>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-2">
              <table className="w-full text-xs text-center border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] text-slate-500">
                    <th className="p-2 text-left font-semibold text-slate-600">Actual \ Predicted</th>
                    {trainResult.best_model.class_labels.map((lbl) => (
                      <th key={lbl} className="p-2 font-mono text-brand-700">
                        {lbl}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {trainResult.best_model.confusion_matrix.map((row, rIdx) => {
                    const actualLabel = trainResult.best_model.class_labels?.[rIdx] || `Class ${rIdx}`
                    return (
                      <tr key={rIdx} className="border-b border-slate-100">
                        <td className="p-2 text-left font-mono font-medium text-slate-800">
                          {actualLabel}
                        </td>
                        {row.map((val, cIdx) => (
                          <td
                            key={cIdx}
                            className={`p-2.5 font-mono font-bold ${
                              rIdx === cIdx
                                ? 'text-emerald-700 bg-emerald-50'
                                : val > 0
                                ? 'text-rose-600 bg-rose-50/60'
                                : 'text-slate-400'
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

            {/* Per-Class Metrics */}
            {trainResult.best_model.per_class_metrics && (
              <div className="space-y-2">
                <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider block">
                  Per-Class Precision, Recall & F1 Breakdown:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                  {Object.entries(trainResult.best_model.per_class_metrics).map(([cls, m]) => (
                    <div
                      key={cls}
                      className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1"
                    >
                      <div className="font-bold text-slate-900 truncate">{cls}</div>
                      <div className="grid grid-cols-3 gap-1 text-[11px] text-slate-600 font-mono">
                        <div>
                          Prec: <strong className="text-slate-900">{m.precision ?? '-'}</strong>
                        </div>
                        <div>
                          Rec: <strong className="text-slate-900">{m.recall ?? '-'}</strong>
                        </div>
                        <div>
                          F1: <strong className="text-brand-700">{m.f1 ?? '-'}</strong>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2. Feature Insights & Explainability Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <span>🔍</span> Feature Insights & Attribution
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Understand which columns drive predictions across the dataset and inspect collinear relationships.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              if (!showGlobalExp && !globalExplanation) {
                onLoadGlobalExplanation()
              }
              setShowGlobalExp(!showGlobalExp)
            }}
            className="px-3 py-1.5 rounded-lg border border-brand-200 bg-brand-50 hover:bg-brand-100 text-brand-700 text-xs font-semibold transition-colors cursor-pointer"
          >
            {loadingGlobalExp
              ? 'Computing Global XAI...'
              : showGlobalExp
              ? 'Show Standard Importance'
              : 'View Global XAI Attribution'}
          </button>
        </div>

        {/* Global Explainability or Standard Feature Importance */}
        {showGlobalExp && globalExplanation ? (
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-900 text-xs">
              <strong>Grouped Feature Attribution:</strong> Evaluated mean absolute attribution across{' '}
              {globalExplanation.sample_rows_evaluated} dataset records. One-hot encoded features are grouped back to original business columns.
            </div>

            {globalExplanation.correlation_warnings.length > 0 && (
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs space-y-1">
                <div className="font-semibold flex items-center gap-1.5">
                  <span>⚠️</span> Collinearity Disclosures:
                </div>
                {globalExplanation.correlation_warnings.map((w, idx) => (
                  <div key={idx} className="text-[11px]">• {w}</div>
                ))}
              </div>
            )}

            <div className="space-y-2.5">
              {globalExplanation.feature_importances.map((gi) => (
                <div key={gi.feature} className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-slate-900">{gi.feature}</span>
                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      {gi.correlated_with && gi.correlated_with.length > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px]">
                          collinear with {gi.correlated_with.join(', ')}
                        </span>
                      )}
                      <span className="text-brand-700 font-bold">{gi.relative_share_pct}% share</span>
                      <span className="text-slate-500">|avg contribution|: {gi.mean_absolute_contribution.toFixed(3)}</span>
                    </div>
                  </div>
                  <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-600 rounded-full"
                      style={{ width: `${Math.min(100, Math.max(2, gi.relative_share_pct))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={featureImportanceData} layout="vertical" margin={{ left: 40, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" stroke="#64748b" fontSize={10} unit="%" />
                  <YAxis type="category" dataKey="feature" stroke="#64748b" fontSize={11} width={120} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      borderColor: '#cbd5e1',
                      borderRadius: 8,
                      fontSize: 11,
                    }}
                    formatter={(val) => [`${val}%`, 'Relative Importance']}
                  />
                  <Bar dataKey="importance" fill="#0284c7" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Validated Local Feature Contributions (if user generated a scenario prediction) */}
        {localExplanation && localExplanation.contributions && localExplanation.contributions.length > 0 && (
          <div className="p-3.5 rounded-lg bg-emerald-50/60 border border-emerald-200 space-y-2">
            <div className="text-xs font-bold text-emerald-800 flex items-center gap-1.5">
              <span>▲</span>
              <span>Scenario Prediction Feature Contributions (Local Attribution):</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {localExplanation.contributions.slice(0, 6).map((c) => (
                <span
                  key={c.feature}
                  className="px-2 py-1 rounded bg-white border border-emerald-200 text-xs font-mono text-slate-800 shadow-2xs"
                >
                  <strong className="text-slate-900">{c.feature}</strong>:{' '}
                  <span className={c.contribution >= 0 ? 'text-emerald-700 font-bold' : 'text-rose-600 font-bold'}>
                    {c.contribution >= 0 ? `+${c.contribution.toFixed(2)}` : c.contribution.toFixed(2)}
                  </span>{' '}
                  {unit || ''}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Non-Causality & Methodology Warning Callout */}
        <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
          <div className="font-semibold text-slate-800 flex items-center gap-1.5">
            <span>ℹ️</span> Statistical Association vs Direct Causation:
          </div>
          <p className="leading-relaxed text-[11px]">
            Feature importance scores and XAI attributions quantify statistical reliance within the training dataset. They do not prove that altering an input feature will cause a direct business outcome. Operational decisions should verify underlying operational mechanisms.
          </p>
        </div>
      </div>

      {/* 3. Data Quality & Training Coverage Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm space-y-4">
        <div className="border-b border-slate-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <span>🛡️</span> Data Quality & Health Assessment
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Schema completeness, missing values, and dataset characteristics.
          </p>
        </div>

        <DataQualityCard
          dataQuality={feasibility?.data_quality}
          columnsInfo={feasibility?.columns_info}
          rowCount={feasibility?.row_count}
        />

        {feasibility?.warnings && feasibility.warnings.length > 0 && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs space-y-1">
            <div className="font-semibold flex items-center gap-1.5">
              <span>⚠️</span> Dataset Warnings:
            </div>
            <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
              {feasibility.warnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
