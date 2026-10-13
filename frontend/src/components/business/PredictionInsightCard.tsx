import type { PredictResponse } from '../../types'
import { formatBusinessValue } from '../../utils/businessMetrics'

interface PredictionInsightCardProps {
  result: PredictResponse
  targetName: string
  problemType: 'regression' | 'classification'
  unit?: string | null
  baselineValue?: number | null
  className?: string
}

export default function PredictionInsightCard({
  result,
  targetName,
  problemType,
  unit,
  baselineValue,
  className = '',
}: PredictionInsightCardProps) {
  const isRegression = problemType === 'regression'

  // Format the main prediction
  const formattedPred = isRegression
    ? formatBusinessValue(result.prediction, result.unit || unit)
    : String(result.prediction)

  // Compare to baseline if regression
  let baselineDiffText = ''
  if (isRegression && baselineValue !== null && baselineValue !== undefined) {
    const numPred = Number(result.prediction)
    if (!isNaN(numPred)) {
      const diff = numPred - baselineValue
      const diffPct = baselineValue !== 0 ? ((diff / Math.abs(baselineValue)) * 100).toFixed(1) : null
      const sign = diff >= 0 ? '+' : ''
      baselineDiffText = `${sign}${formatBusinessValue(diff, result.unit || unit)} (${sign}${diffPct}%) vs typical historical baseline (${formatBusinessValue(baselineValue, result.unit || unit)})`
    }
  }

  return (
    <div className={`p-5 rounded-xl bg-slate-900 border border-emerald-500/30 space-y-4 shadow-lg shadow-emerald-500/5 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
            Live Prediction Result
          </span>
        </div>
        <span className="px-2.5 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
          Target: <strong className="text-white">{targetName}</strong>
        </span>
      </div>

      <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <span className="text-[11px] text-slate-400 block uppercase font-medium">Model Output</span>
          <div className="text-3xl font-extrabold text-white mt-1">
            {formattedPred}
          </div>
          {baselineDiffText && (
            <div className="text-xs text-emerald-300/90 font-medium mt-1">
              {baselineDiffText}
            </div>
          )}
        </div>
        <div className="text-right">
          <span className="px-2 py-1 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            {isRegression ? 'Point Estimate' : 'Predicted Class'}
          </span>
          <div className="text-[10px] text-slate-400 mt-1">
            Statistical projection (non-guaranteed)
          </div>
        </div>
      </div>

      {/* Probabilities Breakdown for Classification */}
      {!isRegression && result.probabilities && (
        <div className="space-y-2 pt-2 border-t border-slate-800/80">
          <div className="text-xs font-medium text-slate-300">
            Confidence & Class Distribution:
          </div>
          <div className="space-y-1.5">
            {Object.entries(result.probabilities).map(([cls, prob]) => {
              const pct = Math.round(prob * 100)
              const isChosen = String(result.prediction) === cls
              return (
                <div key={cls} className="space-y-1">
                  <div className="flex justify-between items-center text-xs">
                    <span className={isChosen ? 'font-bold text-white' : 'text-slate-400'}>
                      {cls} {isChosen && '★'}
                    </span>
                    <span className="font-mono text-slate-300">{pct}% ({prob.toFixed(3)})</span>
                  </div>
                  <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        isChosen ? 'bg-emerald-500' : 'bg-slate-600'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          {result.probability_note && (
            <p className="text-[11px] text-slate-400 italic pt-1">
              ℹ {result.probability_note}
            </p>
          )}
        </div>
      )}

      {/* Summary Narrative */}
      {result.explanation && (
        <p className="text-xs text-slate-300 bg-slate-950/40 p-3 rounded-lg border border-slate-800/80 leading-relaxed">
          {result.explanation}
        </p>
      )}
    </div>
  )
}
