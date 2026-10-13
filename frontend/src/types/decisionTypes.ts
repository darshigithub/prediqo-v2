/**
 * TypeScript types and schemas for the Prediqo Decision Layer MVP.
 */

export type DecisionPriority = 'critical' | 'high' | 'medium' | 'low' | 'informational'

export type RecommendationStatus =
  | 'needs_review'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'completed'
  | 'dismissed'

export type RuleEvaluationStatus = 'TRIGGERED' | 'NOT_TRIGGERED' | 'NOT_EVALUABLE'

export type ComparisonOperator =
  | 'eq'
  | 'neq'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'is_present'
  | 'is_missing'

export type EvidenceSourceType =
  | 'prediction'
  | 'forecast'
  | 'data_quality'
  | 'model_metric'
  | 'operational_fact'

export interface BusinessRule {
  rule_id: string
  name: string
  description: string
  scenario: string
  enabled: boolean
  priority: DecisionPriority
  evidence_source: EvidenceSourceType
  field_name: string
  operator: ComparisonOperator
  threshold_value?: any
  compare_to_field?: string | null
  expected_unit?: string | null
  recommended_action: string
  explanation_template: string
  requires_approval: boolean
  created_at: string
  updated_at: string
}

export interface RuleCreatePayload {
  name: string
  description: string
  scenario: string
  enabled: boolean
  priority: DecisionPriority
  evidence_source: EvidenceSourceType
  field_name: string
  operator: ComparisonOperator
  threshold_value?: any
  compare_to_field?: string | null
  expected_unit?: string | null
  recommended_action: string
  explanation_template: string
  requires_approval: boolean
}

export interface RuleValidationPayload {
  field_name: string
  operator: ComparisonOperator
  threshold_value?: any
  compare_to_field?: string | null
  expected_unit?: string | null
}

export interface RuleValidationResponse {
  is_valid: boolean
  message: string
  details?: Record<string, any> | null
}

export interface EvidenceItem {
  field_name: string
  source_type: EvidenceSourceType
  value: any
  unit?: string | null
  source_id?: string | null
  source_label?: string | null
  timestamp: string
}

export interface RuleEvaluationResult {
  rule_id: string
  rule_name: string
  status: RuleEvaluationStatus
  priority: DecisionPriority
  field_name: string
  operator: ComparisonOperator
  evaluated_value: any
  threshold_value: any
  evaluated_unit?: string | null
  threshold_unit?: string | null
  message: string
  recommended_action?: string | null
  requires_approval: boolean
  evidence_items: EvidenceItem[]
}

export interface Recommendation {
  recommendation_id: string
  evaluation_id: string
  scenario: string
  title: string
  recommended_action: string
  description: string
  priority: DecisionPriority
  status: RecommendationStatus
  triggered_rule_ids: string[]
  supporting_evidence: EvidenceItem[]
  missing_evidence: string[]
  uncertainty_notes: string[]
  requires_approval: boolean
  status_comment?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
}

export interface DecisionAuditItem {
  audit_id: string
  evaluation_id?: string | null
  recommendation_id?: string | null
  action: string
  previous_status?: string | null
  new_status?: string | null
  actor: string
  comment?: string | null
  timestamp: string
}

export interface EvaluationRequest {
  scenario: string
  dataset_id?: string | null
  prediction_model_id?: string | null
  prediction_inputs?: Record<string, any> | null
  forecast_model_id?: string | null
  operational_facts?: Record<string, any> | null
  rule_ids?: string[] | null
  actor?: string | null
}

export interface DecisionEvaluation {
  evaluation_id: string
  scenario: string
  dataset_id?: string | null
  prediction_model_id?: string | null
  forecast_model_id?: string | null
  operational_facts: Record<string, any>
  total_rules_evaluated: number
  triggered_rules_count: number
  not_triggered_rules_count: number
  not_evaluable_rules_count: number
  rule_results: RuleEvaluationResult[]
  recommendations: Recommendation[]
  missing_evidence: string[]
  created_at: string
}

export interface RecommendationStatusUpdate {
  new_status: RecommendationStatus
  comment?: string | null
  actor?: string | null
}

export interface DecisionOverviewStats {
  total_evaluations: number
  needs_review_count: number
  high_priority_count: number
  pending_approval_count: number
  eval_failures_count: number
  total_active_rules: number
  recent_evaluations: DecisionEvaluation[]
  recent_recommendations: Recommendation[]
}

export interface DecisionScenario {
  id: string
  name: string
  description: string
  relevant_fields: string[]
  default_units: string
}
