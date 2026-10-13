"""Persistence layer for rules, decision evaluations, recommendations, and audit logs.
Uses local JSON files in `data/decisions/` ensuring all records survive application restarts.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import DATA_DIR
from .models import (
    BusinessRule,
    ComparisonOperator,
    DecisionAuditItem,
    DecisionEvaluation,
    DecisionOverviewStats,
    DecisionPriority,
    EvidenceSourceType,
    Recommendation,
    RecommendationStatus,
    RuleEvaluationStatus,
)

logger = logging.getLogger(__name__)

DECISIONS_DIR = DATA_DIR / "decisions"
RULES_FILE = DECISIONS_DIR / "rules.json"
EVALUATIONS_DIR = DECISIONS_DIR / "evaluations"
RECOMMENDATIONS_DIR = DECISIONS_DIR / "recommendations"
AUDIT_FILE = DECISIONS_DIR / "audit_log.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_directories():
    """Initializes decisions directories and seed rules if not present."""
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    RECOMMENDATIONS_DIR.mkdir(parents=True, exist_ok=True)

    if not RULES_FILE.exists():
        _init_seed_rules()

    if not AUDIT_FILE.exists():
        AUDIT_FILE.write_text("[]")


def _init_seed_rules():
    """Initializes standard template business rules across common scenarios."""
    ts = _now()
    seed_rules: List[BusinessRule] = [
        BusinessRule(
            rule_id="rule_inv_stockout",
            name="Potential Inventory Stockout Alert",
            description="Triggers when predicted future demand exceeds currently available stock.",
            scenario="inventory",
            enabled=True,
            priority=DecisionPriority.HIGH,
            evidence_source=EvidenceSourceType.FORECAST,
            field_name="predicted_demand",
            operator=ComparisonOperator.GT,
            threshold_value=None,
            compare_to_field="available_inventory",
            expected_unit="units",
            recommended_action="Review inventory replenishment immediately to prevent potential stockouts.",
            explanation_template="Predicted demand ({value}) exceeds available inventory ({threshold}).",
            requires_approval=True,
            created_at=ts,
            updated_at=ts,
        ),
        BusinessRule(
            rule_id="rule_inv_excess",
            name="Excess Inventory Holding Alert",
            description="Triggers when available stock exceeds maximum recommended warehouse capacity.",
            scenario="inventory",
            enabled=True,
            priority=DecisionPriority.MEDIUM,
            evidence_source=EvidenceSourceType.OPERATIONAL_FACT,
            field_name="available_inventory",
            operator=ComparisonOperator.GT,
            threshold_value=None,
            compare_to_field="max_inventory_capacity",
            expected_unit="units",
            recommended_action="Review inventory holding costs and defer replenishment orders to prevent overstocking.",
            explanation_template="Available stock ({value}) exceeds warehouse capacity threshold ({threshold}).",
            requires_approval=False,
            created_at=ts,
            updated_at=ts,
        ),
        BusinessRule(
            rule_id="rule_dq_completeness",
            name="Data Quality Completeness Warning",
            description="Triggers when dataset row completeness drops below 85%.",
            scenario="data_quality",
            enabled=True,
            priority=DecisionPriority.HIGH,
            evidence_source=EvidenceSourceType.DATA_QUALITY,
            field_name="data_completeness_pct",
            operator=ComparisonOperator.LT,
            threshold_value=85.0,
            compare_to_field=None,
            expected_unit="%",
            recommended_action="Audit source data pipelines and inspect missing values before relying on predictive outputs.",
            explanation_template="Dataset completeness is {value}, which is below the safe threshold of {threshold}.",
            requires_approval=False,
            created_at=ts,
            updated_at=ts,
        ),
        BusinessRule(
            rule_id="rule_forecast_wape",
            name="High Forecast Volatility Warning",
            description="Triggers when forecast backtest WAPE exceeds 25%.",
            scenario="demand",
            enabled=True,
            priority=DecisionPriority.MEDIUM,
            evidence_source=EvidenceSourceType.MODEL_METRIC,
            field_name="forecast_wape",
            operator=ComparisonOperator.GT,
            threshold_value=25.0,
            compare_to_field=None,
            expected_unit="%",
            recommended_action="Historical forecast error exceeds 25%. Maintain safety buffer stock and inspect demand variability.",
            explanation_template="Backtest WAPE error is {value}, higher than {threshold}.",
            requires_approval=False,
            created_at=ts,
            updated_at=ts,
        ),
        BusinessRule(
            rule_id="rule_high_churn",
            name="Elevated Customer Churn Risk",
            description="Triggers when model predicts a high churn likelihood (>= 70%).",
            scenario="churn",
            enabled=True,
            priority=DecisionPriority.CRITICAL,
            evidence_source=EvidenceSourceType.PREDICTION,
            field_name="top_class_probability",
            operator=ComparisonOperator.GTE,
            threshold_value=0.70,
            compare_to_field=None,
            expected_unit="%",
            recommended_action="Initiate proactive customer retention outreach and offer targeted account review.",
            explanation_template="Predicted churn probability is {value}, exceeding critical risk threshold {threshold}.",
            requires_approval=True,
            created_at=ts,
            updated_at=ts,
        ),
        BusinessRule(
            rule_id="rule_err_tolerance",
            name="Operational Error Tolerance Exceeded",
            description="Triggers when model MAE exceeds acceptable error threshold.",
            scenario="general",
            enabled=True,
            priority=DecisionPriority.MEDIUM,
            evidence_source=EvidenceSourceType.MODEL_METRIC,
            field_name="model_mae",
            operator=ComparisonOperator.GT,
            threshold_value=None,
            compare_to_field="max_acceptable_error",
            expected_unit=None,
            recommended_action="Model prediction deviation exceeds specified operational tolerance. Review input features.",
            explanation_template="Model MAE ({value}) exceeds operational error threshold ({threshold}).",
            requires_approval=False,
            created_at=ts,
            updated_at=ts,
        ),
    ]
    raw = [r.model_dump() for r in seed_rules]
    RULES_FILE.write_text(json.dumps(raw, indent=2))


# ---------- Rules CRUD ----------

def list_rules(scenario: Optional[str] = None, enabled_only: bool = False) -> List[BusinessRule]:
    ensure_directories()
    try:
        raw = json.loads(RULES_FILE.read_text())
        rules = [BusinessRule(**item) for item in raw]
        if scenario and scenario != "all":
            rules = [r for r in rules if r.scenario.lower() == scenario.lower() or r.scenario.lower() == "general"]
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules
    except Exception as e:
        logger.error("Error reading rules: %s", e)
        return []


def get_rule(rule_id: str) -> Optional[BusinessRule]:
    ensure_directories()
    rules = list_rules()
    for r in rules:
        if r.rule_id == rule_id:
            return r
    return None


def save_rule(rule: BusinessRule) -> BusinessRule:
    ensure_directories()
    rules = list_rules()
    updated = False
    new_rules: List[BusinessRule] = []

    for r in rules:
        if r.rule_id == rule.rule_id:
            new_rules.append(rule)
            updated = True
        else:
            new_rules.append(r)

    if not updated:
        new_rules.append(rule)

    raw = [r.model_dump() for r in new_rules]
    RULES_FILE.write_text(json.dumps(raw, indent=2))
    return rule


def delete_rule(rule_id: str) -> bool:
    ensure_directories()
    rules = list_rules()
    new_rules = [r for r in rules if r.rule_id != rule_id]
    if len(new_rules) == len(rules):
        return False
    raw = [r.model_dump() for r in new_rules]
    RULES_FILE.write_text(json.dumps(raw, indent=2))
    return True


# ---------- Decision Evaluations ----------

def save_evaluation(evaluation: DecisionEvaluation) -> DecisionEvaluation:
    ensure_directories()
    path = EVALUATIONS_DIR / f"{evaluation.evaluation_id}.json"
    path.write_text(json.dumps(evaluation.model_dump(), indent=2))
    return evaluation


def get_evaluation(eval_id: str) -> Optional[DecisionEvaluation]:
    ensure_directories()
    path = EVALUATIONS_DIR / f"{eval_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return DecisionEvaluation(**data)
    except Exception as e:
        logger.error("Error reading evaluation %s: %s", eval_id, e)
        return None


def list_evaluations(limit: int = 50) -> List[DecisionEvaluation]:
    ensure_directories()
    evals: List[DecisionEvaluation] = []
    files = sorted(EVALUATIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[:limit]:
        try:
            data = json.loads(f.read_text())
            evals.append(DecisionEvaluation(**data))
        except Exception:
            pass
    return evals


# ---------- Recommendations ----------

def save_recommendation(rec: Recommendation) -> Recommendation:
    ensure_directories()
    path = RECOMMENDATIONS_DIR / f"{rec.recommendation_id}.json"
    path.write_text(json.dumps(rec.model_dump(), indent=2))
    return rec


def get_recommendation(rec_id: str) -> Optional[Recommendation]:
    ensure_directories()
    path = RECOMMENDATIONS_DIR / f"{rec_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return Recommendation(**data)
    except Exception as e:
        logger.error("Error reading recommendation %s: %s", rec_id, e)
        return None


def list_recommendations(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    evaluation_id: Optional[str] = None,
    limit: int = 100,
) -> List[Recommendation]:
    ensure_directories()
    recs: List[Recommendation] = []
    files = sorted(RECOMMENDATIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    for f in files:
        if len(recs) >= limit:
            break
        try:
            data = json.loads(f.read_text())
            rec = Recommendation(**data)
            if status and status != "all" and rec.status.value != status:
                continue
            if priority and priority != "all" and rec.priority.value != priority:
                continue
            if evaluation_id and rec.evaluation_id != evaluation_id:
                continue
            recs.append(rec)
        except Exception:
            pass
    return recs


# ---------- Audit Trail ----------

def record_audit(item: DecisionAuditItem) -> DecisionAuditItem:
    ensure_directories()
    try:
        raw = json.loads(AUDIT_FILE.read_text()) if AUDIT_FILE.exists() else []
        raw.insert(0, item.model_dump())
        # Keep last 500 audit items
        AUDIT_FILE.write_text(json.dumps(raw[:500], indent=2))
    except Exception as e:
        logger.error("Error writing audit item: %s", e)
    return item


def list_audit_trail(limit: int = 100) -> List[DecisionAuditItem]:
    ensure_directories()
    try:
        raw = json.loads(AUDIT_FILE.read_text()) if AUDIT_FILE.exists() else []
        return [DecisionAuditItem(**item) for item in raw[:limit]]
    except Exception:
        return []


# ---------- Overview Stats ----------

def get_overview_stats() -> DecisionOverviewStats:
    ensure_directories()
    all_evals = list_evaluations(limit=100)
    all_recs = list_recommendations(limit=200)
    active_rules = list_rules(enabled_only=True)

    needs_review = sum(1 for r in all_recs if r.status == RecommendationStatus.NEEDS_REVIEW)
    pending_appr = sum(1 for r in all_recs if r.status == RecommendationStatus.PENDING_APPROVAL)
    high_priority = sum(
        1 for r in all_recs
        if r.priority in (DecisionPriority.CRITICAL, DecisionPriority.HIGH)
        and r.status in (RecommendationStatus.NEEDS_REVIEW, RecommendationStatus.PENDING_APPROVAL)
    )

    eval_failures = sum(1 for e in all_evals if e.not_evaluable_rules_count > 0)

    return DecisionOverviewStats(
        total_evaluations=len(all_evals),
        needs_review_count=needs_review,
        high_priority_count=high_priority,
        pending_approval_count=pending_appr,
        eval_failures_count=eval_failures,
        total_active_rules=len(active_rules),
        recent_evaluations=all_evals[:5],
        recent_recommendations=all_recs[:10],
    )
