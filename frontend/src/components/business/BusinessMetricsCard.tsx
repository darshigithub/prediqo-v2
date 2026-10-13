import {
  explainRegressionMetrics,
  explainClassificationMetrics,
  explainForecastingMetrics,
  explainBaselineComparison,
  type MetricInsight,
} from '../../utils/businessMetrics'

interface BusinessMetricsCardProps {
  type: 'regression' | 'classification' | 'forecasting'
  metrics: Record<string, any>
  targetName: string
  unit?: string | null
  frequency?: string
  classLabels?: string[] | null
  vsBaselinePct?: number | null
  className?: string
}

export default function BusinessMetricsCard({
  type,
  metrics,
  targetName,
  unit,
  frequency = 'period',
  classLabels,
  vsBaselinePct,
  className = '',
}: BusinessMetricsCardProps) {
  let insights: MetricInsight[] = []

  if (type === 'regression') {
    insights = explainRegressionMetrics(metrics, targetName, unit)
  } else if (type === 'classification') {
    insights = explainClassificationMetrics(metrics, targetName, classLabels)
  } else if (type === 'forecasting') {
    insights = explainForecastingMetrics(metrics, targetName, frequency, unit)
  }

  const baselineInfo =
    vsBaselinePct !== undefined && vsBaselinePct !== null
      ? explainBaselineComparison(vsBaselinePct, type)
      : null

  const tierColors: Record<MetricInsight['statusTier'], { badge: string; border: string }> = {
    excellent: {
      badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      border: 'border-emerald-500/30',
    },
    good: {
      badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      border: 'border-blue-500/30',
    },
    moderate: {
      badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      border: 'border-amber-500/30',
    },
    caution: {
      badge: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      border: 'border-rose-500/30',
    },
  }

  return (
    <div className={`p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
          <span>📊</span>
          <span>Business Performance & Evaluation</span>
        </h3>
        {baselineInfo && (
          <div
            className={`px-2.5 py-1 rounded text-xs font-semibold border ${
              baselineInfo.isPositive
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : 'bg-slate-800 text-slate-300 border-slate-700'
            }`}
          >
            {baselineInfo.headline}
          </div>
        )}
      </div>

      {baselineInfo && (
        <p className="text-xs text-slate-400 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/80">
          ℹ {baselineInfo.description}
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {insights.map((insight) => {
          const style = tierColors[insight.statusTier] || tierColors.good
          return (
            <div
              key={insight.metricName}
              className={`p-3.5 rounded-lg bg-slate-800/40 border border-slate-700/60 flex flex-col justify-between space-y-2`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-slate-300">{insight.displayName}</span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${style.badge}`}>
                  {insight.formattedValue}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-normal">
                {insight.businessMeaning}
              </p>
              <div className="text-[10px] text-slate-500 font-mono pt-1 border-t border-slate-800/80">
                {insight.technicalExplanation}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
