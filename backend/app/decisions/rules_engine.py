"""Safe, deterministic business rules evaluation engine.
Does not use `eval`, dynamic compilation, or unvalidated code execution.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from .models import (
    BusinessRule,
    ComparisonOperator,
    EvidenceItem,
    EvidenceSourceType,
    RuleEvaluationResult,
    RuleEvaluationStatus,
    RuleValidationPayload,
    RuleValidationResponse,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_rule_definition(payload: RuleValidationPayload) -> RuleValidationResponse:
    """Validates rule structure, operators, and types before persistence."""
    field_name = payload.field_name.strip()
    if not field_name:
        return RuleValidationResponse(is_valid=False, message="Field name cannot be empty.")

    op = payload.operator
    if op in (ComparisonOperator.IS_PRESENT, ComparisonOperator.IS_MISSING):
        return RuleValidationResponse(
            is_valid=True,
            message=f"Operator '{op.value}' is valid for field '{field_name}' (requires no threshold value).",
        )

    # For comparison operators, either threshold_value or compare_to_field must be specified
    if payload.threshold_value is None and not payload.compare_to_field:
        return RuleValidationResponse(
            is_valid=False,
            message=f"Operator '{op.value}' requires either a 'threshold_value' or a 'compare_to_field'.",
        )

    # If dynamic comparison, target field cannot be self
    if payload.compare_to_field and payload.compare_to_field.strip() == field_name:
        return RuleValidationResponse(
            is_valid=False,
            message="Dynamic comparison field cannot be the same as the evaluation field.",
        )

    # If numeric comparison, check that static threshold (if provided) is numeric
    if op in (ComparisonOperator.GT, ComparisonOperator.GTE, ComparisonOperator.LT, ComparisonOperator.LTE):
        if payload.threshold_value is not None:
            try:
                float(payload.threshold_value)
            except (ValueError, TypeError):
                return RuleValidationResponse(
                    is_valid=False,
                    message=f"Operator '{op.value}' requires a numeric threshold value. Received: {payload.threshold_value}",
                )

    return RuleValidationResponse(
        is_valid=True,
        message="Rule specification is valid.",
    )


def _check_unit_compatibility(
    unit_a: Optional[str], unit_b: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """Checks if two units are compatible for direct comparison."""
    if not unit_a or not unit_b:
        return True, None  # One or both are unspecified, permissible with caution

    u_a = unit_a.strip().lower()
    u_b = unit_b.strip().lower()

    if u_a == u_b:
        return True, None

    # Handle standard synonyms
    synonyms = {
        "$": "usd",
        "usd": "$",
        "dollars": "$",
        "percentage": "%",
        "percent": "%",
        "pts": "points",
        "points": "pts",
    }
    if synonyms.get(u_a) == u_b or synonyms.get(u_b) == u_a:
        return True, None

    return False, f"Incompatible units: cannot compare '{unit_a}' with '{unit_b}'."


def evaluate_rule(
    rule: BusinessRule,
    evidence_facts: Dict[str, Any],
    evidence_metadata: Optional[Dict[str, EvidenceItem]] = None,
) -> RuleEvaluationResult:
    """Deterministically evaluates a business rule against a dictionary of extracted evidence facts."""
    field_name = rule.field_name
    op = rule.operator

    # Check existence in facts
    has_field = field_name in evidence_facts and evidence_facts[field_name] is not None
    eval_value = evidence_facts.get(field_name)

    # Resolve evidence item if available
    field_evidence = evidence_metadata.get(field_name) if evidence_metadata else None
    eval_unit = field_evidence.unit if field_evidence else rule.expected_unit

    evidence_items_used: List[EvidenceItem] = []
    if field_evidence:
        evidence_items_used.append(field_evidence)

    # 1. Handle presence/missing operators
    if op == ComparisonOperator.IS_PRESENT:
        is_triggered = has_field and eval_value != ""
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            status=RuleEvaluationStatus.TRIGGERED if is_triggered else RuleEvaluationStatus.NOT_TRIGGERED,
            priority=rule.priority,
            field_name=field_name,
            operator=op,
            evaluated_value=eval_value,
            threshold_value="PRESENT",
            evaluated_unit=eval_unit,
            threshold_unit=None,
            message=f"Field '{field_name}' is {'present' if is_triggered else 'missing'}.",
            recommended_action=rule.recommended_action if is_triggered else None,
            requires_approval=rule.requires_approval,
            evidence_items=evidence_items_used,
        )

    if op == ComparisonOperator.IS_MISSING:
        is_triggered = not has_field or eval_value == ""
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            status=RuleEvaluationStatus.TRIGGERED if is_triggered else RuleEvaluationStatus.NOT_TRIGGERED,
            priority=rule.priority,
            field_name=field_name,
            operator=op,
            evaluated_value=eval_value,
            threshold_value="MISSING",
            evaluated_unit=eval_unit,
            threshold_unit=None,
            message=f"Field '{field_name}' is {'missing' if is_triggered else 'present'}.",
            recommended_action=rule.recommended_action if is_triggered else None,
            requires_approval=rule.requires_approval,
            evidence_items=evidence_items_used,
        )

    # If field is missing and operator is a comparison operator -> NOT_EVALUABLE
    if not has_field:
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            status=RuleEvaluationStatus.NOT_EVALUABLE,
            priority=rule.priority,
            field_name=field_name,
            operator=op,
            evaluated_value=None,
            threshold_value=rule.threshold_value or rule.compare_to_field,
            evaluated_unit=eval_unit,
            threshold_unit=None,
            message=f"Missing evidence: field '{field_name}' is not present in provided scenario data.",
            recommended_action=None,
            requires_approval=rule.requires_approval,
            evidence_items=[],
        )

    # 2. Resolve Threshold (static literal vs dynamic compare_to_field)
    target_value: Any = None
    target_unit: Optional[str] = rule.expected_unit

    if rule.compare_to_field:
        compare_field = rule.compare_to_field
        if compare_field not in evidence_facts or evidence_facts[compare_field] is None:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                status=RuleEvaluationStatus.NOT_EVALUABLE,
                priority=rule.priority,
                field_name=field_name,
                operator=op,
                evaluated_value=eval_value,
                threshold_value=f"field:{compare_field}",
                evaluated_unit=eval_unit,
                threshold_unit=None,
                message=f"Missing evidence: dynamic comparison target '{compare_field}' is not available.",
                recommended_action=None,
                requires_approval=rule.requires_approval,
                evidence_items=evidence_items_used,
            )
        target_value = evidence_facts[compare_field]
        target_evidence = evidence_metadata.get(compare_field) if evidence_metadata else None
        if target_evidence:
            evidence_items_used.append(target_evidence)
            if target_evidence.unit:
                target_unit = target_evidence.unit
    else:
        target_value = rule.threshold_value

    if target_value is None:
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            status=RuleEvaluationStatus.NOT_EVALUABLE,
            priority=rule.priority,
            field_name=field_name,
            operator=op,
            evaluated_value=eval_value,
            threshold_value=None,
            evaluated_unit=eval_unit,
            threshold_unit=None,
            message="Rule configuration error: neither threshold_value nor compare_to_field is defined.",
            recommended_action=None,
            requires_approval=rule.requires_approval,
            evidence_items=evidence_items_used,
        )

    # 3. Check Unit Compatibility
    units_compat, unit_err = _check_unit_compatibility(eval_unit, target_unit)
    if not units_compat:
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            status=RuleEvaluationStatus.NOT_EVALUABLE,
            priority=rule.priority,
            field_name=field_name,
            operator=op,
            evaluated_value=eval_value,
            threshold_value=target_value,
            evaluated_unit=eval_unit,
            threshold_unit=target_unit,
            message=f"Unit conflict: {unit_err}",
            recommended_action=None,
            requires_approval=rule.requires_approval,
            evidence_items=evidence_items_used,
        )

    # 4. Perform deterministic comparison
    is_triggered = False

    try:
        if op == ComparisonOperator.EQ:
            is_triggered = str(eval_value).strip().lower() == str(target_value).strip().lower()
        elif op == ComparisonOperator.NEQ:
            is_triggered = str(eval_value).strip().lower() != str(target_value).strip().lower()
        elif op in (ComparisonOperator.GT, ComparisonOperator.GTE, ComparisonOperator.LT, ComparisonOperator.LTE):
            # Must convert to float safely
            try:
                num_eval = float(eval_value)
                num_target = float(target_value)
            except (ValueError, TypeError):
                return RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    status=RuleEvaluationStatus.NOT_EVALUABLE,
                    priority=rule.priority,
                    field_name=field_name,
                    operator=op,
                    evaluated_value=eval_value,
                    threshold_value=target_value,
                    evaluated_unit=eval_unit,
                    threshold_unit=target_unit,
                    message=f"Type error: operator '{op.value}' requires numeric values. Evaluated '{eval_value}', threshold '{target_value}'.",
                    recommended_action=None,
                    requires_approval=rule.requires_approval,
                    evidence_items=evidence_items_used,
                )

            if op == ComparisonOperator.GT:
                is_triggered = num_eval > num_target
            elif op == ComparisonOperator.GTE:
                is_triggered = num_eval >= num_target
            elif op == ComparisonOperator.LT:
                is_triggered = num_eval < num_target
            elif op == ComparisonOperator.LTE:
                is_triggered = num_eval <= num_target
    except Exception as e:
        logger.warning("Error evaluating rule %s: %s", rule.rule_id, e)
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            status=RuleEvaluationStatus.NOT_EVALUABLE,
            priority=rule.priority,
            field_name=field_name,
            operator=op,
            evaluated_value=eval_value,
            threshold_value=target_value,
            evaluated_unit=eval_unit,
            threshold_unit=target_unit,
            message=f"Evaluation execution failure: {str(e)}",
            recommended_action=None,
            requires_approval=rule.requires_approval,
            evidence_items=evidence_items_used,
        )

    # Generate explanation message
    unit_suffix = f" {eval_unit}" if eval_unit else ""
    target_unit_suffix = f" {target_unit}" if target_unit else ""

    comp_symbol = {
        ComparisonOperator.EQ: "==",
        ComparisonOperator.NEQ: "!=",
        ComparisonOperator.GT: ">",
        ComparisonOperator.GTE: ">=",
        ComparisonOperator.LT: "<",
        ComparisonOperator.LTE: "<=",
    }.get(op, op.value)

    if is_triggered:
        msg = f"Rule triggered: {field_name} ({eval_value}{unit_suffix}) {comp_symbol} {target_value}{target_unit_suffix}."
        if rule.explanation_template:
            try:
                # Safe formatting with predefined tokens
                formatted_expl = rule.explanation_template.format(
                    field=field_name,
                    value=f"{eval_value}{unit_suffix}",
                    threshold=f"{target_value}{target_unit_suffix}",
                    op=comp_symbol,
                )
                msg = f"{msg} {formatted_expl}"
            except Exception:
                pass
    else:
        msg = f"Condition not met: {field_name} ({eval_value}{unit_suffix}) is not {comp_symbol} {target_value}{target_unit_suffix}."

    return RuleEvaluationResult(
        rule_id=rule.rule_id,
        rule_name=rule.name,
        status=RuleEvaluationStatus.TRIGGERED if is_triggered else RuleEvaluationStatus.NOT_TRIGGERED,
        priority=rule.priority,
        field_name=field_name,
        operator=op,
        evaluated_value=eval_value,
        threshold_value=target_value,
        evaluated_unit=eval_unit,
        threshold_unit=target_unit,
        message=msg,
        recommended_action=rule.recommended_action if is_triggered else None,
        requires_approval=rule.requires_approval,
        evidence_items=evidence_items_used,
    )
