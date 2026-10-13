"""Pydantic data models for the AI-Powered Business Explanation Layer."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ContributionItem(BaseModel):
    """Local feature attribution item from validated XAI."""
    feature: str
    contribution: float
    raw_value: Optional[Any] = None


class PredictionEvidence(BaseModel):
    """Validated structured evidence for prediction explanation."""
    target_name: str
    problem_type: str = "regression"  # "regression" | "classification"
    unit: Optional[str] = None
    prediction: Any  # numeric point estimate or predicted class label
    probabilities: Optional[dict[str, float]] = None
    baseline_reference_value: Optional[float] = None
    decomposition_space: Optional[str] = "ORIGINAL_TARGET_SPACE"
    contributions: list[ContributionItem] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    data_quality: Optional[dict[str, Any]] = None


class ForecastEvidence(BaseModel):
    """Validated structured evidence for forecasting explanation."""
    metric_column: str
    date_column: Optional[str] = None
    frequency: str = "daily"  # "daily" | "weekly" | "monthly"
    horizon: int = 14
    aggregation: str = "SUM"
    unit: Optional[str] = None
    historical_summary: dict[str, Any] = Field(default_factory=dict)
    forecast_summary: dict[str, Any] = Field(default_factory=dict)
    backtest_metrics: dict[str, Any] = Field(default_factory=dict)
    intervals: Optional[dict[str, Any]] = None
    limitations: list[str] = Field(default_factory=list)


class PredictionExplanationRequest(BaseModel):
    """API request payload for generating a prediction business explanation."""
    model_id: Optional[str] = None
    dataset_id: Optional[str] = None
    target_name: str
    problem_type: str = "regression"
    unit: Optional[str] = None
    prediction: Any
    probabilities: Optional[dict[str, float]] = None
    baseline_reference_value: Optional[float] = None
    decomposition_space: Optional[str] = "ORIGINAL_TARGET_SPACE"
    contributions: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    data_quality: Optional[dict[str, Any]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    force_fallback: bool = False
    bypass_cache: bool = False


class ForecastExplanationRequest(BaseModel):
    """API request payload for generating a forecast business explanation."""
    model_id: Optional[str] = None
    dataset_id: Optional[str] = None
    metric_column: str
    date_column: Optional[str] = None
    frequency: str = "daily"
    horizon: int = 14
    aggregation: str = "SUM"
    unit: Optional[str] = None
    historical_summary: dict[str, Any] = Field(default_factory=dict)
    forecast_summary: dict[str, Any] = Field(default_factory=dict)
    backtest_metrics: dict[str, Any] = Field(default_factory=dict)
    intervals: Optional[dict[str, Any]] = None
    limitations: list[str] = Field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    force_fallback: bool = False
    bypass_cache: bool = False


class AIExplanationResponse(BaseModel):
    """Validated structured response from the Business Explanation Layer."""
    summary: str
    what_the_result_means: str
    supporting_evidence: list[str]
    evaluation_quality: str
    uncertainty_and_limitations: list[str]
    suggested_verifications: list[str]
    provider: str
    model: str
    generated_at: str
    is_fallback: bool = False
    cache_hit: bool = False
    evidence_fingerprint: str
    raw_evidence: Optional[dict[str, Any]] = None
