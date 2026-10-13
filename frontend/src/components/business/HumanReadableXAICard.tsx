import { useState } from 'react'
import type { LocalExplanationResponse, GlobalExplanationResponse } from '../../types'
import {
  generateLocalNarrative,
  generateGlobalNarrative,
} from '../../utils/xaiNarratives'

interface HumanReadableXAICardProps {
  localExplanation?: LocalExplanationResponse | null
  globalExplanation?: GlobalExplanationResponse | null
  targetName: string
  unit?: string | null
  className?: string
}

export default function HumanReadableXAICard({
  localExplanation,
  globalExplanation,
  targetName,
  unit,
  className = '',
}: HumanReadableXAICardProps) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false)

  const localNarrative = generateLocalNarrative(localExplanation, targetName, unit)
  const globalNarrative = generateGlobalNarrative(globalExplanation, targetName)

  if (!localNarrative && !globalNarrative) return null

  return (
    <div className={`p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
          <span>🔍</span>
          <span>{localNarrative ? 'Why the Model Made this Prediction' : 'Key Global Drivers'}</span>
        </h3>
        <button
          type="button"
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
        >
          {showTechnicalDetails ? 'Hide Technical Decomposition' : 'View Math & Baseline Details'}
        </button>
      </div>

      {/* Local Prediction Explanation */}
      {localNarrative && (
        <div className="space-y-4">
          <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/50 p-3 rounded-lg border border-slate-800/80">
            {localNarrative.summaryParagraph}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Positive Drivers */}
            <div className="p-3.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20 space-y-2">
              <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                <span>▲</span>
                <span>Top Factors Increasing the Prediction:</span>
              </div>
              {localNarrative.topPositiveDrivers.length === 0 ? (
                <div className="text-xs text-slate-500 italic">No positive drivers for this record.</div>
              ) : (
                <div className="space-y-2">
                  {localNarrative.topPositiveDrivers.slice(0, 4).map((d) => (
                    <div key={d.feature} className="space-y-1">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-200 font-medium truncate">{d.feature}</span>
                        <span className="font-mono text-emerald-400 font-bold">{d.impactText}</span>
                      </div>
                      {d.value !== undefined && d.value !== null && (
                        <div className="text-[10px] text-slate-400">
                          Input value: <span className="text-slate-300">{String(d.value)}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Negative Drivers */}
            <div className="p-3.5 rounded-lg bg-rose-500/5 border border-rose-500/20 space-y-2">
              <div className="text-xs font-semibold text-rose-400 flex items-center gap-1.5">
                <span>▼</span>
                <span>Top Factors Decreasing the Prediction:</span>
              </div>
              {localNarrative.topNegativeDrivers.length === 0 ? (
                <div className="text-xs text-slate-500 italic">No negative drivers for this record.</div>
              ) : (
                <div className="space-y-2">
                  {localNarrative.topNegativeDrivers.slice(0, 4).map((d) => (
                    <div key={d.feature} className="space-y-1">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-200 font-medium truncate">{d.feature}</span>
                        <span className="font-mono text-rose-400 font-bold">{d.impactText}</span>
                      </div>
                      {d.value !== undefined && d.value !== null && (
                        <div className="text-[10px] text-slate-400">
                          Input value: <span className="text-slate-300">{String(d.value)}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Collapsible Technical & Baseline Details */}
          {showTechnicalDetails && localExplanation && (
            <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800 space-y-3 text-xs">
              <div className="font-semibold text-slate-300">Mathematical Additive Decomposition:</div>
              <div className="text-slate-400">{localNarrative.baselineExplanation}</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 font-mono text-[11px]">
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Baseline Y₀</span>
                  <strong className="text-white">{localExplanation.baseline_reference_value.toFixed(3)}</strong>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Net Additive Sum</span>
                  <strong className="text-white">
                    {localExplanation.additive_sum >= 0 ? '+' : ''}
                    {localExplanation.additive_sum.toFixed(3)}
                  </strong>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Reconstruction Error</span>
                  <strong className="text-emerald-400">
                    {localExplanation.reconstruction_error < 1e-4
                      ? '< 0.0001'
                      : localExplanation.reconstruction_error.toFixed(4)}
                  </strong>
                </div>
              </div>
              <div className="text-[11px] text-slate-400 pt-1">
                Decomposition Space: <strong className="text-slate-200">{localExplanation.decomposition_space}</strong>
              </div>
            </div>
          )}

          {/* Scale Disclosure */}
          <div className="text-[11px] text-slate-400 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/80">
            ℹ {localNarrative.scaleDisclosure}
          </div>

          {/* Non-Causal Attribution Disclaimer */}
          <div className="text-[10px] text-slate-500 italic p-2 rounded bg-slate-950/30 border border-slate-900">
            ⚠ {localNarrative.attributionDisclaimer}
          </div>
        </div>
      )}

      {/* Global Drivers Narrative if rendered without local */}
      {!localNarrative && globalNarrative && (
        <div className="space-y-3">
          <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/50 p-3 rounded-lg border border-slate-800/80">
            {globalNarrative.summaryParagraph}
          </p>
          {globalNarrative.collinearityNote && (
            <div className="text-xs text-amber-300 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20">
              ⚠️ {globalNarrative.collinearityNote}
            </div>
          )}
          <div className="space-y-2">
            {globalNarrative.topDrivers.map((d) => (
              <div key={d.feature} className="space-y-1">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-white font-medium">{d.feature}</span>
                  <span className="font-mono text-brand-300">{d.shareText}</span>
                </div>
                <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-500 rounded-full"
                    style={{ width: `${Math.min(100, Math.max(3, d.sharePct))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
