import type {
  DecisionPriority,
  RecommendationStatus,
  ComparisonOperator,
  RuleCreatePayload,
  BusinessRule,
  Recommendation,
} from '../types/decisionTypes'

/**
 * Format evidence value with appropriate units and number localization.
 */
export function formatEvidenceValue(value: any, unit?: string | null): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'boolean') return value ? 'True' : 'False'

  if (typeof value === 'number') {
    const formattedNum = Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 })

    if (!unit) return formattedNum
    if (unit === '$') return `$${formattedNum}`
    if (unit === '%') return `${formattedNum}%`
    return `${formattedNum} ${unit}`
  }

  const str = String(value)
  if (unit && unit !== '$' && unit !== '%') {
    return `${str} ${unit}`
  }
  return str
}

/**
 * Priority badge display metadata for enterprise light/dark UI.
 */
export function getPriorityBadgeInfo(priority: DecisionPriority): {
  label: string
  bg: string
  text: string
  border: string
  dot: string
} {
  switch (priority) {
    case 'critical':
      return {
        label: 'Critical',
        bg: 'bg-rose-50',
        text: 'text-rose-700',
        border: 'border-rose-200',
        dot: 'bg-rose-500',
      }
    case 'high':
      return {
        label: 'High',
        bg: 'bg-amber-50',
        text: 'text-amber-700',
        border: 'border-amber-200',
        dot: 'bg-amber-500',
      }
    case 'medium':
      return {
        label: 'Medium',
        bg: 'bg-blue-50',
        text: 'text-blue-700',
        border: 'border-blue-200',
        dot: 'bg-blue-500',
      }
    case 'low':
      return {
        label: 'Low',
        bg: 'bg-slate-100',
        text: 'text-slate-700',
        border: 'border-slate-200',
        dot: 'bg-slate-400',
      }
    case 'informational':
    default:
      return {
        label: 'Info',
        bg: 'bg-indigo-50',
        text: 'text-indigo-700',
        border: 'border-indigo-200',
        dot: 'bg-indigo-400',
      }
  }
}

/**
 * Recommendation status badge metadata and display properties.
 */
export function getStatusBadgeInfo(status: RecommendationStatus): {
  label: string
  bg: string
  text: string
  border: string
  description: string
  icon: string
} {
  switch (status) {
    case 'needs_review':
      return {
        label: 'Needs Review',
        bg: 'bg-amber-50',
        text: 'text-amber-800',
        border: 'border-amber-300',
        description: 'New recommendation requires operational review.',
        icon: '⏳',
      }
    case 'pending_approval':
      return {
        label: 'Pending Approval',
        bg: 'bg-purple-50',
        text: 'text-purple-800',
        border: 'border-purple-300',
        description: 'Awaiting human authorization before actioning.',
        icon: '🛡️',
      }
    case 'approved':
      return {
        label: 'Approved',
        bg: 'bg-emerald-50',
        text: 'text-emerald-800',
        border: 'border-emerald-300',
        description: 'Authorized for operational execution.',
        icon: '✓',
      }
    case 'rejected':
      return {
        label: 'Rejected',
        bg: 'bg-rose-50',
        text: 'text-rose-800',
        border: 'border-rose-300',
        description: 'Rejected with recorded business justification.',
        icon: '✕',
      }
    case 'completed':
      return {
        label: 'Completed',
        bg: 'bg-sky-50',
        text: 'text-sky-800',
        border: 'border-sky-300',
        description: 'Operational action successfully performed and verified.',
        icon: '✓✓',
      }
    case 'dismissed':
      return {
        label: 'Dismissed',
        bg: 'bg-slate-100',
        text: 'text-slate-600',
        border: 'border-slate-300',
        description: 'Archived as non-actionable or superseded.',
        icon: 'Archive',
      }
    default:
      return {
        label: status,
        bg: 'bg-slate-100',
        text: 'text-slate-700',
        border: 'border-slate-300',
        description: 'Status update.',
        icon: '•',
      }
  }
}

/**
 * Whether the status requires an explicit comment/reason.
 * Strictly mandated for 'rejected' and 'dismissed'.
 */
export function requiresStatusComment(status: RecommendationStatus): boolean {
  return status === 'rejected' || status === 'dismissed'
}

/**
 * Whether a status is considered terminal in the workflow.
 */
export function isTerminalStatus(status: RecommendationStatus): boolean {
  return status === 'completed' || status === 'rejected' || status === 'dismissed'
}

/**
 * Validates permissible lifecycle transitions.
 */
export function canTransitionTo(
  current: RecommendationStatus,
  target: RecommendationStatus
): boolean {
  if (current === target) return false

  // From needs_review or pending_approval: can go to approved, rejected, dismissed
  if (current === 'needs_review' || current === 'pending_approval') {
    return target === 'approved' || target === 'rejected' || target === 'dismissed'
  }

  // From approved: can go to completed, dismissed, rejected
  if (current === 'approved') {
    return target === 'completed' || target === 'dismissed' || target === 'rejected'
  }

  // Terminal states (completed, rejected, dismissed): can reopen to needs_review if necessary
  if (current === 'completed' || current === 'rejected' || current === 'dismissed') {
    return target === 'needs_review'
  }

  return false
}

/**
 * Format rule condition logic into readable formula text.
 */
export function formatComparisonRule(rule: Partial<BusinessRule>): string {
  if (!rule.field_name || !rule.operator) return 'N/A'

  if (rule.operator === 'is_present') {
    return `${rule.field_name} is present`
  }
  if (rule.operator === 'is_missing') {
    return `${rule.field_name} is missing`
  }

  const opSymbols: Record<string, string> = {
    gt: '>',
    gte: '>=',
    lt: '<',
    lte: '<=',
    eq: '=',
    neq: '!=',
  }
  const symbol = opSymbols[rule.operator] || rule.operator

  if (rule.compare_to_field) {
    return `${rule.field_name} ${symbol} field:${rule.compare_to_field}`
  }

  const unitStr = rule.expected_unit ? ` ${rule.expected_unit}` : ''
  return `${rule.field_name} ${symbol} ${rule.threshold_value ?? ''}${unitStr}`
}

/**
 * Aggregate counts for each status across a collection of recommendations.
 */
export function getRecommendationCounts(recommendations: Recommendation[]): {
  total: number
  needsReview: number
  pendingApproval: number
  approved: number
  completed: number
  rejected: number
  dismissed: number
  awaitingAction: number
} {
  let needsReview = 0
  let pendingApproval = 0
  let approved = 0
  let completed = 0
  let rejected = 0
  let dismissed = 0

  for (const r of recommendations) {
    switch (r.status) {
      case 'needs_review':
        needsReview++
        break
      case 'pending_approval':
        pendingApproval++
        break
      case 'approved':
        approved++
        break
      case 'completed':
        completed++
        break
      case 'rejected':
        rejected++
        break
      case 'dismissed':
        dismissed++
        break
    }
  }

  return {
    total: recommendations.length,
    needsReview,
    pendingApproval,
    approved,
    completed,
    rejected,
    dismissed,
    awaitingAction: needsReview + pendingApproval,
  }
}

/**
 * Client-side validation for business rule creation.
 */
export function validateRuleForm(rule: Partial<RuleCreatePayload>): {
  isValid: boolean
  errors: string[]
} {
  const errors: string[] = []

  if (!rule.name || !rule.name.trim()) {
    errors.push('Rule name is required.')
  }
  if (!rule.scenario || !rule.scenario.trim()) {
    errors.push('Business scenario is required.')
  }
  if (!rule.field_name || !rule.field_name.trim()) {
    errors.push('Field name is required.')
  }
  if (!rule.operator) {
    errors.push('Comparison operator is required.')
  }

  // Operator specific validation
  const op = rule.operator as ComparisonOperator
  if (op !== 'is_present' && op !== 'is_missing') {
    const hasThreshold =
      rule.threshold_value !== undefined &&
      rule.threshold_value !== null &&
      rule.threshold_value !== ''
    const hasCompareTo =
      rule.compare_to_field !== undefined &&
      rule.compare_to_field !== null &&
      rule.compare_to_field.trim() !== ''

    if (!hasThreshold && !hasCompareTo) {
      errors.push(`Operator '${op}' requires either a Threshold Value or a Compare To Field.`)
    }
  }

  if (!rule.recommended_action || !rule.recommended_action.trim()) {
    errors.push('Recommended action is required.')
  }

  return {
    isValid: errors.length === 0,
    errors,
  }
}
