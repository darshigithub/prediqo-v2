"""Pydantic schemas and data models for Time-Series Forecasting."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from ..prediction.models import ColumnInfoItem, DataQualitySummary


class ForecastCandidateDate(BaseModel):
    name: str
    display_name: str
    dtype: str
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    distinct_dates: int = 0


class ForecastCandidateMetric(BaseModel):
    name: str
    display_name: str
    dtype: str
    business_role: str
    recommended_aggregation: str = "SUM"
    allowed_aggregations: list[str] = Field(default_factory=lambda: ["SUM", "AVG", "COUNT", "DISTINCT_COUNT"])
    unit: Optional[str] = None
    null_count: Optional[int] = 0
    null_percentage: Optional[float] = 0.0


class ForecastFeasibilityResponse(BaseModel):
    dataset_id: str
    dataset_version: int
    row_count: int
    forecasting_possible: bool
    recommended_date_columns: list[ForecastCandidateDate] = Field(default_factory=list)
    recommended_metrics: list[ForecastCandidateMetric] = Field(default_factory=list)
    available_frequencies: list[str] = Field(default_factory=lambda: ["daily", "weekly", "monthly"])
    data_start_date: Optional[str] = None
    data_end_date: Optional[str] = None
    distinct_periods_estimate: int = 0
    is_stale: bool = False
    stale_warning: Optional[str] = None
    data_quality: Optional[DataQualitySummary] = None
    columns_info: list[ColumnInfoItem] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ForecastTrainRequest(BaseModel):
    dataset_id: str
    date_column: str
    metric_column: str
    frequency: str = "daily"  # "daily" | "weekly" | "monthly"
    aggregation: str = "SUM"  # "SUM" | "AVG" | "COUNT" | "DISTINCT_COUNT"
    horizon: int = Field(default=14, ge=1, le=120)
    backtest_periods: Optional[int] = None
    group_column: Optional[str] = None
    imputation_method: Optional[str] = None  # "zero" | "ffill" | "bfill" | "interpolate"
    non_negative: Optional[bool] = None  # auto-detected if None
    backtest_strategy: Optional[str] = "rolling_origin"  # "rolling_origin" | "single_cutoff"


class HistoricalPoint(BaseModel):
    date: str
    value: float


class BacktestPoint(BaseModel):
    date: str
    actual: float
    predicted: float
    residual: float


class ForecastPoint(BaseModel):
    date: str
    forecast: float
    lower_80: Optional[float] = None
    upper_80: Optional[float] = None
    lower_95: Optional[float] = None
    upper_95: Optional[float] = None


class CandidateForecastModelResult(BaseModel):
    algorithm: str
    metrics: dict[str, Any]
    vs_naive_pct: Optional[float] = None
    is_best: bool = False
    is_baseline: bool = False
    training_time_ms: Optional[float] = None


class BestForecastModelSummary(BaseModel):
    algorithm: str
    primary_metric: str = "mae"
    primary_metric_value: float
    metrics: dict[str, Any]
    vs_naive_pct: Optional[float] = None
    selection_reason: str
    evaluation_windows: int = 1
    backtest_strategy: str = "single_cutoff"
    empirical_coverage_80: Optional[float] = None
    empirical_coverage_95: Optional[float] = None
    coverage_sample_size: int = 0
    interval_notes: Optional[str] = None


class ForecastTrainResponse(BaseModel):
    model_id: str
    dataset_id: str
    dataset_version: int
    date_column: str
    metric_column: str
    frequency: str
    aggregation: str
    horizon: int
    historical_start_date: str
    historical_end_date: str
    total_historical_periods: int
    is_stale: bool = False
    stale_warning: Optional[str] = None
    best_model: BestForecastModelSummary
    candidate_models: list[CandidateForecastModelResult]
    historical_data: list[HistoricalPoint] = []
    backtest_data: list[BacktestPoint] = []
    forecast_data: list[ForecastPoint] = []
    evaluation_windows: int = 1
    backtest_strategy: str = "single_cutoff"
    empirical_coverage_80: Optional[float] = None
    empirical_coverage_95: Optional[float] = None
    coverage_sample_size: int = 0
    interval_notes: Optional[str] = None
    warnings: list[str] = []


class ForecastPredictRequest(BaseModel):
    model_id: str
    horizon: Optional[int] = None


class ForecastPredictResponse(BaseModel):
    model_id: str
    dataset_id: str
    algorithm: str
    horizon: int
    frequency: str
    forecast_data: list[ForecastPoint]
    historical_end_date: str
    is_stale: bool = False
    warnings: list[str] = []


class ForecastModelListItem(BaseModel):
    model_id: str
    dataset_id: str
    dataset_version: int
    date_column: str
    metric_column: str
    frequency: str
    aggregation: str
    algorithm: str
    mae: float
    created_at: str


class ForecastModelMetadata(BaseModel):
    model_id: str
    dataset_id: str
    dataset_version: int
    date_column: str
    metric_column: str
    frequency: str
    aggregation: str
    horizon: int
    created_at: str
    historical_start_date: str
    historical_end_date: str
    total_historical_periods: int
    algorithm: str
    primary_metric: str
    primary_metric_value: float
    metrics: dict[str, Any]
    candidate_models: list[CandidateForecastModelResult] = []
    model_params: dict[str, Any] = {}
    evaluation_windows: Optional[int] = 1
    backtest_strategy: Optional[str] = "single_cutoff"
    empirical_coverage_80: Optional[float] = None
    empirical_coverage_95: Optional[float] = None
    coverage_sample_size: Optional[int] = 0
    interval_notes: Optional[str] = None

