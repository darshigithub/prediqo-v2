export interface ColumnMeta {
  name: string
  dtype: string
  semantic_type: 'ID' | 'DIMENSION' | 'MEASURE' | 'DATE' | 'CATEGORY' | 'TEXT'
  unique_count: number
  null_count: number
  min?: number | null
  max?: number | null
  avg?: number | null
  top_values?: { value: string; count: number }[] | null
  business_role?: string
  display_name?: string
  allowed_aggregations?: string[]
}

export interface DerivedMetric {
  name: string
  display_name: string
  column: string
  aggregation: string
  business_role: string
  description?: string
}

export interface SemanticModelResponse {
  dataset_id: string
  dataset_name: string
  columns: ColumnMeta[]
  dimensions: string[]
  measures: string[]
  date_fields: string[]
  identifiers: string[]
  categories: string[]
  derived_metrics: DerivedMetric[]
}

export interface IngestionJob {
  job_id: string
  dataset_id: string
  dataset_name: string
  source_type: string
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  stage: 'QUEUED' | 'READING' | 'STANDARDIZING' | 'PROFILING' | 'SEMANTIC_ANALYSIS' | 'WRITING' | 'READY' | 'COMPLETED' | 'FAILED'
  progress: number
  started_at: string
  completed_at?: string | null
  error?: string | null
  row_count?: number | null
  processed_rows?: number | null
  version?: number
}

export interface DatasetSummary {
  dataset_id: string
  dataset_name: string
  source_type: string
  rows: number
  columns: number
  created_at?: string
  version?: number
  status?: string
}

export interface DatasetListItem {
  dataset_id: string
  dataset_name: string
  source_type: string
  created_at?: string
  updated_at?: string
  rows?: number
  columns?: number
  version?: number
  status?: string
  error?: string | null
}

export interface DatasetProfile {
  rows: number
  columns: number
  missing_values: number
  duplicate_rows: number
  numeric_columns: string[]
  categorical_columns: string[]
  date_columns: string[]
  column_stats: Record<string, {
    dtype: string
    semantic_type: string
    unique_count: number
    null_count: number
    min?: number | null
    max?: number | null
    avg?: number | null
    top_values?: { value: string; count: number }[] | null
  }>
}

export interface PreviewData {
  dataset_id: string
  total_rows: number
  page?: number
  page_size?: number
  total_pages?: number
  columns: string[]
  rows: Record<string, unknown>[]
}


export interface StructuredQuery {
  dataset_id: string
  operation: string
  group_by: string[]
  metric: string
  aggregation: string
  filters: { column: string; op: string; value: unknown }[]
  sort_by?: string | null
  sort_order: string
  top_n?: number | null
  time_grain?: string | null
}

export interface AnalystResponse {
  question: string
  query: StructuredQuery
  result: {
    data: Record<string, unknown>[]
    sql: string
    row_count: number
    metric: string
    dimension: string | null
  }
  chart_type: string
  chart_reason: string
  insight: string
  parser_used: string
}

export interface AIMetricSpec {
  column: string
  aggregation: string
  alias?: string
}

export interface AIFilterSpec {
  column: string
  operator: string
  value: unknown
}

export interface AISortSpec {
  column: string
  direction: string
}

export interface AIChartConfig {
  type: string
  x?: string | null
  y?: string | null
}

export interface AIQueryPlan {
  intent: string
  table: string
  dimensions: string[]
  metrics: AIMetricSpec[]
  filters: AIFilterSpec[]
  sort: AISortSpec[]
  limit?: number | null
  chart?: AIChartConfig | null
  explanation?: string | null
  time_grain?: string | null
}

export interface AIAnalyzeResponse {
  question: string
  query_plan: AIQueryPlan
  result: {
    columns: string[]
    rows: Record<string, unknown>[]
    row_count: number
    sql: string
    metric?: string | null
    dimension?: string | null
  }
  chart: {
    type: string
    x?: string | null
    y?: string | null
  }
  insight: string
  conversation_id: string
  parser_used: string
  provider?: string
  timing?: {
    llm_ms?: number
    validation_ms?: number
    duckdb_ms?: number
    serialization_ms?: number
    total_ms?: number
    cache_hit?: boolean
  }
  cache_hit?: boolean
}


export interface LLMProviderInfo {
  id: string
  name: string
  configured: boolean
  default_model: string
  models: string[]
}

export interface ProvidersResponse {
  providers: LLMProviderInfo[]
  active_provider: string
}

export interface AISuggestionsResponse {
  suggestions: string[]
}

export interface ChartSpec {
  dataset_id: string
  type: 'bar' | 'line' | 'pie' | 'area' | 'scatter' | 'kpi' | 'table' | 'auto'
  dimension: string | null
  metric: string | null
  aggregation: string
  filters: { column: string; op: string; value: unknown }[]
  sort: string
  top_n: number | null
  title?: string | null
}

export interface ChartSpecResponse {
  spec: ChartSpec
  result: {
    data: Record<string, unknown>[]
    sql: string
    row_count: number
    metric: string
    dimension: string | null
  }
  chart_type: string
  recommended_type: string
  insight: string
}

export interface DashboardChart {
  id: string
  title: string
  chart_type: string
  dataset_id?: string | null
  question?: string | null
  spec: Partial<ChartSpec>
  data: Record<string, unknown>[]
  insight?: string | null
}

export interface Dashboard {
  id: string
  name: string
  layout: DashboardChart[]
  created_at?: string | null
  updated_at?: string | null
}

export interface ConnectorCard {
  id: string
  label: string
  description: string
}

// ---------- Prediction Layer Types ----------
export interface TargetCandidate {
  name: string
  dtype: string
  semantic_type: string
  business_role: string
  display_name: string
  problem_type: 'regression' | 'classification'
  classes?: string[] | null
  sample_values?: any[] | null
}

export interface FeasibilityResponse {
  dataset_id: string
  dataset_version: number
  row_count: number
  prediction_possible: boolean
  regression_targets: TargetCandidate[]
  classification_targets: TargetCandidate[]
  recommended_targets: string[]
  warnings: string[]
}

export interface CandidateModelResult {
  algorithm: string
  metrics: Record<string, any>
  is_best: boolean
}

export interface BestModelSummary {
  algorithm: string
  primary_metric: string
  primary_metric_value: number
  metrics: Record<string, any>
}

export interface FeatureImportanceItem {
  feature: string
  importance: number
}

export interface TrainResponse {
  model_id: string
  dataset_id: string
  dataset_version: number
  target_column: string
  problem_type: 'regression' | 'classification'
  selected_features: string[]
  best_model: BestModelSummary
  candidate_models: CandidateModelResult[]
  training_row_count: number
  test_row_count: number
  feature_importance: FeatureImportanceItem[]
  warnings: string[]
}

export interface PredictResponse {
  model_id: string
  prediction: any
  unit?: string | null
  problem_type: string
  probabilities?: Record<string, number> | null
  explanation: string
  warnings: string[]
}

export interface ModelListItem {
  model_id: string
  dataset_id: string
  dataset_version: number
  target_column: string
  problem_type: string
  algorithm: string
  primary_metric: string
  primary_metric_value: number
  created_at: string
}

export interface ModelMetadata {
  model_id: string
  dataset_id: string
  dataset_version: number
  target_column: string
  problem_type: string
  feature_columns: string[]
  training_row_count: number
  test_row_count: number
  created_at: string
  algorithm: string
  primary_metric: string
  primary_metric_value: number
  preprocessing_description: string
  metrics: Record<string, any>
  candidate_models?: CandidateModelResult[]
  feature_importance?: FeatureImportanceItem[]
}

