import { useState } from 'react'
import type {
  BusinessRule,
  ComparisonOperator,
  DecisionPriority,
  EvidenceSourceType,
  RuleCreatePayload,
} from '../../types/decisionTypes'
import { validateDecisionRule } from '../../services/decisionApi'

interface DecisionRuleEditorProps {
  initialRule?: BusinessRule | null
  onClose: () => void
  onSave: (payload: RuleCreatePayload) => Promise<void>
}

export default function DecisionRuleEditor({
  initialRule,
  onClose,
  onSave,
}: DecisionRuleEditorProps) {
  const [name, setName] = useState(initialRule?.name || '')
  const [description, setDescription] = useState(initialRule?.description || '')
  const [scenario, setScenario] = useState(initialRule?.scenario || 'inventory')
  const [enabled, setEnabled] = useState(initialRule ? initialRule.enabled : true)
  const [priority, setPriority] = useState<DecisionPriority>(initialRule?.priority || 'medium')
  const [evidenceSource, setEvidenceSource] = useState<EvidenceSourceType>(
    initialRule?.evidence_source || 'operational_fact'
  )
  const [fieldName, setFieldName] = useState(initialRule?.field_name || '')
  const [operator, setOperator] = useState<ComparisonOperator>(initialRule?.operator || 'gt')
  const [comparisonMode, setComparisonMode] = useState<'static' | 'dynamic'>(
    initialRule?.compare_to_field ? 'dynamic' : 'static'
  )
  const [thresholdValue, setThresholdValue] = useState(
    initialRule?.threshold_value !== undefined && initialRule?.threshold_value !== null
      ? String(initialRule.threshold_value)
      : ''
  )
  const [compareToField, setCompareToField] = useState(initialRule?.compare_to_field || '')
  const [expectedUnit, setExpectedUnit] = useState(initialRule?.expected_unit || '')
  const [recommendedAction, setRecommendedAction] = useState(initialRule?.recommended_action || '')
  const [explanationTemplate, setExplanationTemplate] = useState(
    initialRule?.explanation_template || '{field} ({value}) {op} {threshold}'
  )
  const [requiresApproval, setRequiresApproval] = useState(
    initialRule ? initialRule.requires_approval : true
  )

  const [validationResult, setValidationResult] = useState<{ is_valid: boolean; message: string } | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRunValidation = async () => {
    setIsValidating(true)
    setValidationResult(null)
    setError(null)

    try {
      const parsedVal =
        comparisonMode === 'static' && thresholdValue.trim() !== ''
          ? !isNaN(Number(thresholdValue))
            ? Number(thresholdValue)
            : thresholdValue
          : undefined

      const res = await validateDecisionRule({
        field_name: fieldName,
        operator,
        threshold_value: parsedVal,
        compare_to_field: comparisonMode === 'dynamic' ? compareToField : undefined,
        expected_unit: expectedUnit || undefined,
      })
      setValidationResult(res)
    } catch (err: any) {
      setError(err.message || 'Validation request failed.')
    } finally {
      setIsValidating(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Please provide a rule name.')
      return
    }
    if (!fieldName.trim()) {
      setError('Please provide an evaluation field name.')
      return
    }
    if (!recommendedAction.trim()) {
      setError('Please define the recommended action for when this rule triggers.')
      return
    }

    setIsSaving(true)
    setError(null)

    try {
      const parsedVal =
        comparisonMode === 'static' && thresholdValue.trim() !== ''
          ? !isNaN(Number(thresholdValue))
            ? Number(thresholdValue)
            : thresholdValue
          : undefined

      await onSave({
        name: name.trim(),
        description: description.trim(),
        scenario: scenario.trim().toLowerCase(),
        enabled,
        priority,
        evidence_source: evidenceSource,
        field_name: fieldName.trim(),
        operator,
        threshold_value: parsedVal,
        compare_to_field: comparisonMode === 'dynamic' && compareToField.trim() ? compareToField.trim() : null,
        expected_unit: expectedUnit.trim() || null,
        recommended_action: recommendedAction.trim(),
        explanation_template: explanationTemplate.trim(),
        requires_approval: requiresApproval,
      })
      onClose()
    } catch (err: any) {
      setError(err.message || 'Failed to save rule.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white border border-slate-200 rounded-2xl shadow-2xl p-6 sm:p-7 space-y-5 text-slate-800 my-8">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="text-lg font-bold text-slate-900">
            {initialRule ? `Edit Rule: ${initialRule.name}` : 'Create New Business Rule'}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4 text-xs">
          {/* Rule Name & Scenario */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-semibold mb-1">Rule Name *</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Stockout Risk Warning"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white"
              />
            </div>
            <div>
              <label className="block text-slate-700 font-semibold mb-1">Business Scenario *</label>
              <select
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white"
              >
                <option value="inventory">Inventory & Stock</option>
                <option value="demand">Sales & Demand Trajectory</option>
                <option value="churn">Customer Churn & Retention</option>
                <option value="data_quality">Data Pipeline Quality</option>
                <option value="general">General Operations</option>
              </select>
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Why this rule exists and when it should trigger"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white"
            />
          </div>

          {/* Priority & Evidence Source */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-semibold mb-1">Recommendation Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as DecisionPriority)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="informational">Informational</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-700 font-semibold mb-1">Evidence Source</label>
              <select
                value={evidenceSource}
                onChange={(e) => setEvidenceSource(e.target.value as EvidenceSourceType)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white"
              >
                <option value="operational_fact">Operational Fact (User Input)</option>
                <option value="forecast">Time-Series Forecast</option>
                <option value="prediction">ML Prediction</option>
                <option value="data_quality">Data Quality Metric</option>
                <option value="model_metric">Model Evaluation Metric</option>
              </select>
            </div>
          </div>

          {/* Condition Logic Box */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="text-[11px] font-bold text-slate-800 uppercase tracking-wider">
              Evaluation Condition Logic (Deterministic)
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <div>
                <label className="block text-[11px] text-slate-600 font-medium mb-1">Field to Evaluate *</label>
                <input
                  type="text"
                  required
                  value={fieldName}
                  onChange={(e) => setFieldName(e.target.value)}
                  placeholder="e.g. predicted_demand"
                  className="w-full bg-white border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-600 font-medium mb-1">Operator</label>
                <select
                  value={operator}
                  onChange={(e) => setOperator(e.target.value as ComparisonOperator)}
                  className="w-full bg-white border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500"
                >
                  <option value="gt">&gt; Greater Than</option>
                  <option value="gte">&ge; Greater Than or Equal</option>
                  <option value="lt">&lt; Less Than</option>
                  <option value="lte">&le; Less Than or Equal</option>
                  <option value="eq">= Equal To</option>
                  <option value="neq">&ne; Not Equal To</option>
                  <option value="is_present">Is Present (Not Missing)</option>
                  <option value="is_missing">Is Missing (Null/Empty)</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-slate-600 font-medium mb-1">Expected Unit (Optional)</label>
                <input
                  type="text"
                  value={expectedUnit}
                  onChange={(e) => setExpectedUnit(e.target.value)}
                  placeholder="e.g. units, $, %, days"
                  className="w-full bg-white border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>

            {operator !== 'is_present' && operator !== 'is_missing' && (
              <div className="pt-2 border-t border-slate-200 space-y-2">
                <div className="flex gap-4 text-[11px]">
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-700 font-medium">
                    <input
                      type="radio"
                      name="compMode"
                      checked={comparisonMode === 'static'}
                      onChange={() => setComparisonMode('static')}
                    />
                    <span>Static Threshold Value</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-700 font-medium">
                    <input
                      type="radio"
                      name="compMode"
                      checked={comparisonMode === 'dynamic'}
                      onChange={() => setComparisonMode('dynamic')}
                    />
                    <span>Dynamic Comparison Against Another Field</span>
                  </label>
                </div>

                {comparisonMode === 'static' ? (
                  <div>
                    <label className="block text-[11px] text-slate-600 font-medium mb-1">Threshold Value *</label>
                    <input
                      type="text"
                      value={thresholdValue}
                      onChange={(e) => setThresholdValue(e.target.value)}
                      placeholder="e.g. 500, 85.0, or active"
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-[11px] text-slate-600 font-medium mb-1">Target Field to Compare Against *</label>
                    <input
                      type="text"
                      value={compareToField}
                      onChange={(e) => setCompareToField(e.target.value)}
                      placeholder="e.g. available_inventory or max_capacity"
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-brand-500"
                    />
                  </div>
                )}
              </div>
            )}

            {/* Validate Rule Spec Button */}
            <div className="pt-1 flex items-center justify-between">
              <button
                type="button"
                disabled={isValidating}
                onClick={handleRunValidation}
                className="py-1 px-3 rounded-lg bg-white hover:bg-slate-100 border border-slate-300 text-brand-700 text-[11px] font-semibold transition-colors cursor-pointer"
              >
                {isValidating ? 'Validating...' : '✓ Validate Rule Specification'}
              </button>

              {validationResult && (
                <span className={`text-[11px] font-medium ${validationResult.is_valid ? 'text-emerald-700' : 'text-rose-700'}`}>
                  {validationResult.is_valid ? '✓ ' : '✕ '} {validationResult.message}
                </span>
              )}
            </div>
          </div>

          {/* Recommended Action */}
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Recommended Action *</label>
            <textarea
              required
              rows={2}
              value={recommendedAction}
              onChange={(e) => setRecommendedAction(e.target.value)}
              placeholder="Clear, actionable operational guidance for when this rule triggers"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-brand-500 focus:bg-white"
            />
          </div>

          {/* Explanation Template */}
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Explanation Template (Optional)</label>
            <input
              type="text"
              value={explanationTemplate}
              onChange={(e) => setExplanationTemplate(e.target.value)}
              placeholder="{field} ({value}) {op} {threshold}"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-900 font-mono text-xs focus:outline-none focus:border-brand-500 focus:bg-white"
            />
          </div>

          {/* Checkbox Options */}
          <div className="flex flex-wrap gap-5 pt-1">
            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                checked={requiresApproval}
                onChange={(e) => setRequiresApproval(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span>Requires Human Approval before action</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span>Rule Enabled</span>
            </label>
          </div>

          {/* Action Buttons */}
          <div className="pt-4 border-t border-slate-100 flex justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="py-2 px-4 rounded-lg bg-white hover:bg-slate-100 text-slate-700 font-semibold text-xs border border-slate-300 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="py-2 px-5 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer"
            >
              {isSaving ? 'Saving Rule...' : initialRule ? 'Save Changes' : 'Create Rule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
