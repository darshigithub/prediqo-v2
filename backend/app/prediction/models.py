"""Pydantic schemas and models for the Prediction Layer."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class TargetCandidate(BaseModel):
    name: str
    dtype: str
    semantic_type: str
    business_role: str
    display_name: str
    problem_type: str  # "regression" | "classification"
    classes: Optional[list[str]] = None
    sample_values: Optional[list[Any]] = None


class FeasibilityResponse(BaseModel):
    dataset_id: str
    dataset_version: int
    row_count: int
    prediction_possible: bool
    regression_targets: list[TargetCandidate] = []
    classification_targets: list[TargetCandidate] = []
    recommended_targets: list[str] = []
    warnings: list[str] = []


class TrainRequest(BaseModel):
    dataset_id: str
    target_column: str
    problem_type: Optional[str] = None  # "regression" | "classification", inferred if None
    features: Optional[list[str]] = None  # recommended if None
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)
    random_state: int = 42


class CandidateModelResult(BaseModel):
    algorithm: str
    metrics: dict[str, Any]
    is_best: bool = False


class BestModelSummary(BaseModel):
    algorithm: str
    primary_metric: str
    primary_metric_value: float
    metrics: dict[str, Any]


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float


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
    feature_importance: list[FeatureImportanceItem] = []
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
    candidate_models: list[CandidateModelResult] = []
    feature_importance: list[FeatureImportanceItem] = []
