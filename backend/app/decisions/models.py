"""Pydantic schemas and models for the Prediqo Decision Layer MVP."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DecisionPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RecommendationStatus(str, Enum):
    NEEDS_REVIEW = "needs_review"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class RuleEvaluationStatus(str, Enum):
    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class ComparisonOperator(str, Enum):
    EQ = "eq"              # Equal to
    NEQ = "neq"            # Not equal to
    GT = "gt"              # Greater than
    GTE = "gte"            # Greater than or equal to
    LT = "lt"              # Less than
    LTE = "lte"            # Less than or equal to
    IS_PRESENT = "is_present"  # Value is provided / not null
    IS_MISSING = "is_missing"  # Value is missing / null


class EvidenceSourceType(str, Enum):
    PREDICTION = "prediction"
    FORECAST = "forecast"
    DATA_QUALITY = "data_quality"
    MODEL_METRIC = "model_metric"
    OPERATIONAL_FACT = "operational_fact"


class BusinessRule(BaseModel):
    rule_id: str
    name: str
    description: str
    scenario: str = "general"     # "inventory", "demand", "churn", "data_quality", "general", etc.
    enabled: bool = True
    priority: DecisionPriority = DecisionPriority.MEDIUM
    evidence_source: EvidenceSourceType = EvidenceSourceType.OPERATIONAL_FACT
    field_name: str               # e.g., "predicted_demand", "available_inventory", "data_completeness_pct"
    operator: ComparisonOperator
    threshold_value: Optional[Any] = None  # Static literal (e.g., 500, "active", 95.0)
    compare_to_field: Optional[str] = None  # Dynamic comparison against another field (e.g., "available_inventory")
    expected_unit: Optional[str] = None    # e.g., "units", "$", "%", "days"
    recommended_action: str
    explanation_template: str
    requires_approval: bool = True
    created_at: str
    updated_at: str


class RuleCreatePayload(BaseModel):
    name: str
    description: str
    scenario: str = "general"
    enabled: bool = True
    priority: DecisionPriority = DecisionPriority.MEDIUM
    evidence_source: EvidenceSourceType = EvidenceSourceType.OPERATIONAL_FACT
    field_name: str
    operator: ComparisonOperator
    threshold_value: Optional[Any] = None
    compare_to_field: Optional[str] = None
    expected_unit: Optional[str] = None
    recommended_action: str
    explanation_template: str
    requires_approval: bool = True


class RuleValidationPayload(BaseModel):
    field_name: str
    operator: ComparisonOperator
    threshold_value: Optional[Any] = None
    compare_to_field: Optional[str] = None
    expected_unit: Optional[str] = None


class RuleValidationResponse(BaseModel):
    is_valid: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class EvidenceItem(BaseModel):
    field_name: str
    source_type: EvidenceSourceType
    value: Any
    unit: Optional[str] = None
    source_id: Optional[str] = None         # model_id, fc_id, dataset_id, or "user_input"
    source_label: Optional[str] = None
    timestamp: str


class RuleEvaluationResult(BaseModel):
    rule_id: str
    rule_name: str
    status: RuleEvaluationStatus
    priority: DecisionPriority
    field_name: str
    operator: ComparisonOperator
    evaluated_value: Any
    threshold_value: Any
    evaluated_unit: Optional[str] = None
    threshold_unit: Optional[str] = None
    message: str
    recommended_action: Optional[str] = None
    requires_approval: bool = True
    evidence_items: List[EvidenceItem] = Field(default_factory=list)


class Recommendation(BaseModel):
    recommendation_id: str
    evaluation_id: str
    scenario: str
    title: str
    recommended_action: str
    description: str
    priority: DecisionPriority
    status: RecommendationStatus = RecommendationStatus.NEEDS_REVIEW
    triggered_rule_ids: List[str] = Field(default_factory=list)
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    requires_approval: bool = True
    status_comment: Optional[str] = None
    updated_by: Optional[str] = "local_user"
    created_at: str
    updated_at: str


class DecisionAuditItem(BaseModel):
    audit_id: str
    evaluation_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    action: str                            # "EVALUATION_CREATED", "STATUS_CHANGED", "RULE_TOGGLED", etc.
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    actor: str = "local_user"
    comment: Optional[str] = None
    timestamp: str


class EvaluationRequest(BaseModel):
    scenario: str                          # e.g., "inventory", "demand", "churn", "general"
    dataset_id: Optional[str] = None
    prediction_model_id: Optional[str] = None
    prediction_inputs: Optional[Dict[str, Any]] = None
    forecast_model_id: Optional[str] = None
    operational_facts: Optional[Dict[str, Any]] = Field(default_factory=dict)
    rule_ids: Optional[List[str]] = None   # None means evaluate all enabled rules for scenario
    actor: Optional[str] = "local_user"


class DecisionEvaluation(BaseModel):
    evaluation_id: str
    scenario: str
    dataset_id: Optional[str] = None
    prediction_model_id: Optional[str] = None
    forecast_model_id: Optional[str] = None
    operational_facts: Dict[str, Any] = Field(default_factory=dict)
    total_rules_evaluated: int = 0
    triggered_rules_count: int = 0
    not_triggered_rules_count: int = 0
    not_evaluable_rules_count: int = 0
    rule_results: List[RuleEvaluationResult] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    created_at: str


class RecommendationStatusUpdate(BaseModel):
    new_status: RecommendationStatus
    comment: Optional[str] = None
    actor: Optional[str] = "local_user"


class DecisionOverviewStats(BaseModel):
    total_evaluations: int = 0
    needs_review_count: int = 0
    high_priority_count: int = 0
    pending_approval_count: int = 0
    eval_failures_count: int = 0
    total_active_rules: int = 0
    recent_evaluations: List[DecisionEvaluation] = Field(default_factory=list)
    recent_recommendations: List[Recommendation] = Field(default_factory=list)
