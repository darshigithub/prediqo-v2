import { useState, useEffect } from 'react'
import type { BusinessRule, RuleCreatePayload } from '../../types/decisionTypes'
import {
  listDecisionRules,
  createDecisionRule,
  updateDecisionRule,
  toggleDecisionRule,
  deleteDecisionRule,
} from '../../services/decisionApi'
import { getPriorityBadgeInfo, formatComparisonRule } from '../../utils/decisionUtils'
import DecisionRuleEditor from './DecisionRuleEditor'

interface DecisionRulesPageProps {
  rules?: BusinessRule[]
  loading?: boolean
  onRefresh?: () => void
}

export default function DecisionRulesPage({
  rules: propRules,
  loading: propLoading,
  onRefresh: propOnRefresh,
}: DecisionRulesPageProps = {}) {
  const [internalRules, setInternalRules] = useState<BusinessRule[]>([])
  const [internalLoading, setInternalLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedScenario, setSelectedScenario] = useState<string>('all')
  const [editingRule, setEditingRule] = useState<BusinessRule | null>(null)
  const [isEditorOpen, setIsEditorOpen] = useState(false)

  const rules = propRules !== undefined ? propRules : internalRules
  const loading = propLoading !== undefined ? propLoading : internalLoading

  const loadRules = async () => {
    if (propOnRefresh) {
      propOnRefresh()
      return
    }
    setInternalLoading(true)
    setError(null)
    try {
      const data = await listDecisionRules(selectedScenario !== 'all' ? selectedScenario : undefined)
      setInternalRules(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load rules.')
    } finally {
      setInternalLoading(false)
    }
  }

  useEffect(() => {
    if (propRules === undefined) {
      loadRules()
    }
  }, [selectedScenario, propRules])

  const handleToggle = async (rule: BusinessRule) => {
    try {
      const updated = await toggleDecisionRule(rule.rule_id, !rule.enabled)
      if (propOnRefresh) {
        propOnRefresh()
      } else {
        setInternalRules((prev) => prev.map((r) => (r.rule_id === rule.rule_id ? updated : r)))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to toggle rule.')
    }
  }

  const handleDelete = async (ruleId: string) => {
    if (!window.confirm('Are you sure you want to delete this business rule?')) return
    try {
      await deleteDecisionRule(ruleId)
      if (propOnRefresh) {
        propOnRefresh()
      } else {
        setInternalRules((prev) => prev.filter((r) => r.rule_id !== ruleId))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete rule.')
    }
  }

  const handleSaveRule = async (payload: RuleCreatePayload) => {
    if (editingRule) {
      await updateDecisionRule(editingRule.rule_id, payload)
    } else {
      await createDecisionRule(payload)
    }
    await loadRules()
  }

  return (
    <div className="space-y-5">
      {/* Top Banner & Scenario Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Settings & Business Rule Configuration
            </h2>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-800 border border-slate-200">
              {rules.length} rules
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-0.5 max-w-xl">
            Configure deterministic evaluation thresholds, evidence mappings, and operational approval policies.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
              Scenario:
            </span>
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              className="bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-brand-500"
            >
              <option value="all">All Scenarios ({rules.length})</option>
              <option value="inventory">Inventory & Stock</option>
              <option value="demand">Sales & Demand Trajectory</option>
              <option value="churn">Customer Churn & Retention</option>
              <option value="data_quality">Data Pipeline Quality</option>
              <option value="general">General Operations</option>
            </select>
          </div>

          <button
            type="button"
            onClick={() => {
              setEditingRule(null)
              setIsEditorOpen(true)
            }}
            className="py-1.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs shadow-sm transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <span>＋</span>
            <span>New Business Rule</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-rose-600 hover:text-rose-900 font-semibold text-xs ml-3"
          >
            ✕
          </button>
        </div>
      )}

      {loading ? (
        <div className="p-16 text-center text-slate-500 space-y-2">
          <div className="inline-block animate-spin text-2xl">⚙</div>
          <div className="text-sm font-medium">Loading configured business rules...</div>
        </div>
      ) : rules.length === 0 ? (
        <div className="p-16 rounded-2xl bg-white border border-slate-200 shadow-sm text-center space-y-3">
          <div className="text-3xl">📋</div>
          <h4 className="text-base font-bold text-slate-900">No Business Rules Found</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
            No rules match this scenario filter. Create your first deterministic rule above to begin evaluating business scenarios.
          </p>
          <button
            type="button"
            onClick={() => {
              setEditingRule(null)
              setIsEditorOpen(true)
            }}
            className="mt-2 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-sm transition-colors cursor-pointer"
          >
            Create First Business Rule
          </button>
        </div>
      ) : (
        <div className="border border-slate-200 rounded-2xl overflow-hidden bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 text-slate-700 uppercase tracking-wider font-semibold border-b border-slate-200 text-[11px]">
                <tr>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Rule Name</th>
                  <th className="py-3 px-4">Scenario</th>
                  <th className="py-3 px-4">Condition</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Sign-Off</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rules.map((rule) => {
                  const conditionStr = formatComparisonRule(rule)
                  const pBadge = getPriorityBadgeInfo(rule.priority)

                  return (
                    <tr key={rule.rule_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-4">
                        <button
                          type="button"
                          onClick={() => handleToggle(rule)}
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold cursor-pointer transition-colors border ${
                            rule.enabled
                              ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                              : 'bg-slate-100 text-slate-600 border-slate-300'
                          }`}
                        >
                          {rule.enabled ? 'ACTIVE' : 'DISABLED'}
                        </button>
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-900">{rule.name}</div>
                        {rule.description && (
                          <div className="text-[11px] text-slate-600 truncate max-w-xs">{rule.description}</div>
                        )}
                      </td>

                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700 font-mono font-medium uppercase border border-slate-200">
                          {rule.scenario}
                        </span>
                      </td>

                      <td className="py-3 px-4 font-mono text-[11px] text-slate-800">
                        {conditionStr}
                      </td>

                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${pBadge.bg} ${pBadge.text} ${pBadge.border}`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${pBadge.dot}`} />
                          {pBadge.label}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-[11px]">
                        {rule.requires_approval ? (
                          <span className="text-purple-700 font-medium">Required</span>
                        ) : (
                          <span className="text-slate-600">Optional</span>
                        )}
                      </td>

                      <td className="py-3 px-4 text-right space-x-2.5">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingRule(rule)
                            setIsEditorOpen(true)
                          }}
                          className="text-brand-600 hover:text-brand-800 font-semibold transition-colors cursor-pointer"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(rule.rule_id)}
                          className="text-rose-600 hover:text-rose-800 font-semibold transition-colors cursor-pointer"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {isEditorOpen && (
        <DecisionRuleEditor
          initialRule={editingRule}
          onClose={() => {
            setIsEditorOpen(false)
            setEditingRule(null)
          }}
          onSave={handleSaveRule}
        />
      )}
    </div>
  )
}
