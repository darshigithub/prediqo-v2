import { useState, useMemo } from 'react'
import type { DecisionAuditItem } from '../../types/decisionTypes'

interface DecisionHistoryPageProps {
  auditLog: DecisionAuditItem[]
  loading: boolean
  onRefresh: () => void
}

export default function DecisionHistoryPage({
  auditLog,
  loading,
  onRefresh,
}: DecisionHistoryPageProps) {
  const [search, setSearch] = useState('')
  const [selectedAction, setSelectedAction] = useState<string>('all')

  const uniqueActions = useMemo(() => {
    const set = new Set<string>()
    auditLog.forEach((item) => set.add(item.action))
    return Array.from(set).sort()
  }, [auditLog])

  const filteredLog = useMemo(() => {
    return auditLog.filter((item) => {
      if (selectedAction !== 'all' && item.action !== selectedAction) return false

      if (search.trim()) {
        const q = search.toLowerCase()
        const matchesActor = item.actor.toLowerCase().includes(q)
        const matchesAction = item.action.toLowerCase().includes(q)
        const matchesComment = item.comment ? item.comment.toLowerCase().includes(q) : false
        const matchesRec = item.recommendation_id ? item.recommendation_id.toLowerCase().includes(q) : false
        const matchesEval = item.evaluation_id ? item.evaluation_id.toLowerCase().includes(q) : false
        if (!matchesActor && !matchesAction && !matchesComment && !matchesRec && !matchesEval) {
          return false
        }
      }

      return true
    })
  }, [auditLog, selectedAction, search])

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'STATUS_CHANGED':
        return 'bg-purple-50 text-purple-700 border-purple-200'
      case 'EVALUATION_COMPLETED':
        return 'bg-blue-50 text-blue-700 border-blue-200'
      case 'RULE_CREATED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200'
      case 'RULE_UPDATED':
      case 'RULE_TOGGLED':
        return 'bg-amber-50 text-amber-700 border-amber-200'
      case 'RULE_DELETED':
        return 'bg-rose-50 text-rose-700 border-rose-200'
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200'
    }
  }

  if (loading && auditLog.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Loading Decision Audit History...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Decision History & Audit Trail
            </h2>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-800 border border-slate-200">
              {filteredLog.length} events
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-0.5">
            Immutable log of all evaluation runs, human approval decisions, rejections with mandatory reasons, and rule modifications.
          </p>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 rounded-lg border border-slate-300 shadow-sm transition-colors cursor-pointer"
        >
          ↻ Refresh Log
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center gap-3 p-3 bg-white border border-slate-200 rounded-xl shadow-sm">
        <div className="flex-1 min-w-[220px]">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by actor, action, recommendation ID, or reason comments..."
            className="w-full px-3.5 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:bg-white transition-colors"
          />
        </div>

        <div>
          <select
            value={selectedAction}
            onChange={(e) => setSelectedAction(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-800 focus:outline-none focus:border-brand-500"
          >
            <option value="all">All Actions</option>
            {uniqueActions.map((act) => (
              <option key={act} value={act}>
                {act}
              </option>
            ))}
          </select>
        </div>

        {(search || selectedAction !== 'all') && (
          <button
            type="button"
            onClick={() => {
              setSearch('')
              setSelectedAction('all')
            }}
            className="text-xs text-brand-600 hover:text-brand-800 font-semibold px-2 py-1 cursor-pointer"
          >
            Reset
          </button>
        )}
      </div>

      {/* Audit Log Table */}
      {filteredLog.length === 0 ? (
        <div className="p-12 rounded-2xl bg-white border border-slate-200 shadow-sm text-center space-y-3">
          <span className="text-3xl block">📜</span>
          <h4 className="text-sm font-bold text-slate-900">No Audit Events Found</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Decision events will automatically appear here as evaluations are executed, rules are modified, or human approvals and rejections are logged.
          </p>
        </div>
      ) : (
        <div className="border border-slate-200 rounded-2xl overflow-hidden bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-700 uppercase tracking-wider font-semibold border-b border-slate-200 text-[11px]">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Target Entity</th>
                  <th className="py-3 px-4">Status Transition</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Rationale / Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredLog.map((item) => (
                  <tr key={item.audit_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 text-slate-600 whitespace-nowrap font-mono text-[11px]">
                      {new Date(item.timestamp).toLocaleDateString()} {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${getActionBadge(item.action)}`}>
                        {item.action}
                      </span>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap font-mono text-[11px]">
                      {item.recommendation_id ? (
                        <span title={item.recommendation_id} className="text-brand-700 font-semibold">
                          rec:{item.recommendation_id.slice(0, 8)}...
                        </span>
                      ) : item.evaluation_id ? (
                        <span title={item.evaluation_id} className="text-blue-700 font-semibold">
                          eval:{item.evaluation_id.slice(0, 8)}...
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      {item.previous_status || item.new_status ? (
                        <div className="flex items-center gap-1.5 text-[11px]">
                          <span className="text-slate-500 font-medium">{item.previous_status || '—'}</span>
                          <span className="text-slate-400">→</span>
                          <span className="text-slate-900 font-bold">{item.new_status || '—'}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-medium">
                        {item.actor}
                      </span>
                    </td>

                    <td className="py-3 px-4 max-w-xs break-words">
                      {item.comment ? (
                        <span className="text-slate-800 font-medium bg-amber-50/80 border border-amber-200/60 px-2 py-1 rounded inline-block">
                          {item.comment}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic text-[11px]">No notes recorded</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
