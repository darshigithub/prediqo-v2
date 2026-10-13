import type {
  AIAnalyzeResponse,
  AISuggestionsResponse,
  AnalystResponse,
  ChartSpec,
  ChartSpecResponse,
  ConnectorCard,
  Dashboard,
  DatasetListItem,
  DatasetProfile,
  DatasetSummary,
  PreviewData,
  ProvidersResponse,
} from '../types'

const BASE = '/api'

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

// ---------- Ingestion Jobs ----------
export const startIngestionJobFile = (file: File): Promise<import('../types').IngestionJob> => {
  const form = new FormData()
  form.append('file', file)
  return request('/ingestion/jobs', { method: 'POST', body: form })
}

export const startIngestionJob = (payload: {
  source_type: string
  dataset_name?: string
  source_config: Record<string, unknown>
}): Promise<import('../types').IngestionJob> =>
  postJson('/ingestion/jobs', payload)

export const getIngestionJob = (jobId: string): Promise<import('../types').IngestionJob> =>
  request(`/ingestion/jobs/${jobId}`)

export const listIngestionJobs = (): Promise<{ jobs: import('../types').IngestionJob[] }> =>
  request('/ingestion/jobs')

export const refreshDataset = (id: string): Promise<import('../types').IngestionJob> =>
  postJson(`/datasets/${id}/refresh`, {})

// ---------- Connectors ----------
export const getConnectors = () =>
  request<{ connectors: ConnectorCard[] }>('/connectors')

export const connectCsv = (file: File): Promise<DatasetSummary> => {
  const form = new FormData()
  form.append('file', file)
  return request('/connect/csv', { method: 'POST', body: form })
}

export const connectExcel = (file: File): Promise<DatasetSummary> => {
  const form = new FormData()
  form.append('file', file)
  return request('/connect/excel', { method: 'POST', body: form })
}

export const connectGoogleSheets = (sheetId: string, sheetName?: string) =>
  postJson<DatasetSummary>('/connect/google-sheets', {
    sheet_id: sheetId,
    sheet_name: sheetName || null,
  })

export const connectPostgres = (cfg: {
  host: string
  port: number
  database: string
  user: string
  password: string
  table: string
}) => postJson<DatasetSummary>('/connect/postgresql', cfg)

// ---------- Datasets ----------
export const listDatasets = () =>
  request<{ datasets: DatasetListItem[] }>('/datasets')

export const getDataset = (id: string) =>
  request<Record<string, unknown>>(`/datasets/${id}`)

export interface PreviewOptions {
  page?: number
  page_size?: number
  limit?: number
  offset?: number
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  filter_col?: string
  filter_val?: string
}

export const getPreview = (id: string, optionsOrLimit: number | PreviewOptions = 50) => {
  if (typeof optionsOrLimit === 'number') {
    return request<PreviewData>(`/datasets/${id}/preview?limit=${optionsOrLimit}`)
  }
  const params = new URLSearchParams()
  if (optionsOrLimit.page !== undefined) params.set('page', String(optionsOrLimit.page))
  if (optionsOrLimit.page_size !== undefined) params.set('page_size', String(optionsOrLimit.page_size))
  if (optionsOrLimit.limit !== undefined) params.set('limit', String(optionsOrLimit.limit))
  if (optionsOrLimit.offset !== undefined) params.set('offset', String(optionsOrLimit.offset))
  if (optionsOrLimit.search) params.set('search', optionsOrLimit.search)
  if (optionsOrLimit.sort_by) params.set('sort_by', optionsOrLimit.sort_by)
  if (optionsOrLimit.sort_order) params.set('sort_order', optionsOrLimit.sort_order)
  if (optionsOrLimit.filter_col) params.set('filter_col', optionsOrLimit.filter_col)
  if (optionsOrLimit.filter_val !== undefined) params.set('filter_val', optionsOrLimit.filter_val)
  return request<PreviewData>(`/datasets/${id}/preview?${params.toString()}`)
}

export const getProfile = (id: string) =>
  request<{ dataset_id: string; profile: DatasetProfile }>(`/datasets/${id}/profile`)

export const getSchema = (id: string) =>
  request<{ dataset_id: string; columns: import('../types').ColumnMeta[] }>(
    `/datasets/${id}/schema`,
  )

export const getSemanticModel = (id: string) =>
  request<import('../types').SemanticModelResponse>(`/datasets/${id}/semantic-model`)

export const deleteDataset = (id: string) =>
  request<{ deleted: string }>(`/datasets/${id}`, { method: 'DELETE' })


// ---------- Query / Analyst / Charts ----------
export const getProviders = () =>
  request<ProvidersResponse>('/ai/providers')

export const askAIAnalyst = (
  datasetId: string,
  question: string,
  conversationId?: string,
  allowFallback?: boolean,
  provider?: string,
  model?: string,
) =>
  postJson<AIAnalyzeResponse>('/ai/analyze', {
    dataset_id: datasetId,
    question,
    conversation_id: conversationId,
    allow_fallback: allowFallback,
    provider,
    model,
  })

export const getAISuggestions = (datasetId: string) =>
  request<AISuggestionsResponse>(`/ai/suggestions/${datasetId}`)

export const askQuestion = (datasetId: string, question: string) =>
  postJson<AnalystResponse>('/query', { dataset_id: datasetId, question })

export const runChartSpec = (spec: ChartSpec) =>
  postJson<ChartSpecResponse>('/chart', spec)

// ---------- Dashboards ----------
export const getDefaultDashboard = () => request<Dashboard>('/default-dashboard')

export const getDashboards = () =>
  request<{ dashboards: { id: string; name: string; chart_count: number }[] }>('/dashboards')

export const createDashboard = (name: string) =>
  postJson<Dashboard>('/dashboards', { name })

export const addToDashboard = (dashboardId: string, payload: {
  dataset_id: string
  question?: string | null
  chart_spec?: ChartSpec | null
  result?: Record<string, unknown>[]
  chart_type?: string | null
  insight?: string | null
}) => postJson<Dashboard>(`/dashboards/${dashboardId}/charts`, payload)

export const removeChart = (dashboardId: string, chartId: string) =>
  request<Dashboard>(`/dashboards/${dashboardId}/charts/${chartId}`, { method: 'DELETE' })

export const moveChart = (dashboardId: string, chartId: string, direction: 'prev' | 'next') =>
  postJson<Dashboard>(`/dashboards/${dashboardId}/charts/${chartId}/move`, { direction })

export const saveDashboardConfig = (dash: Dashboard) =>
  postJson<Dashboard>(`/dashboards/${dash.id}/save`, { ...dash })

// ---------- Prediction Layer ----------
export const getPredictionFeasibility = (datasetId: string): Promise<import('../types').FeasibilityResponse> =>
  request(`/prediction/feasibility/${datasetId}`)

export const trainPredictionModel = (payload: {
  dataset_id: string
  target_column: string
  problem_type?: string
  features?: string[]
  test_size?: number
  random_state?: number
  validation_strategy?: string
  cv_folds?: number
  group_column?: string | null
}): Promise<import('../types').TrainResponse> =>
  postJson('/prediction/train', payload)

export const listPredictionModels = (datasetId: string, currentVersionOnly = false): Promise<{ models: import('../types').ModelListItem[] }> =>
  request(`/prediction/models/${datasetId}?current_version_only=${currentVersionOnly}`)

export const getPredictionModel = (modelId: string): Promise<import('../types').ModelMetadata> =>
  request(`/prediction/models/${modelId}`)

export const predictSingle = (modelId: string, features: Record<string, any>): Promise<import('../types').PredictResponse> =>
  postJson('/prediction/predict', { model_id: modelId, features })

// ---------- Forecasting Layer ----------
export const getForecastFeasibility = (datasetId: string): Promise<import('../types').ForecastFeasibilityResponse> =>
  request(`/forecast/feasibility/${datasetId}`)

export const trainForecastModel = (payload: {
  dataset_id: string
  date_column: string
  metric_column: string
  frequency?: string
  aggregation?: string
  horizon?: number
  group_column?: string | null
  imputation_method?: string | null
  non_negative?: boolean | null
}): Promise<import('../types').ForecastTrainResponse> =>
  postJson('/forecast/train', payload)

export const listForecastModels = (datasetId: string): Promise<{ models: import('../types').ForecastModelListItem[] }> =>
  request(`/forecast/models/${datasetId}`)

export const getForecastModel = (modelId: string): Promise<import('../types').ForecastModelMetadata> =>
  request(`/forecast/models/${modelId}/details`)

export const predictForecast = (payload: {
  model_id: string
  horizon?: number
}): Promise<{
  model_id: string
  dataset_id: string
  algorithm: string
  horizon: number
  frequency: string
  forecast_data: import('../types').ForecastPoint[]
  historical_end_date: string
  is_stale: boolean
  warnings: string[]
}> => postJson('/forecast/predict', payload)

// ---------- Capability Layer ----------
export const getDatasetCapabilities = (datasetId: string): Promise<import('../types').CapabilityAssessmentResponse> =>
  request(`/capabilities/${datasetId}`)

export const overrideDatasetCapabilities = (
  datasetId: string,
  mappings: Record<string, string>
): Promise<import('../types').CapabilityAssessmentResponse> =>
  postJson(`/capabilities/${datasetId}`, { mappings })

// ---------- Explainability (XAI) Layer ----------
export const getExplainabilityFeasibility = (
  modelId: string,
  modelType: 'prediction' | 'forecasting' = 'prediction'
): Promise<import('../types').ExplainabilityFeasibilityResponse> =>
  request(`/explainability/feasibility/${modelId}?model_type=${modelType}`)

export const getLocalExplanation = (payload: {
  model_id: string
  features: Record<string, any>
  target_class?: string | number | null
  method_preference?: string
}): Promise<import('../types').LocalExplanationResponse> =>
  postJson('/explainability/local', payload)

export const getGlobalExplanation = (
  modelId: string,
  maxSampleRows = 100
): Promise<import('../types').GlobalExplanationResponse> =>
  request(`/explainability/global/${modelId}?max_sample_rows=${maxSampleRows}`)

export const getForecastExplanation = (
  modelId: string
): Promise<import('../types').ForecastExplanationResponse> =>
  request(`/explainability/forecast/${modelId}`)

// ---------- AI Business Explanation Layer ----------
export const getAIExplanationStatus = (): Promise<import('../types').AIExplanationStatus> =>
  request('/ai/explain/status')

export const explainPredictionWithAI = (
  payload: import('../types').PredictionAIExplanationRequest
): Promise<import('../types').AIExplanationResponse> =>
  postJson('/ai/explain/prediction', payload)

export const explainForecastWithAI = (
  payload: import('../types').ForecastAIExplanationRequest
): Promise<import('../types').AIExplanationResponse> =>
  postJson('/ai/explain/forecast', payload)



