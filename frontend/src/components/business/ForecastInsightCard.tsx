import type { ForecastTrainResponse, ForecastExplanationResponse } from '../../types'
import { formatBusinessValue } from '../../utils/businessMetrics'
import { generateForecastNarrative } from '../../utils/xaiNarratives'

interface ForecastInsightCardProps {
  trainResult: ForecastTrainResponse
  explanation?: ForecastExplanationResponse | null
  unit?: string | null
  className?: string
}

export default function ForecastInsightCard({
  trainResult,
  explanation,
  unit,
  className = '',
}: ForecastInsightCardProps) {
  const narrative = generateForecastNarrative(
    explanation,
    trainResult.metric_column,
    trainResult.frequency,
    unit
  )

  // Calculate projected aggregate
  const totalForecast = trainResult.forecast_data.reduce((acc, curr) => acc + (curr.forecast || 0), 0)
  const avgForecast = trainResult.forecast_data.length > 0 ? totalForecast / trainResult.forecast_data.length : 0

  return (
    <div className={`p-5 rounded-xl bg-slate-900 border border-brand-500/30 space-y-4 shadow-lg shadow-brand-500/5 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-brand-400 animate-pulse" />
          <span className="text-xs font-semibold text-brand-300 uppercase tracking-wider">
            Executive Forecast Summary
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {trainResult.horizon} {trainResult.frequency} periods
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {trainResult.aggregation} aggregation
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3.5 rounded-lg bg-brand-500/10 border border-brand-500/20">
          <span className="text-[10px] text-slate-400 block uppercase font-medium">Projected Average</span>
          <div className="text-2xl font-extrabold text-white mt-0.5">
            {formatBusinessValue(avgForecast, unit)}
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">per {trainResult.frequency} period</span>
        </div>

        <div className="p-3.5 rounded-lg bg-slate-800/50 border border-slate-700/60">
          <span className="text-[10px] text-slate-400 block uppercase font-medium">Projected Cumulative</span>
          <div className="text-2xl font-extrabold text-white mt-0.5">
            {formatBusinessValue(totalForecast, unit)}
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">over next {trainResult.horizon} periods</span>
        </div>

        <div className="p-3.5 rounded-lg bg-slate-800/50 border border-slate-700/60">
          <span className="text-[10px] text-slate-400 block uppercase font-medium">Backtest Reliability (MAE)</span>
          <div className="text-2xl font-extrabold text-emerald-300 mt-0.5">
            ±{formatBusinessValue(trainResult.best_model.metrics.mae, unit)}
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">
            {trainResult.best_model.vs_naive_pct ? `+${trainResult.best_model.vs_naive_pct}% vs baseline` : 'Historical error'}
          </span>
        </div>
      </div>

      {narrative && (
        <div className="p-3.5 rounded-lg bg-slate-950/50 border border-slate-800/80 space-y-2 text-xs">
          <div className="font-semibold text-slate-200">{narrative.headline}:</div>
          <p className="text-slate-300 leading-relaxed">{narrative.executiveSummary}</p>
          {narrative.intervalReliability && (
            <div className="text-[11px] text-emerald-400/90 font-medium pt-1 border-t border-slate-800/80">
              ✓ {narrative.intervalReliability}
            </div>
          )}
        </div>
      )}

      {/* Projection Preview Table */}
      <div className="pt-2">
        <div className="flex justify-between items-center text-xs font-semibold text-slate-300 mb-2">
          <span>Projection Schedule (Next {Math.min(5, trainResult.forecast_data.length)} Periods)</span>
          <span className="text-[10px] text-slate-400">Values with 80% & 95% Confidence Intervals</span>
        </div>
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-xs text-left text-slate-300">
            <thead className="bg-slate-800/80 text-slate-400">
              <tr>
                <th className="py-2 px-3">Date</th>
                <th className="py-2 px-3">Point Forecast</th>
                <th className="py-2 px-3">80% Range</th>
                <th className="py-2 px-3">95% Range</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono text-[11px]">
              {trainResult.forecast_data.slice(0, 5).map((pt) => (
                <tr key={pt.date} className="hover:bg-slate-800/30">
                  <td className="py-1.5 px-3 text-white font-sans">{pt.date}</td>
                  <td className="py-1.5 px-3 font-bold text-brand-300">
                    {formatBusinessValue(pt.forecast, unit)}
                  </td>
                  <td className="py-1.5 px-3 text-slate-400">
                    {pt.lower_80 !== null && pt.upper_80 !== null
                      ? `[${formatBusinessValue(pt.lower_80, unit)} – ${formatBusinessValue(pt.upper_80, unit)}]`
                      : '-'}
                  </td>
                  <td className="py-1.5 px-3 text-slate-400">
                    {pt.lower_95 !== null && pt.upper_95 !== null
                      ? `[${formatBusinessValue(pt.lower_95, unit)} – ${formatBusinessValue(pt.upper_95, unit)}]`
                      : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
