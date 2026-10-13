"""API endpoints for the Prediqo Decision Layer MVP."""
from __future__ import annotations

from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException, Query

from .models import (
    BusinessRule,
    DecisionAuditItem,
    DecisionEvaluation,
    DecisionOverviewStats,
    EvaluationRequest,
    Recommendation,
    RecommendationStatusUpdate,
    RuleCreatePayload,
    RuleValidationPayload,
    RuleValidationResponse,
)
from .service import DecisionService

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("/overview", response_model=DecisionOverviewStats)
def get_decision_overview():
    """Retrieves executive overview statistics and recent activity."""
    try:
        return DecisionService.get_overview_stats()
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve decision overview: {e}")


@router.get("/scenarios")
def list_decision_scenarios():
    """Lists pre-configured decision scenarios with standard fields and descriptions."""
    return DecisionService.list_scenarios()


# ---------- Rules Endpoints ----------

@router.get("/rules", response_model=List[BusinessRule])
def list_rules(
    scenario: Optional[str] = Query(None, description="Filter rules by scenario (e.g. inventory, churn)"),
    enabled_only: bool = Query(False, description="Filter only enabled rules"),
):
    """Lists configured business rules."""
    try:
        return DecisionService.list_rules(scenario=scenario, enabled_only=enabled_only)
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve rules: {e}")


@router.post("/rules", response_model=BusinessRule)
def create_rule(payload: RuleCreatePayload):
    """Creates a new business rule."""
    try:
        return DecisionService.create_rule(payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to create rule: {e}")


@router.post("/rules/validate", response_model=RuleValidationResponse)
def validate_rule(payload: RuleValidationPayload):
    """Validates rule structure, operators, and types without saving."""
    return DecisionService.validate_rule(payload)


@router.get("/rules/{rule_id}", response_model=BusinessRule)
def get_rule(rule_id: str):
    """Retrieves details of a specific business rule."""
    rule = DecisionService.get_rule(rule_id)
    if not rule:
        raise HTTPException(404, f"Rule '{rule_id}' not found.")
    return rule


@router.put("/rules/{rule_id}", response_model=BusinessRule)
def update_rule(rule_id: str, payload: RuleCreatePayload):
    """Updates an existing business rule."""
    try:
        return DecisionService.update_rule(rule_id, payload)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to update rule: {e}")


@router.patch("/rules/{rule_id}/toggle", response_model=BusinessRule)
def toggle_rule(rule_id: str, enabled: bool = Query(..., description="Set enabled status")):
    """Enables or disables a business rule."""
    try:
        return DecisionService.toggle_rule(rule_id, enabled)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to toggle rule: {e}")


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    """Deletes a business rule."""
    try:
        success = DecisionService.delete_rule(rule_id)
        if not success:
            raise HTTPException(404, f"Rule '{rule_id}' not found.")
        return {"status": "ok", "message": f"Rule '{rule_id}' deleted."}
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to delete rule: {e}")


# ---------- Decision Evaluation Endpoints ----------

@router.post("/evaluate", response_model=DecisionEvaluation)
def evaluate_decision(payload: EvaluationRequest):
    """Evaluates configured business rules against provided evidence and generates recommendations."""
    try:
        return DecisionService.evaluate_scenario(payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Decision evaluation failed: {e}")


@router.get("/evaluations", response_model=List[DecisionEvaluation])
def list_evaluations(limit: int = Query(50, ge=1, le=200)):
    """Lists historical decision evaluations."""
    try:
        return DecisionService.list_evaluations(limit=limit)
    except Exception as e:
        raise HTTPException(500, f"Failed to list evaluations: {e}")


@router.get("/evaluations/{eval_id}", response_model=DecisionEvaluation)
def get_evaluation(eval_id: str):
    """Retrieves full details of a specific decision evaluation including rule results and evidence."""
    ev = DecisionService.get_evaluation(eval_id)
    if not ev:
        raise HTTPException(404, f"Evaluation '{eval_id}' not found.")
    return ev


# ---------- Recommendations Endpoints ----------

@router.get("/recommendations", response_model=List[Recommendation])
def list_recommendations(
    status: Optional[str] = Query(None, description="Filter by status (e.g. needs_review, approved)"),
    priority: Optional[str] = Query(None, description="Filter by priority (e.g. critical, high)"),
    evaluation_id: Optional[str] = Query(None, description="Filter by evaluation ID"),
    limit: int = Query(100, ge=1, le=500),
):
    """Lists business recommendations with optional filtering."""
    try:
        return DecisionService.list_recommendations(
            status=status,
            priority=priority,
            evaluation_id=evaluation_id,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to list recommendations: {e}")


@router.get("/recommendations/{rec_id}", response_model=Recommendation)
def get_recommendation(rec_id: str):
    """Retrieves details of a specific recommendation."""
    rec = DecisionService.get_recommendation(rec_id)
    if not rec:
        raise HTTPException(404, f"Recommendation '{rec_id}' not found.")
    return rec


@router.post("/recommendations/{rec_id}/status", response_model=Recommendation)
def update_recommendation_status(rec_id: str, payload: RecommendationStatusUpdate):
    """Updates the status of a recommendation (review, approve, reject, dismiss, complete)."""
    try:
        return DecisionService.update_recommendation_status(rec_id, payload)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to update recommendation status: {e}")


# ---------- Audit Trail Endpoints ----------

@router.get("/audit", response_model=List[DecisionAuditItem])
def list_audit_trail(limit: int = Query(100, ge=1, le=500)):
    """Retrieves chronological decision audit history."""
    try:
        return DecisionService.list_audit_trail(limit=limit)
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve audit trail: {e}")
