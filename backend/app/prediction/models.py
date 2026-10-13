"""Pydantic schemas and models for the Prediction Layer."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ColumnInfoItem(BaseModel):
    name: str
    display_name: str
    dtype: str
    semantic_type: str
    business_role: str
    unique_count: int = 0
    null_count: int = 0
    null_percentage: float = 0.0
    sample_values: Optional[list[Any]] = None
    unit: Optional[str] = None


class DataQualitySummary(BaseModel):
    total_rows: int = 0
    total_columns: int = 0
    complete_rows_pct: float = 100.0
    columns_with_nulls: int = 0
    quality_grade: str = "Good"  # "Excellent" | "Good" | "Needs Attention" | "Insufficient"
    quality_notes: list[str] = Field(default_factory=list)


class TargetCandidate(BaseModel):
    name: str
    dtype: str
    semantic_type: str
    business_role: str
    display_name: str
    problem_type: str  # "regression" | "classification"
    classes: Optional[list[str]] = None
    sample_values: Optional[list[Any]] = None
    null_count: Optional[int] = 0
    null_percentage: Optional[float] = 0.0
    unit: Optional[str] = None


class FeasibilityResponse(BaseModel):
    dataset_id: str
    dataset_version: int
    row_count: int
    prediction_possible: bool
    regression_targets: list[TargetCandidate] = Field(default_factory=list)
    classification_targets: list[TargetCandidate] = Field(default_factory=list)
    recommended_targets: list[str] = Field(default_factory=list)
    data_quality: Optional[DataQualitySummary] = None
    columns_info: list[ColumnInfoItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ActualVsPredictedPoint(BaseModel):
    actual: float
    predicted: float
    residual: float


class CandidateModelResult(BaseModel):
    algorithm: str
    metrics: dict[str, Any]
    cv_metrics: Optional[dict[str, Any]] = None
    training_time_ms: Optional[float] = None
    is_best: bool = False
    is_baseline: bool = False
    vs_baseline_pct: Optional[float] = None


class BestModelSummary(BaseModel):
    algorithm: str
    primary_metric: str
    primary_metric_value: float
    metrics: dict[str, Any]
    cv_metrics: Optional[dict[str, Any]] = None
    selection_rationale: Optional[str] = None
    vs_baseline_pct: Optional[float] = None
    confusion_matrix: Optional[list[list[int]]] = None
    class_labels: Optional[list[str]] = None
    per_class_metrics: Optional[dict[str, dict[str, float]]] = None
    is_reliable: bool = True
    reliability_notes: Optional[list[str]] = None


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float


class TrainRequest(BaseModel):
    dataset_id: str
    target_column: str
    problem_type: Optional[str] = None  # "regression" | "classification", inferred if None
    features: Optional[list[str]] = None  # recommended if None
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)
    random_state: int = 42
    cv_folds: int = Field(default=5, ge=2, le=10)
    validation_strategy: Optional[str] = "kfold"  # "kfold" | "time_aware" | "stratified_kfold" | "group_kfold"
    group_column: Optional[str] = None  # entity identifier for group-aware splitting


class TrainResponse(BaseModel):
    model_id: str
    dataset_id: str
    dataset_version: int
    target_column: str
    problem_type: str
    selected_features: list[str]
    best_model: BestModelSummary
    candidate_models: list[CandidateModelResult]
    training_row_count: int
    test_row_count: int
    validation_strategy: str = "kfold"
    cv_folds: int = 5
    actual_vs_predicted: list[ActualVsPredictedPoint] = []
    training_time_ms: Optional[float] = None
    feature_importance: list[FeatureImportanceItem] = []
    is_reliable: bool = True
    reliability_notes: list[str] = []
    class_distribution: Optional[dict[str, int]] = None
    confusion_matrix: Optional[list[list[int]]] = None
    class_labels: Optional[list[str]] = None
    per_class_metrics: Optional[dict[str, dict[str, float]]] = None
    baseline_algorithm: Optional[str] = None
    warnings: list[str] = []


class PredictRequest(BaseModel):
    model_id: str
    features: dict[str, Any]


class PredictResponse(BaseModel):
    model_id: str
    prediction: Any
    unit: Optional[str] = None
    problem_type: str
    probabilities: Optional[dict[str, float]] = None
    probability_note: Optional[str] = None
    explanation: str
    warnings: list[str] = []


class ModelListItem(BaseModel):
    model_id: str
    dataset_id: str
    dataset_version: int
    target_column: str
    problem_type: str
    algorithm: str
    primary_metric: str
    primary_metric_value: float
    created_at: str


class ModelMetadata(BaseModel):
    model_id: str
    dataset_id: str
    dataset_version: int
    target_column: str
    problem_type: str
    feature_columns: list[str]
    training_row_count: int
    test_row_count: int
    created_at: str
    algorithm: str
    primary_metric: str
    primary_metric_value: float
    preprocessing_description: str
    metrics: dict[str, Any]
    cv_metrics: Optional[dict[str, Any]] = None
    validation_strategy: Optional[str] = "kfold"
    cv_folds: Optional[int] = 5
    actual_vs_predicted: list[ActualVsPredictedPoint] = []
    candidate_models: list[CandidateModelResult] = []
    feature_importance: list[FeatureImportanceItem] = []
    is_reliable: bool = True
    reliability_notes: list[str] = []
    class_distribution: Optional[dict[str, int]] = None
    confusion_matrix: Optional[list[list[int]]] = None
    class_labels: Optional[list[str]] = None
    per_class_metrics: Optional[dict[str, dict[str, float]]] = None


