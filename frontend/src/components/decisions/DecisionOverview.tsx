import { useMemo } from 'react'
import type { DecisionOverviewStats, Recommendation, DecisionEvaluation } from '../../types/decisionTypes'
import {
  getPriorityBadgeInfo,
  getStatusBadgeInfo,
  getRecommendationCounts,
} from '../../utils/decisionUtils'

interface DecisionOverviewProps {
  stats: DecisionOverviewStats | null
  recommendations?: Recommendation[]
  loading: boolean
  onOpenEvaluateModal: () => void
  onViewRecommendation: (rec: Recommendation) => void
  onGoToRecommendationsTab: () => void
  onGoToHistoryTab?: () => void
  onGoToSettingsTab?: () => void
  onGoToRulesTab?: () => void
  onRefresh: () => void
}

export default function DecisionOverview({
  stats,
  recommendations = [],
  loading,
  onOpenEvaluateModal,
  onViewRecommendation,
  onGoToRecommendationsTab,
  onGoToSettingsTab,
  onGoToRulesTab,
  onRefresh,
}: DecisionOverviewProps) {
  const goToSettings = onGoToSettingsTab || onGoToRulesTab || onGoToRecommendationsTab

  // Calculate authoritative counts
  const counts = useMemo(() => {
    return getRecommendationCounts(recommendations)
  }, [recommendations])

  // Filter recommendations needing attention (needs_review or pending_approval)
  const needsAttentionRecs = useMemo(() => {
    const list = recommendations.filter(
      (r) => r.status === 'needs_review' || r.status === 'pending_approval'
    )
    // Priority order: critical -> high -> medium -> low -> informational
    const priorityWeight: Record<string, number> = {
      critical: 4,
      high: 3,
      medium: 2,
      low: 1,
      informational: 0,
    }
    return list.sort((a, b) => (priorityWeight[b.priority] || 0) - (priorityWeight[a.priority] || 0))
  }, [recommendations])

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Loading Decision Center Overview...</span>
        </div>
      </div>
    )
  }

  // 4 Primary Business-Friendly KPI Cards
  const kpis = [
    {
      title: 'Needs Review',
      value: stats ? stats.needs_review_count + stats.pending_approval_count : counts.awaitingAction,
      sublabel: `${stats?.pending_approval_count ?? counts.pendingApproval} pending approval`,
      icon: '⏳',
      color: 'text-amber-700',
      bg: 'bg-amber-50/70 border-amber-200',
      badge: 'Action Required',
      badgeBg: 'bg-amber-100 text-amber-800',
      description: 'Recommendations awaiting human evaluation or sign-off',
    },
    {
      title: 'Approved',
      value: counts.approved,
      sublabel: 'Authorized for execution',
      icon: '✓',
      color: 'text-emerald-700',
      bg: 'bg-emerald-50/70 border-emerald-200',
      badge: 'Authorized',
      badgeBg: 'bg-emerald-100 text-emerald-800',
      description: 'Operational decisions approved by business reviewers',
    },
    {
      title: 'Completed',
      value: counts.completed,
      sublabel: 'Verified & performed',
      icon: '✓✓',
      color: 'text-sky-700',
      bg: 'bg-sky-50/70 border-sky-200',
      badge: 'Verified',
      badgeBg: 'bg-sky-100 text-sky-800',
      description: 'Business recommendations executed and recorded',
    },
    {
      title: 'Active Rules',
      value: stats?.total_active_rules ?? 0,
      sublabel: 'Deterministic policies',
      icon: '🛡️',
      color: 'text-indigo-700',
      bg: 'bg-indigo-50/70 border-indigo-200',
      badge: 'Engine',
      badgeBg: 'bg-indigo-100 text-indigo-800',
      description: 'Enabled threshold rules actively monitoring data & models',
    },
  ]

  const recentEvals = stats?.recent_evaluations || []

  return (
    <div className="space-y-6">
      {/* Top Banner / Hero Overview */}
      <div className="p-5 sm:p-6 rounded-2xl bg-white border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Operational Decision Intelligence
            </h2>
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200">
              Deterministic Rules Engine
            </span>
          </div>
          <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
            Synthesizes ML predictions, time-series forecasts, and data quality profiles against deterministic business policies.
            All recommendations are transparent, traceable to supporting evidence, and require human operational confirmation.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={onRefresh}
            className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 rounded-lg border border-slate-300 shadow-sm transition-colors cursor-pointer"
          >
            ↻ Refresh
          </button>
          <button
            type="button"
            onClick={onOpenEvaluateModal}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <span>▶</span> Run Evaluation
          </button>
        </div>
      </div>

      {/* 4 Business-Friendly Primary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, idx) => (
          <div
            key={idx}
            className={`p-4 rounded-xl border ${kpi.bg} flex flex-col justify-between shadow-sm space-y-3`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                {kpi.title}
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${kpi.badgeBg}`}>
                {kpi.badge}
              </span>
            </div>

            <div className="flex items-baseline justify-between">
              <div className={`text-3xl font-extrabold font-mono ${kpi.color}`}>
                {kpi.value}
              </div>
              <span className="text-base opacity-75">{kpi.icon}</span>
            </div>

            <div className="pt-2 border-t border-slate-200/60 text-[11px] text-slate-600 leading-tight">
              {kpi.description}
            </div>
          </div>
        ))}
      </div>

      {/* Secondary Metrics Strip */}
      {stats && (
        <div className="px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex items-center gap-1.5">
              <strong className="text-slate-900 font-mono font-bold">{stats.total_evaluations}</strong>
              <span>Historical Evaluations</span>
            </span>
            <span>•</span>
            <span className="flex items-center gap-1.5">
              <strong className="text-rose-700 font-mono font-bold">{stats.high_priority_count}</strong>
              <span>High/Critical Priority Alerts</span>
            </span>
            {stats.eval_failures_count > 0 && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1.5 text-amber-700">
                  <strong className="font-mono font-bold">{stats.eval_failures_count}</strong>
                  <span>Missing Evidence Disclosures</span>
                </span>
              </>
            )}
          </div>

          <button
            onClick={onGoToRecommendationsTab}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 cursor-pointer"
          >
            View All Recommendations ({recommendations.length}) →
          </button>
        </div>
      )}

      {/* Main Two-Column Grid: Immediate Attention & Recent Evaluations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Recommendations Needing Immediate Attention */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
              <span>Needs Immediate Attention ({needsAttentionRecs.length})</span>
            </h3>

            <button
              onClick={onGoToRecommendationsTab}
              className="text-xs text-brand-600 hover:text-brand-700 font-semibold cursor-pointer"
            >
              View all recommendations →
            </button>
          </div>

          {needsAttentionRecs.length === 0 ? (
            <div className="p-8 rounded-xl bg-white border border-slate-200 shadow-sm text-center space-y-3">
              <div className="w-12 h-12 mx-auto rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center text-2xl font-bold">
                ✓
              </div>
              <h4 className="text-sm font-bold text-slate-900">
                All Recommendations Reviewed
              </h4>
              <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                No active recommendations require immediate operational review. Run a new evaluation to check updated data or forecasts against business rules.
              </p>
              <div className="pt-2 flex justify-center gap-2">
                <button
                  type="button"
                  onClick={onOpenEvaluateModal}
                  className="px-3.5 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors cursor-pointer"
                >
                  Run New Evaluation
                </button>
                <button
                  type="button"
                  onClick={onGoToRecommendationsTab}
                  className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 rounded-lg border border-slate-300 transition-colors cursor-pointer"
                >
                  Browse History
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {needsAttentionRecs.slice(0, 4).map((rec) => {
                const pInfo = getPriorityBadgeInfo(rec.priority)
                const sInfo = getStatusBadgeInfo(rec.status)

                return (
                  <div
                    key={rec.recommendation_id}
                    className="p-4 rounded-xl bg-white border border-slate-200 hover:border-slate-300 shadow-sm transition-all flex flex-col justify-between space-y-2.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${pInfo.bg} ${pInfo.text} ${pInfo.border}`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${pInfo.dot}`} />
                          {pInfo.label} Priority
                        </span>

                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${sInfo.bg} ${sInfo.text} ${sInfo.border}`}
                        >
                          <span>{sInfo.label}</span>
                        </span>

                        <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-100 text-slate-600 border border-slate-200">
                          {rec.scenario}
                        </span>
                      </div>

                      <span className="text-[10px] text-slate-600 font-mono">
                        {new Date(rec.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div>
                      <h4 className="text-sm font-bold text-slate-900 mb-1">
                        {rec.title}
                      </h4>
                      <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                        {rec.recommended_action}
                      </p>
                    </div>

                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                      <span className="text-[11px] text-slate-600">
                        {rec.supporting_evidence.length} evidence metrics evaluated
                      </span>

                      <button
                        type="button"
                        onClick={() => onViewRecommendation(rec)}
                        className="py-1 px-3 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer flex items-center gap-1"
                      >
                        <span>Review</span>
                        <span>→</span>
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Right Column: Recent Evaluations & Active Governance */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
              <span>Recent Evaluations ({recentEvals.length})</span>
            </h3>

            <button
              onClick={goToSettings}
              className="text-xs text-slate-600 hover:text-slate-900 font-semibold cursor-pointer"
            >
              Manage Rules ({stats?.total_active_rules ?? 0} active) →
            </button>
          </div>

          {recentEvals.length === 0 ? (
            <div className="p-8 rounded-xl bg-white border border-slate-200 shadow-sm text-center space-y-3">
              <span className="text-3xl block">📋</span>
              <h4 className="text-sm font-semibold text-slate-800">
                No Evaluations Recorded Yet
              </h4>
              <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                Run an evaluation against your operational facts, forecasts, or prediction models to generate explainable recommendations.
              </p>
              <button
                type="button"
                onClick={onOpenEvaluateModal}
                className="mt-2 px-3.5 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors cursor-pointer"
              >
                Run First Evaluation
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {recentEvals.slice(0, 5).map((ev: DecisionEvaluation) => (
                <div
                  key={ev.evaluation_id}
                  className="p-4 rounded-xl bg-white border border-slate-200 hover:border-slate-300 shadow-sm transition-all flex items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900 uppercase font-mono">
                        {ev.scenario}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono border border-slate-200">
                        {ev.evaluation_id.slice(0, 8)}...
                      </span>
                    </div>

                    <div className="text-xs text-slate-600 flex items-center gap-2">
                      <span>
                        {new Date(ev.created_at).toLocaleDateString()} {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <span>•</span>
                      <span className="text-emerald-700 font-semibold">
                        {ev.triggered_rules_count} triggered
                      </span>
                      <span>•</span>
                      <span className="text-slate-600">
                        {ev.total_rules_evaluated} total rules
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {ev.not_evaluable_rules_count > 0 && (
                      <span
                        className="text-[10px] px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200"
                        title="Rules with missing or incompatible evidence"
                      >
                        {ev.not_evaluable_rules_count} missing inputs
                      </span>
                    )}

                    <span className="text-xs px-2.5 py-1 rounded-md font-semibold bg-brand-50 text-brand-700 border border-brand-200 font-mono">
                      {ev.recommendations.length} recs
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
