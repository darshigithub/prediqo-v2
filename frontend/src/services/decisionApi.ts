/**
 * API client for the Prediqo Decision Layer MVP.
 */
import type {
  BusinessRule,
  DecisionAuditItem,
  DecisionEvaluation,
  DecisionOverviewStats,
  DecisionScenario,
  EvaluationRequest,
  Recommendation,
  RecommendationStatusUpdate,
  RuleCreatePayload,
  RuleValidationPayload,
  RuleValidationResponse,
} from '../types/decisionTypes'

const BASE = '/api/decisions'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

function putJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// ---------- Overview & Scenarios ----------

export const getDecisionOverview = (): Promise<DecisionOverviewStats> =>
  request<DecisionOverviewStats>('/overview')

export const listDecisionScenarios = (): Promise<DecisionScenario[]> =>
  request<DecisionScenario[]>('/scenarios')

// ---------- Rules Management ----------

export const listDecisionRules = (scenario?: string, enabledOnly: boolean = false): Promise<BusinessRule[]> => {
  const params = new URLSearchParams()
  if (scenario && scenario !== 'all') params.append('scenario', scenario)
  if (enabledOnly) params.append('enabled_only', 'true')
  const query = params.toString() ? `?${params.toString()}` : ''
  return request<BusinessRule[]>(`/rules${query}`)
}

export const getDecisionRule = (ruleId: string): Promise<BusinessRule> =>
  request<BusinessRule>(`/rules/${ruleId}`)

export const createDecisionRule = (payload: RuleCreatePayload): Promise<BusinessRule> =>
  postJson<BusinessRule>('/rules', payload)

export const updateDecisionRule = (ruleId: string, payload: RuleCreatePayload): Promise<BusinessRule> =>
  putJson<BusinessRule>(`/rules/${ruleId}`, payload)

export const toggleDecisionRule = (ruleId: string, enabled: boolean): Promise<BusinessRule> =>
  request<BusinessRule>(`/rules/${ruleId}/toggle?enabled=${enabled}`, { method: 'PATCH' })

export const deleteDecisionRule = (ruleId: string): Promise<{ status: string; message: string }> =>
  request<{ status: string; message: string }>(`/rules/${ruleId}`, { method: 'DELETE' })

export const validateDecisionRule = (payload: RuleValidationPayload): Promise<RuleValidationResponse> =>
  postJson<RuleValidationResponse>('/rules/validate', payload)

// ---------- Decision Evaluations ----------

export const evaluateDecisionScenario = (payload: EvaluationRequest): Promise<DecisionEvaluation> =>
  postJson<DecisionEvaluation>('/evaluate', payload)

export const listDecisionEvaluations = (limit: number = 50): Promise<DecisionEvaluation[]> =>
  request<DecisionEvaluation[]>(`/evaluations?limit=${limit}`)

export const getDecisionEvaluation = (evalId: string): Promise<DecisionEvaluation> =>
  request<DecisionEvaluation>(`/evaluations/${evalId}`)

// ---------- Recommendations Management ----------

export const listRecommendations = (
  status?: string,
  priority?: string,
  evaluationId?: string,
  limit: number = 100
): Promise<Recommendation[]> => {
  const params = new URLSearchParams()
  if (status && status !== 'all') params.append('status', status)
  if (priority && priority !== 'all') params.append('priority', priority)
  if (evaluationId) params.append('evaluation_id', evaluationId)
  params.append('limit', String(limit))
  return request<Recommendation[]>(`/recommendations?${params.toString()}`)
}

export const getRecommendation = (recId: string): Promise<Recommendation> =>
  request<Recommendation>(`/recommendations/${recId}`)

export const updateRecommendationStatus = (
  recId: string,
  payload: RecommendationStatusUpdate
): Promise<Recommendation> =>
  postJson<Recommendation>(`/recommendations/${recId}/status`, payload)

// ---------- Audit History ----------

export const listDecisionAuditTrail = (limit: number = 100): Promise<DecisionAuditItem[]> =>
  request<DecisionAuditItem[]>(`/audit?limit=${limit}`)

// Convenient aliases
export const evaluateDecision = evaluateDecisionScenario
export const listDecisionRecommendations = listRecommendations
export const getDecisionAuditLog = listDecisionAuditTrail
