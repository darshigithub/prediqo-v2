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
export interface ColumnInfoItem {
  name: string
  display_name: string
  dtype: string
  semantic_type: string
  business_role: string
  unique_count: number
  null_count: number
  null_percentage: number
  sample_values?: any[] | null
  unit?: string | null
}

export interface DataQualitySummary {
  total_rows: number
  total_columns: number
  complete_rows_pct: number
  columns_with_nulls: number
  quality_grade: 'Excellent' | 'Good' | 'Needs Attention' | 'Insufficient' | string
  quality_notes: string[]
}

export interface TargetCandidate {
  name: string
  dtype: string
  semantic_type: string
  business_role: string
  display_name: string
  problem_type: 'regression' | 'classification'
  classes?: string[] | null
  sample_values?: any[] | null
  null_count?: number | null
  null_percentage?: number | null
  unit?: string | null
}

export interface FeasibilityResponse {
  dataset_id: string
  dataset_version: number
  row_count: number
  prediction_possible: boolean
  regression_targets: TargetCandidate[]
  classification_targets: TargetCandidate[]
  recommended_targets: string[]
  data_quality?: DataQualitySummary | null
  columns_info?: ColumnInfoItem[]
  warnings: string[]
}

export interface ActualVsPredictedPoint {
  actual: number
  predicted: number
  residual: number
}

export interface CandidateModelResult {
  algorithm: string
  metrics: Record<string, any>
  cv_metrics?: Record<string, any> | null
  training_time_ms?: number | null
  is_best: boolean
  is_baseline?: boolean
  vs_baseline_pct?: number | null
}

export interface BestModelSummary {
  algorithm: string
  primary_metric: string
  primary_metric_value: number
  metrics: Record<string, any>
  cv_metrics?: Record<string, any> | null
  selection_rationale?: string | null
  vs_baseline_pct?: number | null
  confusion_matrix?: number[][] | null
  class_labels?: string[] | null
  per_class_metrics?: Record<string, { precision: number; recall: number; f1: number; support?: number }> | null
  is_reliable?: boolean
  reliability_notes?: string[] | null
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
  validation_strategy?: string
  cv_folds?: number
  actual_vs_predicted?: ActualVsPredictedPoint[]
  training_time_ms?: number | null
  feature_importance: FeatureImportanceItem[]
  is_reliable?: boolean
  reliability_notes?: string[]
  class_distribution?: Record<string, number> | null
  confusion_matrix?: number[][] | null
  class_labels?: string[] | null
  per_class_metrics?: Record<string, { precision: number; recall: number; f1: number; support?: number }> | null
  baseline_algorithm?: string | null
  warnings: string[]
}

export interface PredictResponse {
  model_id: string
  prediction: any
  unit?: string | null
  problem_type: string
  probabilities?: Record<string, number> | null
  probability_note?: string | null
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
  cv_metrics?: Record<string, any> | null
  validation_strategy?: string
  cv_folds?: number
  actual_vs_predicted?: ActualVsPredictedPoint[]
  candidate_models?: CandidateModelResult[]
  feature_importance?: FeatureImportanceItem[]
}

// ---------- Forecasting Layer Types ----------
export interface ForecastCandidateDate {
  name: string
  display_name: string
  dtype: string
  min_date?: string | null
  max_date?: string | null
  distinct_dates: number
}

export interface ForecastCandidateMetric {
  name: string
  display_name: string
  dtype: string
  business_role: string
  recommended_aggregation: string
  allowed_aggregations: string[]
  unit?: string | null
  null_count?: number | null
  null_percentage?: number | null
}

export interface ForecastFeasibilityResponse {
  dataset_id: string
  dataset_version: number
  row_count: number
  forecasting_possible: boolean
  recommended_date_columns: ForecastCandidateDate[]
  recommended_metrics: ForecastCandidateMetric[]
  available_frequencies: string[]
  data_start_date?: string | null
  data_end_date?: string | null
  distinct_periods_estimate: number
  is_stale: boolean
  stale_warning?: string | null
  data_quality?: DataQualitySummary | null
  columns_info?: ColumnInfoItem[]
  missing_requirements: string[]
  warnings: string[]
}

export interface HistoricalPoint {
  date: string
  value: number
}

export interface BacktestPoint {
  date: string
  actual: number
  predicted: number
  residual: number
}

export interface ForecastPoint {
  date: string
  forecast: number
  lower_80?: number | null
  upper_80?: number | null
  lower_95?: number | null
  upper_95?: number | null
}

export interface CandidateForecastModelResult {
  algorithm: string
  metrics: Record<string, any>
  vs_naive_pct?: number | null
  is_best: boolean
  is_baseline: boolean
  training_time_ms?: number | null
}

export interface BestForecastModelSummary {
  algorithm: string
  primary_metric: string
  primary_metric_value: number
  metrics: Record<string, any>
  vs_naive_pct?: number | null
  selection_reason: string
  evaluation_windows?: number
  backtest_strategy?: string
  empirical_coverage_80?: number | null
  empirical_coverage_95?: number | null
  coverage_sample_size?: number
  interval_notes?: string | null
}

export interface ForecastTrainResponse {
  model_id: string
  dataset_id: string
  dataset_version: number
  date_column: string
  metric_column: string
  frequency: string
  aggregation: string
  horizon: number
  historical_start_date: string
  historical_end_date: string
  total_historical_periods: number
  is_stale: boolean
  stale_warning?: string | null
  best_model: BestForecastModelSummary
  candidate_models: CandidateForecastModelResult[]
  historical_data: HistoricalPoint[]
  backtest_data: BacktestPoint[]
  forecast_data: ForecastPoint[]
  evaluation_windows?: number
  backtest_strategy?: string
  empirical_coverage_80?: number | null
  empirical_coverage_95?: number | null
  coverage_sample_size?: number
  interval_notes?: string | null
  warnings: string[]
}


export interface ForecastModelListItem {
  model_id: string
  dataset_id: string
  dataset_version: number
  date_column: string
  metric_column: string
  frequency: string
  aggregation: string
  algorithm: string
  mae: number
  created_at: string
}

export interface ForecastModelMetadata {
  model_id: string
  dataset_id: string
  dataset_version: number
  date_column: string
  metric_column: string
  frequency: string
  aggregation: string
  horizon: number
  created_at: string
  historical_start_date: string
  historical_end_date: string
  total_historical_periods: number
  algorithm: string
  primary_metric: string
  primary_metric_value: number
  metrics: Record<string, any>
  candidate_models?: CandidateForecastModelResult[]
  model_params?: Record<string, any>
}

export interface CapabilityAssessmentResponse {
  dataset_id: string
  dataset_version: number
  row_count: number
  granularity: {
    likely_granularity: string
    distinct_id_ratio?: number | null
    has_repeated_orders: boolean
    aggregation_policy_note: string
  }
  capabilities: {
    prediction: {
      available: boolean
      recommended_targets: string[]
      regression_target_count: number
      classification_target_count: number
      warnings: string[]
    }
    forecasting: {
      available: boolean
      recommended_date_columns: string[]
      recommended_metrics: string[]
      available_frequencies: string[]
      is_stale: boolean
      missing_requirements: string[]
      warnings: string[]
    }
  }
  detected_mappings: Record<string, string>
  mapping_confidences: Record<string, number>
  warnings: string[]
}

// ---------- Explainability (XAI) Layer ----------
export interface FeatureContributionItem {
  feature: string
  raw_value: any
  contribution: number
  direction: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
  relative_weight_pct: number
  transformed_components?: Array<{
    name: string
    value: any
    contribution: number
  }>
}

export interface LocalExplanationResponse {
  model_id: string
  dataset_id: string
  dataset_version: number
  problem_type: string
  algorithm: string
  predicted_value?: number | null
  predicted_class?: string | number | null
  predicted_proba?: number | null
  target_class?: string | number | null
  baseline_reference_value: number
  reference_definition: string
  decomposition_space: string
  contributions: FeatureContributionItem[]
  additive_sum: number
  reconstruction_error: number
  validation_status: 'EXACT_ADDITIVE' | 'APPROXIMATE' | 'UNSUPPORTED'
  explanation_method: string
  is_calibrated: boolean
  confidence_metric_name: string
  warnings: string[]
  limitations: string[]
  generated_at: string
}

export interface GroupedFeatureImportanceItem {
  feature: string
  mean_absolute_contribution: number
  relative_share_pct: number
  correlated_with?: string[]
}

export interface GlobalExplanationResponse {
  model_id: string
  dataset_id: string
  dataset_version: number
  problem_type: string
  algorithm: string
  explanation_method: string
  sample_rows_evaluated: number
  feature_importances: GroupedFeatureImportanceItem[]
  correlation_warnings: string[]
  limitations: string[]
  generated_at: string
}

export interface ForecastExplanationResponse {
  model_id: string
  dataset_id: string
  dataset_version: number
  metric_column: string
  date_column: string
  frequency: string
  aggregation: string
  horizon: number
  algorithm: string
  selection_reason: string
  historical_trend: string
  trend_slope?: number | null
  trend_intercept?: number | null
  level_state?: number | null
  seasonal_cycle?: number | null
  recent_change_pct?: number | null
  recent_observation_reference?: number | null
  backtest_strategy?: string | null
  evaluation_windows?: number | null
  backtest_mae?: number | null
  backtest_rmse?: number | null
  vs_naive_pct?: number | null
  empirical_coverage_80?: number | null
  empirical_coverage_95?: number | null
  interval_notes?: string | null
  data_quality_notes: string[]
  limitations: string[]
  generated_at: string
}

export interface ExplainabilityFeasibilityResponse {
  model_id: string
  model_type: 'prediction' | 'forecasting'
  dataset_id: string
  dataset_version: number
  algorithm: string
  supports_local_explanation: boolean
  supports_global_explanation: boolean
  preferred_explanation_method: string
  is_exact_decomposition: boolean
  reason: string
  limitations: string[]
}

// ---------------------------------------------------------------------------
// AI-Powered Business Explanation Layer Types
// ---------------------------------------------------------------------------

export interface AIExplanationResponse {
  summary: string
  what_the_result_means: string
  supporting_evidence: string[]
  evaluation_quality: string
  uncertainty_and_limitations: string[]
  suggested_verifications: string[]
  provider: string
  model: string
  generated_at: string
  is_fallback: boolean
  cache_hit: boolean
  evidence_fingerprint: string
  raw_evidence?: Record<string, any>
}

export interface PredictionAIExplanationRequest {
  model_id?: string
  dataset_id?: string
  target_name: string
  problem_type?: string
  unit?: string | null
  prediction: any
  probabilities?: Record<string, number> | null
  baseline_reference_value?: number | null
  decomposition_space?: string
  contributions?: Array<{ feature: string; contribution: number; raw_value?: any }>
  metrics?: Record<string, any>
  model_metadata?: Record<string, any>
  data_quality?: Record<string, any> | null
  provider?: string
  model?: string
  force_fallback?: boolean
  bypass_cache?: boolean
}

export interface ForecastAIExplanationRequest {
  model_id?: string
  dataset_id?: string
  metric_column: string
  date_column?: string | null
  frequency?: string
  horizon?: number
  aggregation?: string
  unit?: string | null
  historical_summary?: Record<string, any>
  forecast_summary?: Record<string, any>
  backtest_metrics?: Record<string, any>
  intervals?: Record<string, any> | null
  limitations?: string[]
  provider?: string
  model?: string
  force_fallback?: boolean
  bypass_cache?: boolean
}

export interface AIProviderInfo {
  provider_id: string
  display_name: string
  available: boolean
  default_model: string
  base_url?: string
}

export interface AIExplanationStatus {
  cached_explanations_count: number
  providers: AIProviderInfo[]
  prompt_version: string
}



