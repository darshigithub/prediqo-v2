"""Pydantic schemas and data transfer objects for Explainable AI (XAI)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field


class TransformedComponentItem(BaseModel):
    """Sub-feature contribution component (e.g. one-hot category or date extraction)."""
    name: str = ""
    component: str = ""
    contribution: float = 0.0
    value: Optional[Any] = None
    raw_value: Optional[Any] = None


class FeatureContributionItem(BaseModel):
    """Local attribution of an original input feature towards the prediction."""
    feature: str
    contribution: float
    feature_value: Optional[Any] = None
    raw_value: Optional[Any] = None
    direction: str = Field(
        ..., description="'POSITIVE' (increased output), 'NEGATIVE' (decreased output), or 'NEUTRAL'"
    )
    relative_weight_pct: float = Field(
        ..., description="Proportion of total absolute contribution magnitude across all features (0-100)"
    )
    transformed_components: Optional[list[TransformedComponentItem]] = None


class LocalExplanationRequest(BaseModel):
    """Request payload for local record-level explanation."""
    features: dict[str, Any]
    model_id: Optional[str] = None
    target_class: Optional[Any] = None
    method_preference: Optional[str] = "auto"


class LocalExplanationResponse(BaseModel):
    """Local attribution explanation for a single prediction."""
    model_id: str
    dataset_id: str
    dataset_version: int
    problem_type: str
    algorithm: str
    prediction: Any
    predicted_value: Optional[float] = None
    predicted_class: Optional[str] = None
    predicted_proba: Optional[float] = None
    target_class: Optional[Any] = None
    class_probabilities: Optional[dict[str, float]] = None

    # Reference value
    reference_value: float = Field(
        ..., description="Model baseline, background reference, or expected prior value"
    )
    baseline_reference_value: float = Field(
        ..., description="Model baseline, background reference, or expected prior value"
    )
    reference_definition: str = "Model expected prior or background sample baseline"

    # Scale & Space
    output_scale: str = Field(
        ..., description="'PREDICTION_SPACE' (direct units), 'LOG_ODDS_MARGIN', or 'PROBABILITY_SPACE'"
    )
    decomposition_space: str = Field(
        ..., description="'PREDICTION_SPACE', 'LOG_ODDS_MARGIN', or 'PROBABILITY_SPACE'"
    )
    explanation_method: str = Field(
        ..., description="'exact_tree_path', 'exact_linear', 'tree_shap', 'linear_shap', or 'baseline'"
    )

    # Feature Contributions
    feature_contributions: list[FeatureContributionItem] = Field(default_factory=list)
    contributions: list[FeatureContributionItem] = Field(default_factory=list)

    # Additive Reconstruction
    reconstruction_sum: float
    additive_sum: float
    reconstruction_error: float
    validation_status: str = Field(
        ..., description="'EXACT_ADDITIVE', 'APPROXIMATE', or 'UNSUPPORTED'"
    )
    is_valid: bool

    # Confidence Calibration & Disclosures
    is_calibrated: bool = False
    confidence_metric_name: str = "heuristic_score"
    probability_note: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class GroupedFeatureImportanceItem(BaseModel):
    """Global feature influence aggregated across original input columns."""
    feature: str
    importance: float = Field(..., description="Normalized global importance (0.0 to 1.0)")
    relative_share_pct: float = Field(..., description="Percentage share of global importance (0.0 to 100.0)")
    mean_abs_contribution: float
    mean_absolute_contribution: float
    correlated_with: Optional[list[str]] = None
    raw_components: Optional[list[str]] = None


class GlobalExplanationResponse(BaseModel):
    """Global explanation summarizing feature influence across a trained model."""
    model_id: str
    dataset_id: str
    dataset_version: int
    problem_type: str
    algorithm: str
    explanation_method: str
    sample_size: int
    sample_rows_evaluated: int
    features: list[GroupedFeatureImportanceItem] = Field(default_factory=list)
    feature_importances: list[GroupedFeatureImportanceItem] = Field(default_factory=list)
    correlated_features_warning: Optional[list[str]] = None
    correlation_warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ForecastExplanationResponse(BaseModel):
    """Explainability breakdown of a time-series forecast model."""
    model_id: str
    dataset_id: str
    dataset_version: int
    metric_column: str
    date_column: str
    frequency: str
    aggregation: str
    horizon: int
    algorithm: str
    selection_reason: str
    historical_trend: str
    trend_slope: Optional[float] = None
    trend_intercept: Optional[float] = None
    level_state: Optional[float] = None
    seasonal_cycle: Optional[int] = None
    recent_change_pct: Optional[float] = None
    recent_observation_reference: Optional[float] = None
    backtest_strategy: str
    evaluation_windows: int
    backtest_mae: float
    backtest_rmse: float
    vs_naive_pct: Optional[float] = None
    empirical_coverage_80: Optional[float] = None
    empirical_coverage_95: Optional[float] = None
    interval_notes: Optional[str] = None
    data_quality_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ExplainabilityFeasibilityResponse(BaseModel):
    """Summary of trained models eligible for explainability on a dataset."""
    dataset_id: str
    dataset_version: int
    model_id: Optional[str] = None
    model_type: Optional[str] = None
    algorithm: Optional[str] = None
    has_trained_models: bool = True
    prediction_models_count: int = 0
    forecast_models_count: int = 0
    prediction_models: list[dict[str, Any]] = Field(default_factory=list)
    forecast_models: list[dict[str, Any]] = Field(default_factory=list)
    supports_local_explanation: bool = True
    supports_global_explanation: bool = True
    is_exact_decomposition: bool = True
    preferred_explanation_method: str = "exact_decomposition"
    reason: str = "Trained model registered with exact decision-path or linear decomposition."
    limitations: list[str] = Field(default_factory=list)
