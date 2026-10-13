import type { Recommendation } from '../../types/decisionTypes'
import {
  getPriorityBadgeInfo,
  getStatusBadgeInfo,
  formatEvidenceValue,
} from '../../utils/decisionUtils'

interface DecisionRecommendationCardProps {
  recommendation: Recommendation
  onViewDetails: (rec: Recommendation) => void
  onQuickApprove?: (rec: Recommendation) => void
}

export default function DecisionRecommendationCard({
  recommendation: rec,
  onViewDetails,
  onQuickApprove,
}: DecisionRecommendationCardProps) {
  const pBadge = getPriorityBadgeInfo(rec.priority)
  const sBadge = getStatusBadgeInfo(rec.status)

  const isPendingReview = rec.status === 'needs_review' || rec.status === 'pending_approval'

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md hover:border-slate-300 transition-all flex flex-col justify-between space-y-4">
      {/* Top Header Row: Badges & Timestamp */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Priority Badge */}
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${pBadge.bg} ${pBadge.text} ${pBadge.border}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${pBadge.dot}`} />
              {pBadge.label} Priority
            </span>

            {/* Status Badge */}
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${sBadge.bg} ${sBadge.text} ${sBadge.border}`}
            >
              <span>{sBadge.icon}</span>
              <span>{sBadge.label}</span>
            </span>

            {/* Scenario Badge */}
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase bg-slate-100 text-slate-700 border border-slate-200">
              {rec.scenario}
            </span>
          </div>

          <span className="text-[11px] text-slate-600 font-mono">
            {new Date(rec.created_at).toLocaleDateString()} {new Date(rec.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

        {/* Title */}
        <h4 className="text-base font-bold text-slate-900 leading-snug">
          {rec.title}
        </h4>
      </div>

      {/* Recommended Action Callout Box */}
      <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200 text-xs space-y-1">
        <span className="text-[10px] text-emerald-800 font-bold uppercase tracking-wider block">
          Recommended Action
        </span>
        <p className="text-emerald-950 font-semibold leading-relaxed">
          {rec.recommended_action}
        </p>
      </div>

      {/* Description / Business Context */}
      <p className="text-xs text-slate-600 leading-relaxed">
        {rec.description}
      </p>

      {/* Supporting Evidence Pills */}
      {rec.supporting_evidence.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <span className="text-[11px] font-semibold text-slate-700">
            Supporting Evidence ({rec.supporting_evidence.length}):
          </span>
          <div className="flex flex-wrap gap-2">
            {rec.supporting_evidence.map((ev, idx) => (
              <div
                key={idx}
                className="px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] space-y-0.5"
              >
                <div className="text-[10px] text-slate-600 font-mono truncate max-w-[150px]">
                  {ev.field_name}
                </div>
                <div className="text-slate-900 font-bold">
                  {formatEvidenceValue(ev.value, ev.unit)}
                </div>
                {ev.source_label && (
                  <div className="text-[9px] text-slate-600 truncate max-w-[150px]">
                    {ev.source_label}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Incomplete / Missing Evidence Disclosures */}
      {rec.missing_evidence && rec.missing_evidence.length > 0 && (
        <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-900 space-y-1">
          <span className="font-semibold block flex items-center gap-1">
            <span>⚠️</span> Incomplete Evidence Disclosures:
          </span>
          {rec.missing_evidence.map((me, idx) => (
            <div key={idx} className="text-amber-800 text-[10px]">
              • {me}
            </div>
          ))}
        </div>
      )}

      {/* Rejection / Completed note if present */}
      {rec.status === 'rejected' && rec.status_comment && (
        <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-[11px] text-rose-800">
          <span className="font-semibold block">Rejection Justification:</span>
          <span className="text-slate-700 italic">{rec.status_comment}</span>
        </div>
      )}

      {rec.status === 'approved' && (
        <div className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-medium flex items-center gap-1.5">
          <span>✓</span>
          <span>Authorized by human reviewer. Ready for execution.</span>
        </div>
      )}

      {rec.status === 'completed' && (
        <div className="px-3 py-1.5 rounded-lg bg-sky-50 border border-sky-200 text-xs text-sky-800 font-medium flex items-center gap-1.5">
          <span>✓✓</span>
          <span>Operational action completed and recorded.</span>
        </div>
      )}

      {/* Card Footer Actions */}
      <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[11px] text-slate-600">
          {rec.requires_approval ? (
            <span className="inline-flex items-center gap-1 text-purple-700 font-medium">
              <span>🛡️</span> Requires Human Sign-Off
            </span>
          ) : (
            <span className="text-slate-600">Operational Guidance</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {onQuickApprove && isPendingReview && (
            <button
              type="button"
              onClick={() => onQuickApprove(rec)}
              className="py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer"
            >
              Approve
            </button>
          )}

          <button
            type="button"
            onClick={() => onViewDetails(rec)}
            className="py-1.5 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs shadow-sm transition-colors cursor-pointer flex items-center gap-1"
          >
            <span>{isPendingReview ? 'Review & Decide' : 'View Full Details'}</span>
            <span>→</span>
          </button>
        </div>
      </div>
    </div>
  )
}
