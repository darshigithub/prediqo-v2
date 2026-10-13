import { useState, useEffect, useCallback, useMemo } from 'react'
import type {
  DecisionOverviewStats,
  Recommendation,
  BusinessRule,
  DecisionAuditItem,
  RecommendationStatus,
} from '../types/decisionTypes'
import {
  getDecisionOverview,
  listDecisionRecommendations,
  listDecisionRules,
  getDecisionAuditLog,
  updateRecommendationStatus,
} from '../services/decisionApi'
import { getRecommendationCounts } from '../utils/decisionUtils'

import DecisionOverview from '../components/decisions/DecisionOverview'
import DecisionRecommendationsList from '../components/decisions/DecisionRecommendationsList'
import DecisionRulesPage from '../components/decisions/DecisionRulesPage'
import DecisionHistoryPage from '../components/decisions/DecisionHistoryPage'
import DecisionDetailModal from '../components/decisions/DecisionDetailModal'
import DecisionEvaluateModal from '../components/decisions/DecisionEvaluateModal'

type TabType = 'overview' | 'recommendations' | 'history' | 'settings'

export default function DecisionCenterPage() {
  const [activeTab, setActiveTab] = useState<TabType>('overview')

  // Data states
  const [stats, setStats] = useState<DecisionOverviewStats | null>(null)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [rules, setRules] = useState<BusinessRule[]>([])
  const [auditLog, setAuditLog] = useState<DecisionAuditItem[]>([])

  // Loading & error states
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Modals
  const [showEvaluateModal, setShowEvaluateModal] = useState(false)
  const [activeDetailRec, setActiveDetailRec] = useState<Recommendation | null>(null)

  // Load all decision data
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, recsRes, rulesRes, auditRes] = await Promise.all([
        getDecisionOverview(),
        listDecisionRecommendations(),
        listDecisionRules(),
        getDecisionAuditLog(),
      ])

      setStats(statsRes)
      setRecommendations(Array.isArray(recsRes) ? recsRes : (recsRes as any)?.recommendations || [])
      setRules(Array.isArray(rulesRes) ? rulesRes : (rulesRes as any)?.rules || [])
      setAuditLog(Array.isArray(auditRes) ? auditRes : (auditRes as any)?.audit_log || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load Decision Center data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Count aggregates
  const counts = useMemo(() => {
    return getRecommendationCounts(recommendations)
  }, [recommendations])

  // Handle recommendation status updates (approve, reject, dismiss, complete)
  const handleUpdateStatus = async (
    recId: string,
    newStatus: RecommendationStatus,
    comment?: string
  ) => {
    await updateRecommendationStatus(recId, {
      new_status: newStatus,
      comment: comment || null,
      actor: 'user',
    })
    // Reload state after status change
    await loadData()
  }

  // Quick-approve helper
  const handleQuickApprove = async (rec: Recommendation) => {
    try {
      await handleUpdateStatus(rec.recommendation_id, 'approved', 'Quick-approved from dashboard')
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`)
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="text-2xl">⚖️</span>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Decision Center</h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-brand-100 text-brand-700 border border-brand-200 font-semibold">
              Operational Intelligence
            </span>
          </div>
          <p className="text-sm text-slate-600 mt-1 max-w-2xl leading-relaxed">
            Deterministic rule-based business recommendations grounded in validated prediction &amp; forecasting intelligence.
          </p>
        </div>

        <button
          onClick={() => setShowEvaluateModal(true)}
          className="px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors flex items-center gap-2 cursor-pointer"
        >
          <span>▶</span> Run Decision Evaluation
        </button>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-rose-600 hover:text-rose-900 text-xs font-semibold ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 4 Navigation Tabs: Overview, Recommendations, History, Settings */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-1">
        {/* 1. Overview */}
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
            activeTab === 'overview'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <span>📊</span> Overview
        </button>

        {/* 2. Recommendations */}
        <button
          onClick={() => setActiveTab('recommendations')}
          className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
            activeTab === 'recommendations'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <span>📋</span> Recommendations
          {counts.awaitingAction > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500 text-white font-bold">
              {counts.awaitingAction}
            </span>
          )}
        </button>

        {/* 3. History */}
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
            activeTab === 'history'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <span>📜</span> History
          {auditLog.length > 0 && (
            <span className="text-[10px] opacity-75 font-mono">({auditLog.length})</span>
          )}
        </button>

        {/* 4. Settings */}
        <button
          onClick={() => setActiveTab('settings')}
          className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
            activeTab === 'settings'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <span>⚙️</span> Settings &amp; Rules
          <span className="text-[10px] opacity-75 font-mono">({rules.length})</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div>
        {activeTab === 'overview' && (
          <DecisionOverview
            stats={stats}
            recommendations={recommendations}
            loading={loading}
            onOpenEvaluateModal={() => setShowEvaluateModal(true)}
            onViewRecommendation={(rec) => setActiveDetailRec(rec)}
            onGoToRecommendationsTab={() => setActiveTab('recommendations')}
            onGoToHistoryTab={() => setActiveTab('history')}
            onGoToSettingsTab={() => setActiveTab('settings')}
            onRefresh={loadData}
          />
        )}

        {activeTab === 'recommendations' && (
          <DecisionRecommendationsList
            recommendations={recommendations}
            loading={loading}
            onViewDetails={(rec) => setActiveDetailRec(rec)}
            onQuickApprove={handleQuickApprove}
            onRefresh={loadData}
            onOpenEvaluateModal={() => setShowEvaluateModal(true)}
          />
        )}

        {activeTab === 'history' && (
          <DecisionHistoryPage
            auditLog={auditLog}
            loading={loading}
            onRefresh={loadData}
          />
        )}

        {activeTab === 'settings' && (
          <DecisionRulesPage
            rules={rules}
            loading={loading}
            onRefresh={loadData}
          />
        )}
      </div>

      {/* Modals */}
      {showEvaluateModal && (
        <DecisionEvaluateModal
          onClose={() => setShowEvaluateModal(false)}
          onEvaluationCompleted={(_eval) => {
            loadData()
          }}
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
