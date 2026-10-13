import { useState } from 'react'
import type { Recommendation, RecommendationStatus } from '../../types/decisionTypes'
import {
  getPriorityBadgeInfo,
  getStatusBadgeInfo,
  formatEvidenceValue,
  requiresStatusComment,
} from '../../utils/decisionUtils'

interface DecisionDetailModalProps {
  recommendation: Recommendation
  onClose: () => void
  onUpdateStatus: (recId: string, newStatus: RecommendationStatus, comment?: string) => Promise<void>
}

export default function DecisionDetailModal({
  recommendation: rec,
  onClose,
  onUpdateStatus,
}: DecisionDetailModalProps) {
  const [comment, setComment] = useState('')
  const [actionTarget, setActionTarget] = useState<RecommendationStatus | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pBadge = getPriorityBadgeInfo(rec.priority)
  const sBadge = getStatusBadgeInfo(rec.status)

  const isCommentMandatory = actionTarget ? requiresStatusComment(actionTarget) : false
  const canConfirm = !isCommentMandatory || comment.trim().length > 0

  const handleConfirmAction = async () => {
    if (!actionTarget) return

    // Strictly enforce reason for rejection or dismissal
    if (isCommentMandatory && !comment.trim()) {
      setError(`A specific business rationale or explanation is required when setting status to '${actionTarget}'.`)
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      await onUpdateStatus(rec.recommendation_id, actionTarget, comment.trim() || undefined)
      onClose()
    } catch (err: any) {
      setError(err.message || 'Failed to update recommendation status.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-3xl bg-white border border-slate-200 rounded-2xl shadow-2xl p-6 sm:p-7 space-y-6 text-slate-800 my-8">
        {/* Modal Header */}
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${pBadge.bg} ${pBadge.text} ${pBadge.border}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${pBadge.dot}`} />
                {pBadge.label} Priority
              </span>

              <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${sBadge.bg} ${sBadge.text} ${sBadge.border}`}>
                <span>{sBadge.icon}</span>
                <span>{sBadge.label}</span>
              </span>

              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-slate-100 text-slate-700 border border-slate-200">
                {rec.scenario}
              </span>

              <span className="text-[11px] text-slate-500 font-mono">
                ID: {rec.recommendation_id.slice(0, 8)}...
              </span>
            </div>

            <h3 className="text-xl font-bold text-slate-900">
              {rec.title}
            </h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 text-xl p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-rose-600 hover:text-rose-900 text-xs font-semibold ml-3"
            >
              ✕
            </button>
          </div>
        )}

        <div className="space-y-6 max-h-[65vh] overflow-y-auto pr-1">
          {/* SECTION A: RECOMMENDATION */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 font-bold text-xs flex items-center justify-center">
                A
              </span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Recommendation & Suggested Action
              </h4>
            </div>

            {/* Prominent Action Callout Box */}
            <div className="p-4 rounded-xl bg-emerald-50/80 border border-emerald-200 space-y-1.5">
              <span className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider block">
                Suggested Operational Action
              </span>
              <p className="text-sm font-bold text-emerald-950 leading-relaxed">
                {rec.recommended_action}
              </p>
            </div>

            {/* Context Narrative */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 leading-relaxed">
              <span className="text-[10px] font-bold uppercase text-slate-600 block mb-1">
                Context & Business Impact
              </span>
              <p>{rec.description}</p>
            </div>
          </div>

          {/* SECTION B: SUPPORTING EVIDENCE */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 font-bold text-xs flex items-center justify-center">
                B
              </span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Supporting Evidence & Observed Data ({rec.supporting_evidence.length})
              </h4>
            </div>

            {rec.supporting_evidence.length === 0 ? (
              <p className="text-xs text-slate-500 italic p-3 bg-slate-50 rounded-lg border border-slate-200">
                No individual metric evidence was recorded for this recommendation.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 text-slate-700 uppercase tracking-wider text-[11px] border-b border-slate-200 font-semibold">
                    <tr>
                      <th className="py-2.5 px-3.5">Metric / Field</th>
                      <th className="py-2.5 px-3.5">Observed Value</th>
                      <th className="py-2.5 px-3.5">Unit</th>
                      <th className="py-2.5 px-3.5">Source Type</th>
                      <th className="py-2.5 px-3.5">Source Label / Model</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {rec.supporting_evidence.map((ev, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-2.5 px-3.5 font-mono font-medium text-slate-900">
                          {ev.field_name}
                        </td>
                        <td className="py-2.5 px-3.5 font-bold text-emerald-700">
                          {formatEvidenceValue(ev.value, ev.unit)}
                        </td>
                        <td className="py-2.5 px-3.5 text-slate-600 font-mono">
                          {ev.unit || '—'}
                        </td>
                        <td className="py-2.5 px-3.5 text-slate-600 capitalize">
                          {ev.source_type}
                        </td>
                        <td className="py-2.5 px-3.5 text-slate-600">
                          {ev.source_label || ev.source_id || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* SECTION C: WHY THIS RECOMMENDATION WAS CREATED */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 font-bold text-xs flex items-center justify-center">
                C
              </span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Why This Recommendation Was Created
              </h4>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-900">
                  Triggered Business Rule
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-200 text-slate-800">
                  {rec.triggered_rule_ids && rec.triggered_rule_ids.length > 0
                    ? `rules: ${rec.triggered_rule_ids.map((id) => id.slice(0, 8)).join(', ')}`
                    : 'rule: custom'}
                </span>
              </div>
              <p className="text-slate-600 leading-relaxed">
                This recommendation was triggered by deterministic evaluation. The observed metric values in Section B met or crossed the operational boundaries established for the <strong>{rec.scenario.toUpperCase()}</strong> scenario.
              </p>
              {rec.evaluation_id && (
                <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-200/80 font-mono">
                  Evaluation Run ID: {rec.evaluation_id}
                </div>
              )}
            </div>
          </div>

          {/* SECTION D: LIMITATIONS AND MISSING INFORMATION */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 font-bold text-xs flex items-center justify-center">
                D
              </span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Limitations, Assumptions & Governance Disclosures
              </h4>
            </div>

            {/* Missing Evidence Items */}
            {rec.missing_evidence && rec.missing_evidence.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1.5">
                <span className="font-bold block flex items-center gap-1.5">
                  <span>⚠️</span> Missing or Incomplete Evidence Fields
                </span>
                <div className="space-y-1 pl-4">
                  {rec.missing_evidence.map((me, idx) => (
                    <div key={idx} className="text-amber-800 text-[11px]">
                      • {me}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Uncertainty Notes & Non-Causality Disclosures */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2 text-xs text-slate-600">
              <div className="font-semibold text-slate-800 flex items-center gap-1">
                <span>🛡️</span> Non-Causal Decision Safeguards:
              </div>
              <p className="text-[11px] leading-relaxed">
                Recommendations are synthesized deterministically based on configured business thresholds. They reflect correlation and operational risk boundaries, not guaranteed causal outcomes.
              </p>
              {rec.uncertainty_notes && rec.uncertainty_notes.length > 0 && (
                <div className="space-y-1 pt-1.5 border-t border-slate-200 text-[11px] text-slate-600">
                  {rec.uncertainty_notes.map((note, idx) => (
                    <div key={idx}>ℹ {note}</div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* SECTION E: HUMAN REVIEW AND DECISION ACTION */}
          <div className="space-y-3 pt-2 border-t border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 font-bold text-xs flex items-center justify-center">
                  E
                </span>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Human Operational Review
                </h4>
              </div>

              <span className="text-xs text-slate-600">
                Current Status:{' '}
                <strong className={`font-semibold ${sBadge.text}`}>
                  {sBadge.label}
                </strong>
              </span>
            </div>

            {/* If user clicked an action to confirm */}
            {actionTarget ? (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-300 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 text-sm flex items-center gap-2">
                    <span>Confirm Decision:</span>
                    <span className="capitalize px-2 py-0.5 rounded bg-slate-200 text-slate-900 font-mono">
                      {actionTarget}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setActionTarget(null)
                      setError(null)
                    }}
                    className="text-slate-600 hover:text-slate-900 text-xs font-medium cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">
                    Decision Rationale or Action Notes{' '}
                    {isCommentMandatory ? (
                      <span className="text-rose-600 font-bold">* Required for {actionTarget}</span>
                    ) : (
                      <span className="text-slate-600">(Optional)</span>
                    )}
                  </label>
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder={
                      isCommentMandatory
                        ? `Please provide the specific operational reason for ${actionTarget}...`
                        : `Enter optional notes regarding this ${actionTarget} decision...`
                    }
                    rows={3}
                    className="w-full bg-white border border-slate-300 rounded-lg p-2.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  />
                  {isCommentMandatory && !comment.trim() && (
                    <span className="text-[11px] text-rose-600 mt-1 block">
                      A clear justification must be recorded in the audit trail before submitting.
                    </span>
                  )}
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                  <button
                    type="button"
                    onClick={() => {
                      setActionTarget(null)
                      setError(null)
                    }}
                    className="px-3.5 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700 font-medium text-xs hover:bg-slate-100 transition-colors cursor-pointer"
                  >
                    Back
                  </button>

                  <button
                    type="button"
                    disabled={isSubmitting || !canConfirm}
                    onClick={handleConfirmAction}
                    className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    {isSubmitting ? (
                      <span>Recording Decision...</span>
                    ) : (
                      <span>Confirm Status Update</span>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                <p className="text-xs text-slate-600">
                  Select an operational review action below to update this recommendation's state. All status transitions are permanently recorded in the immutable audit log.
                </p>

                <div className="flex flex-wrap items-center gap-2.5">
                  {(rec.status === 'needs_review' || rec.status === 'pending_approval') && (
                    <>
                      <button
                        type="button"
                        onClick={() => setActionTarget('approved')}
                        className="py-2 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer flex items-center gap-1.5"
                      >
                        <span>✓</span>
                        <span>Approve Recommendation</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setActionTarget('rejected')}
                        className="py-2 px-4 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer flex items-center gap-1.5"
                      >
                        <span>✕</span>
                        <span>Reject (Requires Rationale)</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setActionTarget('dismissed')}
                        className="py-2 px-3.5 rounded-lg bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 font-semibold text-xs transition-colors cursor-pointer"
                      >
                        Dismiss
                      </button>
                    </>
                  )}

                  {rec.status === 'approved' && (
                    <>
                      <button
                        type="button"
                        onClick={() => setActionTarget('completed')}
                        className="py-2 px-4 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer flex items-center gap-1.5"
                      >
                        <span>✓✓</span>
                        <span>Mark Action as Completed</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setActionTarget('dismissed')}
                        className="py-2 px-3.5 rounded-lg bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 font-semibold text-xs transition-colors cursor-pointer"
                      >
                        Dismiss
                      </button>
                    </>
                  )}

                  {rec.status === 'completed' && (
                    <div className="flex items-center gap-2 text-xs text-emerald-700 font-semibold">
                      <span className="w-5 h-5 rounded-full bg-emerald-100 flex items-center justify-center">✓</span>
                      <span>This operational action was completed and verified.</span>
                    </div>
                  )}

                  {rec.status === 'rejected' && (
                    <div className="text-xs text-rose-700 space-y-1">
                      <div className="font-semibold flex items-center gap-1.5">
                        <span className="w-4 h-4 rounded-full bg-rose-100 flex items-center justify-center">✕</span>
                        <span>Recommendation was rejected.</span>
                      </div>
                      {rec.status_comment && (
                        <div className="text-slate-600 pl-5 italic">
                          Rationale: "{rec.status_comment}"
                        </div>
                      )}
                    </div>
                  )}

                  {rec.status === 'dismissed' && (
                    <div className="text-xs text-slate-600 space-y-1">
                      <span className="font-semibold block">Recommendation was archived / dismissed.</span>
                      {rec.status_comment && (
                        <div className="italic text-slate-600">
                          Rationale: "{rec.status_comment}"
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="pt-3 border-t border-slate-100 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
