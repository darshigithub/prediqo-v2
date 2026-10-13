"""Comprehensive test suite for the Prediqo Decision Layer MVP.
Tests rules validation, deterministic operator logic, unit compatibility,
missing evidence handling, recommendation generation, status transitions,
audit trails, and disk persistence.
"""
import pytest
from app.decisions.models import (
    BusinessRule,
    ComparisonOperator,
    DecisionPriority,
    EvaluationRequest,
    EvidenceSourceType,
    RecommendationStatus,
    RecommendationStatusUpdate,
    RuleCreatePayload,
    RuleEvaluationStatus,
    RuleValidationPayload,
)
from app.decisions.rules_engine import evaluate_rule, validate_rule_definition
from app.decisions.service import DecisionService
from app.decisions.store import list_rules, get_rule, save_rule, delete_rule


def test_rule_validation():
    # Valid rule
    valid_res = validate_rule_definition(
        RuleValidationPayload(
            field_name="predicted_demand",
            operator=ComparisonOperator.GT,
            threshold_value=500,
        )
    )
    assert valid_res.is_valid is True

    # Empty field name
    empty_res = validate_rule_definition(
        RuleValidationPayload(
            field_name="  ",
            operator=ComparisonOperator.GT,
            threshold_value=500,
        )
    )
    assert empty_res.is_valid is False
    assert "empty" in empty_res.message.lower()

    # Missing threshold and compare_to_field for GT
    no_thresh = validate_rule_definition(
        RuleValidationPayload(
            field_name="predicted_demand",
            operator=ComparisonOperator.GT,
            threshold_value=None,
        )
    )
    assert no_thresh.is_valid is False

    # Non-numeric threshold for numeric operator
    non_num = validate_rule_definition(
        RuleValidationPayload(
            field_name="predicted_demand",
            operator=ComparisonOperator.GT,
            threshold_value="not_a_number",
        )
    )
    assert non_num.is_valid is False
    assert "numeric" in non_num.message.lower()

    # Self-comparison
    self_comp = validate_rule_definition(
        RuleValidationPayload(
            field_name="stock",
            operator=ComparisonOperator.GT,
            compare_to_field="stock",
        )
    )
    assert self_comp.is_valid is False
    assert "same" in self_comp.message.lower()


def test_all_comparison_operators():
    # Helper to build test rule
    def make_rule(op: ComparisonOperator, thresh: any = None, compare_field: str = None, unit: str = None):
        return BusinessRule(
            rule_id="test_op",
            name="Test Op",
            description="Test",
            scenario="test",
            enabled=True,
            priority=DecisionPriority.HIGH,
            evidence_source=EvidenceSourceType.OPERATIONAL_FACT,
            field_name="val",
            operator=op,
            threshold_value=thresh,
            compare_to_field=compare_field,
            expected_unit=unit,
            recommended_action="Take Action",
            explanation_template="{field} {op} {threshold}",
            requires_approval=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

    # 1. EQ
    eq_rule = make_rule(ComparisonOperator.EQ, "Active")
    assert evaluate_rule(eq_rule, {"val": "Active"}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(eq_rule, {"val": "Inactive"}).status == RuleEvaluationStatus.NOT_TRIGGERED

    # 2. NEQ
    neq_rule = make_rule(ComparisonOperator.NEQ, "Active")
    assert evaluate_rule(neq_rule, {"val": "Suspended"}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(neq_rule, {"val": "Active"}).status == RuleEvaluationStatus.NOT_TRIGGERED

    # 3. GT
    gt_rule = make_rule(ComparisonOperator.GT, 100)
    assert evaluate_rule(gt_rule, {"val": 150}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(gt_rule, {"val": 100}).status == RuleEvaluationStatus.NOT_TRIGGERED
    assert evaluate_rule(gt_rule, {"val": 50}).status == RuleEvaluationStatus.NOT_TRIGGERED

    # 4. GTE
    gte_rule = make_rule(ComparisonOperator.GTE, 100)
    assert evaluate_rule(gte_rule, {"val": 100}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(gte_rule, {"val": 99}).status == RuleEvaluationStatus.NOT_TRIGGERED

    # 5. LT
    lt_rule = make_rule(ComparisonOperator.LT, 100)
    assert evaluate_rule(lt_rule, {"val": 90}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(lt_rule, {"val": 100}).status == RuleEvaluationStatus.NOT_TRIGGERED

    # 6. LTE
    lte_rule = make_rule(ComparisonOperator.LTE, 100)
    assert evaluate_rule(lte_rule, {"val": 100}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(lte_rule, {"val": 101}).status == RuleEvaluationStatus.NOT_TRIGGERED

    # 7. IS_PRESENT
    pres_rule = make_rule(ComparisonOperator.IS_PRESENT)
    assert evaluate_rule(pres_rule, {"val": "hello"}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(pres_rule, {"other": 123}).status == RuleEvaluationStatus.NOT_TRIGGERED

    # 8. IS_MISSING
    miss_rule = make_rule(ComparisonOperator.IS_MISSING)
    assert evaluate_rule(miss_rule, {"other": 123}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(miss_rule, {"val": None}).status == RuleEvaluationStatus.TRIGGERED
    assert evaluate_rule(miss_rule, {"val": 456}).status == RuleEvaluationStatus.NOT_TRIGGERED


def test_missing_evidence_is_not_evaluable():
    rule = BusinessRule(
        rule_id="test_missing",
        name="Missing Check",
        description="Test",
        scenario="test",
        enabled=True,
        priority=DecisionPriority.MEDIUM,
        evidence_source=EvidenceSourceType.OPERATIONAL_FACT,
        field_name="unprovided_metric",
        operator=ComparisonOperator.GT,
        threshold_value=50,
        compare_to_field=None,
        expected_unit=None,
        recommended_action="Take Action",
        explanation_template="",
        requires_approval=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    # When field is missing for a GT operator, it must be NOT_EVALUABLE, not NOT_TRIGGERED!
    res = evaluate_rule(rule, {"other_field": 100})
    assert res.status == RuleEvaluationStatus.NOT_EVALUABLE
    assert "missing evidence" in res.message.lower()


def test_unit_compatibility_checking():
    rule = BusinessRule(
        rule_id="test_units",
        name="Unit Incompatibility Check",
        description="Test",
        scenario="test",
        enabled=True,
        priority=DecisionPriority.HIGH,
        evidence_source=EvidenceSourceType.OPERATIONAL_FACT,
        field_name="delivery_lead_time",
        operator=ComparisonOperator.GT,
        threshold_value=None,
        compare_to_field="budget_amount",
        expected_unit="days",
        recommended_action="Action",
        explanation_template="",
        requires_approval=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    from app.decisions.models import EvidenceItem
    evidence_meta = {
        "delivery_lead_time": EvidenceItem(
            field_name="delivery_lead_time",
            source_type=EvidenceSourceType.OPERATIONAL_FACT,
            value=14,
            unit="days",
            timestamp="2026-01-01T00:00:00Z",
        ),
        "budget_amount": EvidenceItem(
            field_name="budget_amount",
            source_type=EvidenceSourceType.OPERATIONAL_FACT,
            value=5000,
            unit="$",
            timestamp="2026-01-01T00:00:00Z",
        ),
    }

    res = evaluate_rule(
        rule,
        {"delivery_lead_time": 14, "budget_amount": 5000},
        evidence_metadata=evidence_meta,
    )
    assert res.status == RuleEvaluationStatus.NOT_EVALUABLE
    assert "incompatible units" in res.message.lower()


def test_rule_crud_and_persistence():
    payload = RuleCreatePayload(
        name="Unit Test Custom Rule",
        description="Testing CRUD persistence",
        scenario="inventory",
        enabled=True,
        priority=DecisionPriority.CRITICAL,
        evidence_source=EvidenceSourceType.OPERATIONAL_FACT,
        field_name="custom_stock_level",
        operator=ComparisonOperator.LT,
        threshold_value=25,
        expected_unit="units",
        recommended_action="Emergency stock reorder",
        explanation_template="{field} is below critical threshold {threshold}",
        requires_approval=True,
    )

    created = DecisionService.create_rule(payload)
    assert created.rule_id.startswith("rule_")
    assert created.name == "Unit Test Custom Rule"

    # Retrieve by ID
    fetched = DecisionService.get_rule(created.rule_id)
    assert fetched is not None
    assert fetched.priority == DecisionPriority.CRITICAL

    # Toggle
    toggled = DecisionService.toggle_rule(created.rule_id, False)
    assert toggled.enabled is False

    # Delete
    deleted = DecisionService.delete_rule(created.rule_id)
    assert deleted is True
    assert DecisionService.get_rule(created.rule_id) is None


def test_decision_evaluation_and_recommendation_lifecycle():
    # Evaluate an inventory scenario with stockout condition
    req = EvaluationRequest(
        scenario="inventory",
        operational_facts={
            "predicted_demand": 1500,
            "available_inventory": 900,
            "available_inventory_unit": "units",
            "max_inventory_capacity": 5000,
        },
        actor="test_officer",
    )

    evaluation = DecisionService.evaluate_scenario(req)
    assert evaluation.evaluation_id.startswith("eval_")
    assert evaluation.total_rules_evaluated > 0

    # Stockout rule should trigger (predicted_demand 1500 > available_inventory 900)
    stockout_res = next((r for r in evaluation.rule_results if r.rule_id == "rule_inv_stockout"), None)
    assert stockout_res is not None
    assert stockout_res.status == RuleEvaluationStatus.TRIGGERED

    # Check generated recommendation
    assert len(evaluation.recommendations) > 0
    rec = next((r for r in evaluation.recommendations if "rule_inv_stockout" in r.triggered_rule_ids), None)
    assert rec is not None
    assert rec.priority == DecisionPriority.HIGH
    assert rec.status == RecommendationStatus.PENDING_APPROVAL
    assert "replenishment" in rec.recommended_action.lower()
    assert len(rec.supporting_evidence) >= 1

    # Status Lifecycle: Approval
    approved_rec = DecisionService.update_recommendation_status(
        rec.recommendation_id,
        RecommendationStatusUpdate(
            new_status=RecommendationStatus.APPROVED,
            comment="Approved by inventory director.",
            actor="inventory_director",
        ),
    )
    assert approved_rec.status == RecommendationStatus.APPROVED
    assert approved_rec.status_comment == "Approved by inventory director."

    # Status Lifecycle: Rejection requires comment
    with pytest.raises(ValueError) as exc:
        DecisionService.update_recommendation_status(
            rec.recommendation_id,
            RecommendationStatusUpdate(
                new_status=RecommendationStatus.REJECTED,
                comment="",  # Empty comment
                actor="inventory_director",
            ),
        )
    assert "reason or comment is required" in str(exc.value).lower()

    # Reject with comment succeeds
    rejected_rec = DecisionService.update_recommendation_status(
        rec.recommendation_id,
        RecommendationStatusUpdate(
            new_status=RecommendationStatus.REJECTED,
            comment="Alternate supplier already booked.",
            actor="inventory_director",
        ),
    )
    assert rejected_rec.status == RecommendationStatus.REJECTED


def test_decision_api_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Overview
    res = client.get("/api/decisions/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_evaluations" in data
    assert "total_active_rules" in data

    # 2. Scenarios
    res = client.get("/api/decisions/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert any(s["id"] == "inventory" for s in scenarios)

    # 3. Rules list
    res = client.get("/api/decisions/rules")
    assert res.status_code == 200
    rules = res.json()
    assert len(rules) >= 1

    # 4. Rule validate
    res = client.post(
        "/api/decisions/rules/validate",
        json={
            "field_name": "test_field",
            "operator": "gt",
            "threshold_value": 100,
        },
    )
    assert res.status_code == 200
    assert res.json()["is_valid"] is True

    # 5. Evaluate scenario
    res = client.post(
        "/api/decisions/evaluate",
        json={
            "scenario": "data_quality",
            "operational_facts": {
                "data_completeness_pct": 72.5,
            },
        },
    )
    assert res.status_code == 200
    eval_data = res.json()
    assert eval_data["triggered_rules_count"] >= 1
    assert len(eval_data["recommendations"]) >= 1

    # 6. Recommendations list
    res = client.get("/api/decisions/recommendations")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 7. Audit trail
    res = client.get("/api/decisions/audit")
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_audit_trail_and_overview_stats():
    stats = DecisionService.get_overview_stats()
    assert stats.total_evaluations >= 0
    assert stats.total_active_rules > 0

    audit_items = DecisionService.list_audit_trail(limit=10)
    assert len(audit_items) > 0
    assert all(a.audit_id.startswith("aud_") for a in audit_items)
