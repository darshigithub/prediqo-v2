"""API routes for AI-Powered Business Explanation Layer.
Provides guaranteed business-friendly fallback responses and prevents leaking internal exceptions.
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException

from .explanation_models import (
    AIExplanationResponse,
    ForecastExplanationRequest,
    PredictionExplanationRequest,
)
from .explanation_service import (
    ExplanationService,
    generate_deterministic_forecast_explanation,
    generate_deterministic_prediction_explanation,
    generate_evidence_fingerprint,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai-explanations"])


@router.get("/status")
def get_explanation_status() -> dict[str, Any]:
    """Returns AI explanation status, active providers, and cache size."""
    try:
        return ExplanationService.get_status()
    except Exception as e:
        logger.warning("Status check failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve AI explanation service status.")


@router.post("/prediction", response_model=AIExplanationResponse)
def explain_prediction(req: PredictionExplanationRequest) -> AIExplanationResponse:
    """Generates structured business explanation for a single prediction with guaranteed fallback."""
    try:
        return ExplanationService.explain_prediction(req)
    except Exception as e:
        logger.warning("Unexpected exception in explain_prediction: %s. Returning deterministic fallback.", e)
        compact_evidence: dict[str, Any] = {
            "target_name": req.target_name,
            "problem_type": req.problem_type,
            "unit": req.unit,
            "prediction": req.prediction,
            "probabilities": req.probabilities,
            "baseline_reference_value": req.baseline_reference_value,
            "decomposition_space": req.decomposition_space or "ORIGINAL_TARGET_SPACE",
            "contributions": req.contributions[:10] if req.contributions else [],
            "metrics": req.metrics,
            "model_metadata": req.model_metadata,
            "data_quality": req.data_quality,
        }
        fingerprint = generate_evidence_fingerprint(compact_evidence)
        return generate_deterministic_prediction_explanation(compact_evidence, fingerprint)


@router.post("/forecast", response_model=AIExplanationResponse)
def explain_forecast(req: ForecastExplanationRequest) -> AIExplanationResponse:
    """Generates structured business explanation for a time-series forecast with guaranteed fallback."""
    try:
        return ExplanationService.explain_forecast(req)
    except Exception as e:
        logger.warning("Unexpected exception in explain_forecast: %s. Returning deterministic fallback.", e)
        compact_evidence: dict[str, Any] = {
            "metric_column": req.metric_column,
            "date_column": req.date_column,
            "frequency": req.frequency,
            "horizon": req.horizon,
            "aggregation": req.aggregation,
            "unit": req.unit,
            "historical_summary": req.historical_summary,
            "forecast_summary": req.forecast_summary,
            "backtest_metrics": req.backtest_metrics,
            "intervals": req.intervals,
            "limitations": req.limitations,
        }
        fingerprint = generate_evidence_fingerprint(compact_evidence)
        return generate_deterministic_forecast_explanation(compact_evidence, fingerprint)
