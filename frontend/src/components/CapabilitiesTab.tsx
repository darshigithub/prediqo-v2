import { useEffect, useState } from 'react'
import {
  getDatasetCapabilities,
  overrideDatasetCapabilities,
} from '../services/api'
import type { CapabilityAssessmentResponse } from '../types'

interface CapabilitiesTabProps {
  datasetId: string
}

export default function CapabilitiesTab({ datasetId }: CapabilitiesTabProps) {
  const [data, setData] = useState<CapabilityAssessmentResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [saving, setSaving] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Mapping overrides state
  const [mappings, setMappings] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!datasetId) {
      setData(null)
      return
    }

    setLoading(true)
    setError(null)
    setSuccessMsg(null)

    getDatasetCapabilities(datasetId)
      .then((res) => {
        setData(res)
        setMappings(res.detected_mappings || {})
      })
      .catch((err) => {
        setError(err.message || 'Failed to assess dataset capabilities.')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [datasetId])

  const handleSaveOverrides = async () => {
    if (!datasetId) return
    setSaving(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const res = await overrideDatasetCapabilities(datasetId, mappings)
      setData(res)
      setMappings(res.detected_mappings || {})
      setSuccessMsg('Field mappings updated and capabilities re-evaluated.')
    } catch (err: any) {
      setError(err.message || 'Failed to update field mappings.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="p-16 text-center text-slate-400">
        <div className="inline-block animate-spin text-xl mb-2">⚙</div>
        <div>Auditing dataset schema, granularity, and capabilities...</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-12 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-xl">
        Select a dataset above to view schema intelligence and capability assessment.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
          ✓ {successMsg}
        </div>
      )}

      {/* Top Banner: Granularity Assessment */}
      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Data Granularity & Aggregation Policy
            </div>
            <h3 className="text-base font-bold text-white capitalize mt-0.5">
              {data.granularity.likely_granularity.replace('_', ' ')} Granularity
            </h3>
          </div>
          <span
            className={`px-3 py-1 rounded font-semibold text-xs ${
              data.granularity.has_repeated_orders
                ? 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
                : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
            }`}
          >
            {data.granularity.has_repeated_orders ? '⚠️ Repeated Orders (Order-Item Level)' : '✓ 1 Row / Transaction'}
          </span>
        </div>

        <p className="text-xs text-slate-300 bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
          {data.granularity.aggregation_policy_note}
        </p>

        {data.granularity.distinct_id_ratio != null && (
          <div className="text-[11px] text-slate-400">
            Distinct ID to Row Ratio: <strong className="text-white">{(Number(data.granularity.distinct_id_ratio) * 100).toFixed(1)}%</strong>
          </div>
        )}
      </div>

      {/* Capability Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Prediction Capability */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
              <span>⚡</span> Machine Learning Prediction
            </h3>
            <span
              className={`px-2.5 py-0.5 rounded font-semibold text-xs ${
                data.capabilities.prediction.available
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
              }`}
            >
              {data.capabilities.prediction.available ? 'Available' : 'Unavailable'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
              <span className="text-slate-400">Regression Targets:</span>
              <div className="text-base font-bold text-white mt-0.5">
                {data.capabilities.prediction.regression_target_count}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
              <span className="text-slate-400">Classification Targets:</span>
              <div className="text-base font-bold text-white mt-0.5">
                {data.capabilities.prediction.classification_target_count}
              </div>
            </div>
          </div>

          {data.capabilities.prediction.recommended_targets.length > 0 && (
            <div className="text-xs space-y-1">
              <span className="text-slate-400">Recommended Targets:</span>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {data.capabilities.prediction.recommended_targets.map((t: string) => (
                  <span key={t} className="px-2 py-0.5 rounded bg-brand-900/30 text-brand-300 border border-brand-500/30 font-mono text-[11px]">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.capabilities.prediction.warnings.length > 0 && (
            <div className="space-y-1 pt-1">
              {data.capabilities.prediction.warnings.map((w: string, idx: number) => (
                <div key={idx} className="text-[11px] text-amber-300 bg-amber-500/10 p-2 rounded border border-amber-500/20">
                  ⚠️ {w}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Forecasting Capability */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
              <span>📈</span> Time-Series Forecasting
            </h3>
            <span
              className={`px-2.5 py-0.5 rounded font-semibold text-xs ${
                data.capabilities.forecasting.available
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
              }`}
            >
              {data.capabilities.forecasting.available ? 'Available' : 'Unavailable'}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div>
              <span className="text-slate-400">Detected Date Columns:</span>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {data.capabilities.forecasting.recommended_date_columns.map((d: string) => (
                  <span key={d} className="px-2 py-0.5 rounded bg-blue-900/30 text-blue-300 border border-blue-500/30 font-mono text-[11px]">
                    {d}
                  </span>
                ))}
                {data.capabilities.forecasting.recommended_date_columns.length === 0 && (
                  <span className="text-slate-500">None detected</span>
                )}
              </div>
            </div>

            <div>
              <span className="text-slate-400">Aggregatable Measures:</span>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {data.capabilities.forecasting.recommended_metrics.map((m: string) => (
                  <span key={m} className="px-2 py-0.5 rounded bg-emerald-900/30 text-emerald-300 border border-emerald-500/30 font-mono text-[11px]">
                    {m}
                  </span>
                ))}
                {data.capabilities.forecasting.recommended_metrics.length === 0 && (
                  <span className="text-slate-500">None detected</span>
                )}
              </div>
            </div>
          </div>

          {data.capabilities.forecasting.is_stale && (
            <div className="text-[11px] text-amber-300 bg-amber-500/10 p-2.5 rounded border border-amber-500/20">
              ⚠️ Stale data: dataset cutoff is in the past.
            </div>
          )}

          {data.capabilities.forecasting.missing_requirements.length > 0 && (
            <div className="space-y-1 pt-1">
              {data.capabilities.forecasting.missing_requirements.map((m: string, idx: number) => (
                <div key={idx} className="text-[11px] text-rose-300 bg-rose-500/10 p-2 rounded border border-rose-500/20">
                  ✕ {m}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detected Schema Mappings & Manual Overrides */}
      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
              <span>🎯</span> Semantic Concept Mapping & Overrides
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Prediqo infers canonical business concepts from column names and types. You can manually adjust them below:
            </p>
          </div>
          <button
            type="button"
            disabled={saving}
            onClick={handleSaveOverrides}
            className="py-1.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-medium text-xs transition-all disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Apply Mappings'}
          </button>
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-xs text-left text-slate-300">
            <thead className="bg-slate-800/80 text-slate-400">
              <tr>
                <th className="py-2.5 px-3">Canonical Concept</th>
                <th className="py-2.5 px-3">Mapped Column</th>
                <th className="py-2.5 px-3">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {['date', 'revenue', 'quantity', 'customer', 'order'].map((concept) => {
                const currentVal = mappings[concept] || ''
                const conf = data.mapping_confidences[concept] || 0
                return (
                  <tr key={concept} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 text-white font-medium capitalize">
                      {concept}
                    </td>
                    <td className="py-2.5 px-3">
                      <input
                        type="text"
                        value={currentVal}
                        onChange={(e) =>
                          setMappings({
                            ...mappings,
                            [concept]: e.target.value,
                          })
                        }
                        placeholder={`Column name for ${concept}`}
                        className="bg-slate-800 border border-slate-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-brand-500 w-56 font-mono"
                      />
                    </td>
                    <td className="py-2.5 px-3">
                      {conf > 0 ? (
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          conf >= 0.9 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-300'
                        }`}>
                          {Math.round(conf * 100)}% match
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[10px]">Unmapped</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
