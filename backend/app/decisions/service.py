"""Decision service orchestrating scenario evaluation, recommendation synthesis,
status lifecycle transitions, and audit logging.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import (
    BusinessRule,
    DecisionAuditItem,
    DecisionEvaluation,
    DecisionOverviewStats,
    DecisionPriority,
    EvaluationRequest,
    EvidenceItem,
    Recommendation,
    RecommendationStatus,
    RecommendationStatusUpdate,
    RuleCreatePayload,
    RuleEvaluationResult,
    RuleEvaluationStatus,
    RuleValidationPayload,
    RuleValidationResponse,
)
from .rules_engine import evaluate_rule, validate_rule_definition
from .evidence_collector import collect_evidence
from .store import (
    delete_rule as store_delete_rule,
    get_evaluation as store_get_eval,
    get_overview_stats as store_get_overview,
    get_recommendation as store_get_rec,
    get_rule as store_get_rule,
    list_audit_trail as store_list_audit,
    list_evaluations as store_list_evals,
    list_recommendations as store_list_recs,
    list_rules as store_list_rules,
    record_audit as store_record_audit,
    save_evaluation as store_save_eval,
    save_recommendation as store_save_rec,
    save_rule as store_save_rule,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionService:
    @staticmethod
    def list_scenarios() -> List[Dict[str, Any]]:
        """Returns standard pre-configured business scenarios and their expected fields."""
        return [
            {
                "id": "inventory",
                "name": "Inventory & Stock Planning",
                "description": "Align future demand projections with warehouse stock availability to prevent stockouts and overstocking.",
                "relevant_fields": ["predicted_demand", "available_inventory", "max_inventory_capacity", "lead_time_days"],
                "default_units": "units",
            },
            {
                "id": "demand",
                "name": "Sales & Demand Trajectory",
                "description": "Monitor time-series demand spikes, volatility, and volume forecast thresholds.",
                "relevant_fields": ["forecast_total", "forecast_average", "forecast_peak", "forecast_wape"],
                "default_units": "units / $",
            },
            {
                "id": "churn",
                "name": "Customer Retention & Churn Risk",
                "description": "Evaluate predicted customer churn probabilities and identify high-risk accounts.",
                "relevant_fields": ["top_class_probability", "predicted_value", "account_tenure"],
                "default_units": "%",
            },
            {
                "id": "data_quality",
                "name": "Data Pipeline Health & Integrity",
                "description": "Enforce baseline dataset completeness and missing value tolerances before modeling.",
                "relevant_fields": ["data_completeness_pct", "columns_with_nulls", "dataset_total_rows"],
                "default_units": "%",
            },
            {
                "id": "general",
                "name": "General Operational Risk",
                "description": "Generic rule evaluation across custom operational facts, budgets, and ML model error tolerances.",
                "relevant_fields": ["model_mae", "model_accuracy", "max_acceptable_error", "budget_limit"],
                "default_units": "custom",
            },
        ]

    # ---------- Rules Management ----------

    @staticmethod
    def list_rules(scenario: Optional[str] = None, enabled_only: bool = False) -> List[BusinessRule]:
        return store_list_rules(scenario=scenario, enabled_only=enabled_only)

    @staticmethod
    def get_rule(rule_id: str) -> Optional[BusinessRule]:
        return store_get_rule(rule_id)

    @staticmethod
    def validate_rule(payload: RuleValidationPayload) -> RuleValidationResponse:
        return validate_rule_definition(payload)

    @staticmethod
    def create_rule(payload: RuleCreatePayload) -> BusinessRule:
        val = validate_rule_definition(
            RuleValidationPayload(
                field_name=payload.field_name,
                operator=payload.operator,
                threshold_value=payload.threshold_value,
                compare_to_field=payload.compare_to_field,
                expected_unit=payload.expected_unit,
            )
        )
        if not val.is_valid:
            raise ValueError(val.message)

        ts = _now()
        rule = BusinessRule(
            rule_id=f"rule_{uuid.uuid4().hex[:8]}",
            name=payload.name.strip(),
            description=payload.description.strip(),
            scenario=payload.scenario.strip().lower(),
            enabled=payload.enabled,
            priority=payload.priority,
            evidence_source=payload.evidence_source,
            field_name=payload.field_name.strip(),
            operator=payload.operator,
            threshold_value=payload.threshold_value,
            compare_to_field=payload.compare_to_field.strip() if payload.compare_to_field else None,
            expected_unit=payload.expected_unit.strip() if payload.expected_unit else None,
            recommended_action=payload.recommended_action.strip(),
            explanation_template=payload.explanation_template.strip(),
            requires_approval=payload.requires_approval,
            created_at=ts,
            updated_at=ts,
        )
        saved = store_save_rule(rule)
        store_record_audit(
            DecisionAuditItem(
                audit_id=f"aud_{uuid.uuid4().hex[:8]}",
                action="RULE_CREATED",
                actor="local_user",
                comment=f"Created rule '{saved.name}' ({saved.rule_id}) for scenario '{saved.scenario}'.",
                timestamp=ts,
            )
        )
        return saved

    @staticmethod
    def update_rule(rule_id: str, payload: RuleCreatePayload) -> BusinessRule:
        existing = store_get_rule(rule_id)
        if not existing:
            raise KeyError(f"Rule '{rule_id}' not found.")

        val = validate_rule_definition(
            RuleValidationPayload(
                field_name=payload.field_name,
                operator=payload.operator,
                threshold_value=payload.threshold_value,
                compare_to_field=payload.compare_to_field,
                expected_unit=payload.expected_unit,
            )
        )
        if not val.is_valid:
            raise ValueError(val.message)

        ts = _now()
        updated = BusinessRule(
            rule_id=rule_id,
            name=payload.name.strip(),
            description=payload.description.strip(),
            scenario=payload.scenario.strip().lower(),
            enabled=payload.enabled,
            priority=payload.priority,
            evidence_source=payload.evidence_source,
            field_name=payload.field_name.strip(),
            operator=payload.operator,
            threshold_value=payload.threshold_value,
            compare_to_field=payload.compare_to_field.strip() if payload.compare_to_field else None,
            expected_unit=payload.expected_unit.strip() if payload.expected_unit else None,
            recommended_action=payload.recommended_action.strip(),
            explanation_template=payload.explanation_template.strip(),
            requires_approval=payload.requires_approval,
            created_at=existing.created_at,
            updated_at=ts,
        )
        store_save_rule(updated)
        store_record_audit(
            DecisionAuditItem(
                audit_id=f"aud_{uuid.uuid4().hex[:8]}",
                action="RULE_UPDATED",
                actor="local_user",
                comment=f"Updated rule '{updated.name}' ({rule_id}).",
                timestamp=ts,
            )
        )
        return updated

    @staticmethod
    def toggle_rule(rule_id: str, enabled: bool) -> BusinessRule:
        existing = store_get_rule(rule_id)
        if not existing:
            raise KeyError(f"Rule '{rule_id}' not found.")

        existing.enabled = enabled
        existing.updated_at = _now()
        store_save_rule(existing)
        store_record_audit(
            DecisionAuditItem(
                audit_id=f"aud_{uuid.uuid4().hex[:8]}",
                action="RULE_TOGGLED",
                actor="local_user",
                comment=f"Rule '{existing.name}' ({rule_id}) set to {'enabled' if enabled else 'disabled'}.",
                timestamp=existing.updated_at,
            )
        )
        return existing

    @staticmethod
    def delete_rule(rule_id: str) -> bool:
        existing = store_get_rule(rule_id)
        if not existing:
            raise KeyError(f"Rule '{rule_id}' not found.")
        success = store_delete_rule(rule_id)
        if success:
            store_record_audit(
                DecisionAuditItem(
                    audit_id=f"aud_{uuid.uuid4().hex[:8]}",
                    action="RULE_DELETED",
                    actor="local_user",
                    comment=f"Deleted rule '{existing.name}' ({rule_id}).",
                    timestamp=_now(),
                )
            )
        return success

    # ---------- Decision Evaluation ----------

    @staticmethod
    def evaluate_scenario(req: EvaluationRequest) -> DecisionEvaluation:
        ts = _now()
        eval_id = f"eval_{uuid.uuid4().hex[:8]}"

        # 1. Collect evidence
        facts, metadata, missing_notes = collect_evidence(req)

        # 2. Select rules to evaluate
        all_rules = store_list_rules(scenario=req.scenario, enabled_only=True)
        if req.rule_ids:
            target_ids = set(req.rule_ids)
            rules_to_eval = [r for r in store_list_rules(enabled_only=False) if r.rule_id in target_ids]
        else:
            rules_to_eval = all_rules

        # 3. Evaluate each rule deterministically
        rule_results: List[RuleEvaluationResult] = []
        triggered_rules: List[RuleEvaluationResult] = []
        triggered_count = 0
        not_triggered_count = 0
        not_evaluable_count = 0

        for rule in rules_to_eval:
            res = evaluate_rule(rule, facts, metadata)
            rule_results.append(res)
            if res.status == RuleEvaluationStatus.TRIGGERED:
                triggered_count += 1
                triggered_rules.append(res)
            elif res.status == RuleEvaluationStatus.NOT_TRIGGERED:
                not_triggered_count += 1
            elif res.status == RuleEvaluationStatus.NOT_EVALUABLE:
                not_evaluable_count += 1
                missing_notes.append(f"Rule '{rule.name}' not evaluable: {res.message}")

        # 4. Generate structured recommendations from triggered rules
        recommendations: List[Recommendation] = []

        for trig in triggered_rules:
            rec_id = f"rec_{uuid.uuid4().hex[:8]}"
            # Priority comes from the explicit rule definition, never fabricated
            status = RecommendationStatus.PENDING_APPROVAL if trig.requires_approval else RecommendationStatus.NEEDS_REVIEW

            uncertainty_notes: List[str] = [
                "Guidance notice: This recommendation is generated from deterministic business rules and statistical associations.",
                "It does not guarantee improved operational or financial outcomes.",
            ]
            if not_evaluable_count > 0:
                uncertainty_notes.append(
                    f"{not_evaluable_count} related rule(s) could not be evaluated due to missing evidence."
                )

            rec = Recommendation(
                recommendation_id=rec_id,
                evaluation_id=eval_id,
                scenario=req.scenario,
                title=f"{trig.rule_name} Action Required",
                recommended_action=trig.recommended_action or "Review operational conditions and verify supporting evidence.",
                description=trig.message,
                priority=trig.priority,
                status=status,
                triggered_rule_ids=[trig.rule_id],
                supporting_evidence=trig.evidence_items,
                missing_evidence=missing_notes,
                uncertainty_notes=uncertainty_notes,
                requires_approval=trig.requires_approval,
                created_at=ts,
                updated_at=ts,
            )
            store_save_rec(rec)
            recommendations.append(rec)

        evaluation = DecisionEvaluation(
            evaluation_id=eval_id,
            scenario=req.scenario,
            dataset_id=req.dataset_id,
            prediction_model_id=req.prediction_model_id,
            forecast_model_id=req.forecast_model_id,
            operational_facts=req.operational_facts or {},
            total_rules_evaluated=len(rules_to_eval),
            triggered_rules_count=triggered_count,
            not_triggered_rules_count=not_triggered_count,
            not_evaluable_rules_count=not_evaluable_count,
            rule_results=rule_results,
            recommendations=recommendations,
            missing_evidence=missing_notes,
            created_at=ts,
        )

        store_save_eval(evaluation)

        # Audit record
        store_record_audit(
            DecisionAuditItem(
                audit_id=f"aud_{uuid.uuid4().hex[:8]}",
                evaluation_id=eval_id,
                action="EVALUATION_EXECUTED",
                actor=req.actor or "local_user",
                comment=f"Evaluated scenario '{req.scenario}' across {len(rules_to_eval)} rules ({triggered_count} triggered, {not_evaluable_count} not evaluable). Generated {len(recommendations)} recommendations.",
                timestamp=ts,
            )
        )

        return evaluation

    @staticmethod
    def get_evaluation(eval_id: str) -> Optional[DecisionEvaluation]:
        return store_get_eval(eval_id)

    @staticmethod
    def list_evaluations(limit: int = 50) -> List[DecisionEvaluation]:
        return store_list_evals(limit=limit)

    # ---------- Recommendations Management ----------

    @staticmethod
    def list_recommendations(
        status: Optional[str] = None,
        priority: Optional[str] = None,
        evaluation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Recommendation]:
        return store_list_recs(status=status, priority=priority, evaluation_id=evaluation_id, limit=limit)

    @staticmethod
    def get_recommendation(rec_id: str) -> Optional[Recommendation]:
        return store_get_rec(rec_id)

    @staticmethod
    def update_recommendation_status(
        rec_id: str,
        payload: RecommendationStatusUpdate,
    ) -> Recommendation:
        rec = store_get_rec(rec_id)
        if not rec:
            raise KeyError(f"Recommendation '{rec_id}' not found.")

        # Rejection or dismissal requires an explicit comment
        if payload.new_status in (RecommendationStatus.REJECTED, RecommendationStatus.DISMISSED):
            if not payload.comment or not payload.comment.strip():
                raise ValueError(
                    f"A reason or comment is required when setting status to '{payload.new_status.value}'."
                )

        prev_status = rec.status
        rec.status = payload.new_status
        rec.status_comment = payload.comment.strip() if payload.comment else None
        rec.updated_by = payload.actor or "local_user"
        rec.updated_at = _now()

        store_save_rec(rec)

        store_record_audit(
            DecisionAuditItem(
                audit_id=f"aud_{uuid.uuid4().hex[:8]}",
                recommendation_id=rec_id,
                evaluation_id=rec.evaluation_id,
                action="RECOMMENDATION_STATUS_CHANGED",
                previous_status=prev_status.value,
                new_status=payload.new_status.value,
                actor=rec.updated_by,
                comment=payload.comment,
                timestamp=rec.updated_at,
            )
        )
        return rec

    # ---------- Overview & Audit ----------

    @staticmethod
    def get_overview_stats() -> DecisionOverviewStats:
        return store_get_overview()

    @staticmethod
    def list_audit_trail(limit: int = 100) -> List[DecisionAuditItem]:
        return store_list_audit(limit=limit)
