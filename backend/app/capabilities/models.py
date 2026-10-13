"""Pydantic schemas for dataset capability assessment and flexible schema mappings."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class CapabilityPredictionSummary(BaseModel):
    available: bool
    recommended_targets: list[str] = []
    regression_target_count: int = 0
    classification_target_count: int = 0
    warnings: list[str] = []


class CapabilityForecastingSummary(BaseModel):
    available: bool
    recommended_date_columns: list[str] = []
    recommended_metrics: list[str] = []
    available_frequencies: list[str] = ["daily", "weekly", "monthly"]
    is_stale: bool = False
    missing_requirements: list[str] = []
    warnings: list[str] = []


class GranularityReport(BaseModel):
    likely_granularity: str  # "transaction" | "order_item" | "daily_aggregated" | "generic_tabular"
    distinct_id_ratio: Optional[float] = None
    has_repeated_orders: bool = False
    aggregation_policy_note: str


class CapabilityAssessmentResponse(BaseModel):
    dataset_id: str
    dataset_version: int
    row_count: int
    granularity: GranularityReport
    capabilities: dict[str, Any]
    detected_mappings: dict[str, str] = {}
    mapping_confidences: dict[str, float] = {}
    warnings: list[str] = []
