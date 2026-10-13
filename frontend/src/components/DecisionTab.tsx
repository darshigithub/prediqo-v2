import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import type { Recommendation, DecisionOverviewStats } from '../types/decisionTypes'
import {
  getDecisionOverview,
  listDecisionRecommendations,
  updateRecommendationStatus,
} from '../services/decisionApi'
import DecisionRecommendationCard from './decisions/DecisionRecommendationCard'
import DecisionDetailModal from './decisions/DecisionDetailModal'
import DecisionEvaluateModal from './decisions/DecisionEvaluateModal'

interface DecisionTabProps {
  datasetId: string
}

export default function DecisionTab({ datasetId }: DecisionTabProps) {
  const [stats, setStats] = useState<DecisionOverviewStats | null>(null)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Modals
  const [showEvaluateModal, setShowEvaluateModal] = useState(false)
  const [activeDetailRec, setActiveDetailRec] = useState<Recommendation | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, recsRes] = await Promise.all([
        getDecisionOverview(),
        listDecisionRecommendations(),
      ])
      setStats(statsRes)
      setRecommendations(Array.isArray(recsRes) ? recsRes : (recsRes as any)?.recommendations || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load decisions.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData, datasetId])

  const handleUpdateStatus = async (
    recId: string,
    newStatus: any,
    comment?: string
  ) => {
    await updateRecommendationStatus(recId, {
      new_status: newStatus,
      comment: comment || null,
      actor: 'user',
    })
    await loadData()
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">⚖️</span>
            <h3 className="text-base font-bold text-slate-900">
              Operational Decision Intelligence
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-brand-100 text-brand-700 font-semibold border border-brand-200">
              Deterministic Rules
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1 max-w-xl">
            Evaluate business policies against prediction outputs, demand projections, and data quality metrics without retraining models.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/decisions"
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg border border-slate-300 transition-colors"
          >
            Open Full Decision Center ↗
          </Link>
          <button
            type="button"
            onClick={() => setShowEvaluateModal(true)}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <span>▶</span> Run Evaluation
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-xs">
          {error}
        </div>
      )}

      {/* Quick Metrics Bar */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] text-slate-500 font-medium block">Total Active Rules</span>
            <span className="text-xl font-bold text-slate-900 font-mono">
              {stats.total_active_rules}
            </span>
          </div>
          <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] text-slate-500 font-medium block">Needs Review</span>
            <span className={`text-xl font-bold font-mono ${stats.needs_review_count > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
              {stats.needs_review_count}
            </span>
          </div>
          <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] text-slate-500 font-medium block">Pending Approval</span>
            <span className="text-xl font-bold text-purple-700 font-mono">
              {stats.pending_approval_count}
            </span>
          </div>
          <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] text-slate-500 font-medium block">High Priority Actions</span>
            <span className={`text-xl font-bold font-mono ${stats.high_priority_count > 0 ? 'text-rose-600' : 'text-slate-900'}`}>
              {stats.high_priority_count}
            </span>
          </div>
        </div>
      )}

      {/* Recommendations Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
            Actionable Recommendations ({recommendations.length})
          </h4>
          <button
            onClick={loadData}
            className="text-xs text-brand-600 hover:text-brand-700 font-semibold"
          >
            ↻ Refresh
          </button>
        </div>

        {loading && recommendations.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">
            Loading decision recommendations...
          </div>
        ) : recommendations.length === 0 ? (
          <div className="p-10 rounded-xl bg-white border border-slate-200 shadow-sm text-center space-y-3">
            <span className="text-3xl block">⚖️</span>
            <h4 className="text-sm font-semibold text-slate-800">No Recommendations Generated Yet</h4>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Run a deterministic decision evaluation to verify this dataset and your trained models against active operational rules.
            </p>
            <button
              onClick={() => setShowEvaluateModal(true)}
              className="mt-2 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors cursor-pointer"
            >
              Evaluate Dataset Decisions
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendations.map((rec) => (
              <DecisionRecommendationCard
                key={rec.recommendation_id}
                recommendation={rec}
                onViewDetails={(r) => setActiveDetailRec(r)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      {showEvaluateModal && (
        <DecisionEvaluateModal
          onClose={() => setShowEvaluateModal(false)}
          onEvaluationCompleted={() => loadData()}
        />
      )}

      {activeDetailRec && (
        <DecisionDetailModal
          recommendation={activeDetailRec}
          onClose={() => setActiveDetailRec(null)}
          onUpdateStatus={handleUpdateStatus}
        />
      )}
    </div>
  )
}
