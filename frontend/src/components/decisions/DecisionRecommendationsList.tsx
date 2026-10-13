import { useState, useMemo } from 'react'
import type { Recommendation } from '../../types/decisionTypes'
import { getRecommendationCounts } from '../../utils/decisionUtils'
import DecisionRecommendationCard from './DecisionRecommendationCard'

interface DecisionRecommendationsListProps {
  recommendations: Recommendation[]
  loading: boolean
  onViewDetails: (rec: Recommendation) => void
  onQuickApprove?: (rec: Recommendation) => void
  onRefresh: () => void
  onOpenEvaluateModal: () => void
}

export default function DecisionRecommendationsList({
  recommendations,
  loading,
  onViewDetails,
  onQuickApprove,
  onRefresh,
  onOpenEvaluateModal,
}: DecisionRecommendationsListProps) {
  const [search, setSearch] = useState('')
  const [selectedScenario, setSelectedScenario] = useState<string>('all')
  const [selectedPriority, setSelectedPriority] = useState<string>('all')
  const [selectedStatus, setSelectedStatus] = useState<string>('all')

  const uniqueScenarios = useMemo(() => {
    const set = new Set<string>()
    recommendations.forEach((r) => set.add(r.scenario))
    return Array.from(set).sort()
  }, [recommendations])

  const counts = useMemo(() => {
    return getRecommendationCounts(recommendations)
  }, [recommendations])

  const filteredRecommendations = useMemo(() => {
    return recommendations.filter((r) => {
      if (selectedScenario !== 'all' && r.scenario !== selectedScenario) return false
      if (selectedPriority !== 'all' && r.priority !== selectedPriority) return false
      if (selectedStatus !== 'all' && r.status !== selectedStatus) return false

      if (search.trim()) {
        const q = search.toLowerCase()
        const matchesTitle = r.title.toLowerCase().includes(q)
        const matchesAction = r.recommended_action.toLowerCase().includes(q)
        const matchesDesc = r.description.toLowerCase().includes(q)
        const matchesScenario = r.scenario.toLowerCase().includes(q)
        if (!matchesTitle && !matchesAction && !matchesDesc && !matchesScenario) {
          return false
        }
      }

      return true
    })
  }, [recommendations, selectedScenario, selectedPriority, selectedStatus, search])

  const handleResetFilters = () => {
    setSearch('')
    setSelectedScenario('all')
    setSelectedPriority('all')
    setSelectedStatus('all')
  }

  if (loading && recommendations.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Loading recommendations...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Header and Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Actionable Business Recommendations
            </h2>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-800 border border-slate-200">
              {filteredRecommendations.length} / {recommendations.length}
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-0.5">
            Rule-driven recommendations synthesized from validated model outputs and operational boundaries.
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
            <span>▶</span> New Evaluation
          </button>
        </div>
      </div>

      {/* Quick Status Filter Pills */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          onClick={() => setSelectedStatus('all')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            selectedStatus === 'all'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'bg-white text-slate-700 hover:bg-slate-50 border border-slate-300'
          }`}
        >
          All ({recommendations.length})
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatus('needs_review')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            selectedStatus === 'needs_review'
              ? 'bg-amber-600 text-white shadow-sm'
              : 'bg-white text-amber-800 hover:bg-amber-50 border border-amber-300'
          }`}
        >
          Needs Review ({counts.needsReview})
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatus('pending_approval')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            selectedStatus === 'pending_approval'
              ? 'bg-purple-600 text-white shadow-sm'
              : 'bg-white text-purple-800 hover:bg-purple-50 border border-purple-300'
          }`}
        >
          Pending Approval ({counts.pendingApproval})
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatus('approved')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            selectedStatus === 'approved'
              ? 'bg-emerald-600 text-white shadow-sm'
              : 'bg-white text-emerald-800 hover:bg-emerald-50 border border-emerald-300'
          }`}
        >
          Approved ({counts.approved})
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatus('completed')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            selectedStatus === 'completed'
              ? 'bg-sky-600 text-white shadow-sm'
              : 'bg-white text-sky-800 hover:bg-sky-50 border border-sky-300'
          }`}
        >
          Completed ({counts.completed})
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatus('rejected')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            selectedStatus === 'rejected'
              ? 'bg-rose-600 text-white shadow-sm'
              : 'bg-white text-rose-800 hover:bg-rose-50 border border-rose-300'
          }`}
        >
          Rejected ({counts.rejected})
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatus('dismissed')}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
            selectedStatus === 'dismissed'
              ? 'bg-slate-700 text-white shadow-sm'
              : 'bg-white text-slate-700 hover:bg-slate-50 border border-slate-300'
          }`}
        >
          Dismissed ({counts.dismissed})
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center gap-3 p-3 bg-white border border-slate-200 rounded-xl shadow-sm">
        <div className="flex-1 min-w-[220px]">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search recommendations by title, action, evidence, or scenario..."
            className="w-full px-3.5 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:bg-white transition-colors"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Scenario Filter */}
          <select
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-800 focus:outline-none focus:border-brand-500"
          >
            <option value="all">All Scenarios</option>
            {uniqueScenarios.map((sc) => (
              <option key={sc} value={sc}>
                {sc.toUpperCase()}
              </option>
            ))}
          </select>

          {/* Priority Filter */}
          <select
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-800 focus:outline-none focus:border-brand-500"
          >
            <option value="all">All Priorities</option>
            <option value="critical">Critical Priority</option>
            <option value="high">High Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="low">Low Priority</option>
            <option value="informational">Informational</option>
          </select>

          {/* Reset Filters */}
          {(search || selectedScenario !== 'all' || selectedPriority !== 'all' || selectedStatus !== 'all') && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="text-xs text-brand-600 hover:text-brand-800 font-semibold px-2 py-1 cursor-pointer"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Recommendations Cards Grid */}
      {filteredRecommendations.length === 0 ? (
        <div className="p-12 rounded-2xl bg-white border border-slate-200 shadow-sm text-center space-y-3">
          <span className="text-3xl block">🔍</span>
          <h4 className="text-sm font-bold text-slate-900">
            {recommendations.length === 0
              ? 'No Recommendations Generated'
              : 'No Recommendations Match Selected Filters'}
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            {recommendations.length === 0
              ? 'Run a decision evaluation against your prediction models, forecasts, or operational facts to trigger business recommendations.'
              : 'Try clearing your search terms or resetting scenario, priority, and status filters.'}
          </p>
          {recommendations.length === 0 ? (
            <button
              type="button"
              onClick={onOpenEvaluateModal}
              className="mt-3 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors cursor-pointer"
            >
              Run First Decision Evaluation
            </button>
          ) : (
            <button
              type="button"
              onClick={handleResetFilters}
              className="mt-3 px-3.5 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors cursor-pointer"
            >
              Clear All Filters
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredRecommendations.map((rec) => (
            <DecisionRecommendationCard
              key={rec.recommendation_id}
              recommendation={rec}
              onViewDetails={onViewDetails}
              onQuickApprove={onQuickApprove}
            />
          ))}
        </div>
      )}
    </div>
  )
}
