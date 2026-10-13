"""System prompts and prompt builders for the AI Business Explanation Layer.
Provides clear non-guarantee instructions, standard disclaimers, and corrective retry prompt augmentation.
"""
from __future__ import annotations

import json
from typing import Any, Optional

PROMPT_VERSION = "v1.1"

STANDARD_DISCLAIMER = "These results are estimates based on the available data. Actual outcomes may differ."

EXPLANATION_SYSTEM_PROMPT = """You are an expert Data Science and Predictive Analytics interpreter for enterprise business leaders.
Your mission is to produce clear, executive-friendly, and strictly factual business explanations of machine learning predictions and time-series forecasts.

STRICT EVIDENCE & NUMERICAL INTEGRITY RULES:
1. ABSOLUTE NUMERICAL TRUTH: Every metric, predicted value, historical figure, probability, unit, and interval MUST come directly and verbatim from the supplied evidence JSON. NEVER invent, extrapolate, alter, or hallucinate numbers, currency amounts, ROI, or cost savings.
2. NON-CAUSALITY: Correlation is NOT causation. Feature importance and local additive XAI contributions reflect statistical weights along the model's decision surface; they are NEVER direct causal levers. Do not state that modifying a feature directly causes changes in business outcomes.
3. SCALE ACCURACY: If the model operates in 'LOG_ODDS_MARGIN' space, explicitly state that feature contributions represent directional shifts on a log-odds margin, NOT direct percentage point changes in final probability.
4. CALIBRATION DISCLOSURE: Uncalibrated class probabilities or tree vote shares reflect model scoring confidence, NOT calibrated real-world probabilities. A high score does not guarantee model reliability.
5. NON-GUARANTEE POLICY: Predictions and forecasts are statistical estimates, not certain future outcomes. Never claim guaranteed outcomes, guaranteed profits, or zero risk. Where appropriate, note: "These results are estimates based on the available data. Actual outcomes may differ."
6. MISSING EVIDENCE: If a metric, unit, baseline, or feature is absent or null in the evidence payload, explicitly state that it is unavailable rather than fabricating it.
7. STRICT STRUCTURED OUTPUT: Return ONLY a valid JSON object matching the requested schema. Do not include markdown code block formatting (```json) or conversational text outside the JSON object.
"""


def build_prediction_prompt(evidence: dict[str, Any], corrective_feedback: Optional[str] = None) -> str:
    """Builds a compact user prompt for explaining a tabular machine learning prediction, with optional corrective feedback."""
    target_name = evidence.get("target_name", "Target")
    problem_type = evidence.get("problem_type", "regression")
    unit = evidence.get("unit") or ""
    prediction = evidence.get("prediction")
    baseline = evidence.get("baseline_reference_value")
    decomp_space = evidence.get("decomposition_space", "ORIGINAL_TARGET_SPACE")
    probabilities = evidence.get("probabilities") or {}
    metrics = evidence.get("metrics") or {}
    model_meta = evidence.get("model_metadata") or {}
    contributions = evidence.get("contributions") or []

    # Sort contributions into positive and negative
    pos = [c for c in contributions if (c.get("contribution") or 0) > 0.0001]
    neg = [c for c in contributions if (c.get("contribution") or 0) < -0.0001]
    pos_sorted = sorted(pos, key=lambda x: x.get("contribution", 0), reverse=True)[:5]
    neg_sorted = sorted(neg, key=lambda x: x.get("contribution", 0))[:5]

    evidence_summary = {
        "target": target_name,
        "type": problem_type,
        "prediction_value": prediction,
        "unit": unit or "unspecified",
        "probabilities": probabilities,
        "baseline_reference": baseline,
        "decomposition_space": decomp_space,
        "top_positive_features": pos_sorted,
        "top_negative_features": neg_sorted,
        "model_performance_metrics": metrics,
        "algorithm": model_meta.get("algorithm", "Trained ML Model"),
        "validation_strategy": model_meta.get("validation_strategy", "K-Fold CV"),
        "cv_folds": model_meta.get("cv_folds", 5),
    }

    correction_block = ""
    if corrective_feedback:
        correction_block = f"""
CORRECTION REQUIRED FROM PREVIOUS ATTEMPT:
The previous response failed validation: {corrective_feedback}
Please correct this specific issue:
- Do not assert that any outcome is guaranteed, certain, or risk-free.
- Frame results as estimates based on available data where actual outcomes may differ.
- Output valid JSON conforming exactly to the schema below.
"""

    return f"""Analyze the following validated prediction evidence and produce an executive business explanation.
{correction_block}
EVIDENCE PAYLOAD:
{json.dumps(evidence_summary, indent=2, default=str)}

OUTPUT JSON FORMAT (Return exactly this JSON structure):
{{
  "summary": "Concise 2-sentence executive summary stating what is predicted, the value or class, unit, and baseline comparison.",
  "what_the_result_means": "Clear explanation of what this specific prediction means operationally for the business.",
  "supporting_evidence": [
    "Bullet 1: Top positive feature driver with its numerical contribution and input value.",
    "Bullet 2: Top negative feature driver with its numerical contribution and input value.",
    "Bullet 3: Baseline reference context."
  ],
  "evaluation_quality": "Assessment of model performance based strictly on the provided CV and holdout metrics vs baseline.",
  "uncertainty_and_limitations": [
    "Scale/calibration notice (e.g. log-odds scale, uncalibrated scores).",
    "Non-causal disclosure: Feature attributions represent statistical associations, not direct causal levers. These results are estimates based on available data; actual outcomes may differ."
  ],
  "suggested_verifications": [
    "Verification 1: Operational sanity check before action.",
    "Verification 2: Data freshness check."
  ]
}}"""


def build_forecast_prompt(evidence: dict[str, Any], corrective_feedback: Optional[str] = None) -> str:
    """Builds a compact user prompt for explaining a time-series forecast, with optional corrective feedback."""
    metric = evidence.get("metric_column", "Metric")
    freq = evidence.get("frequency", "daily")
    horizon = evidence.get("horizon", 14)
    unit = evidence.get("unit") or ""
    hist = evidence.get("historical_summary") or {}
    fc = evidence.get("forecast_summary") or {}
    metrics = evidence.get("backtest_metrics") or {}
    intervals = evidence.get("intervals") or {}
    limitations = evidence.get("limitations") or []

    evidence_summary = {
        "metric": metric,
        "frequency": freq,
        "horizon_periods": horizon,
        "unit": unit or "unspecified",
        "historical_period": {
            "start": hist.get("start_date"),
            "end": hist.get("end_date"),
            "mean": hist.get("mean_value"),
            "last": hist.get("last_value"),
        },
        "forecast_projections": {
            "projected_average": fc.get("projected_avg"),
            "projected_cumulative": fc.get("projected_cumulative"),
            "trajectory": fc.get("trajectory", "stable"),
            "change_pct_vs_historical": fc.get("change_pct_vs_historical"),
        },
        "backtest_performance": {
            "algorithm": metrics.get("best_algorithm", "Time-Series Model"),
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "wape": metrics.get("wape"),
            "vs_naive_pct": metrics.get("vs_naive_pct"),
        },
        "intervals": {
            "lower_80": intervals.get("lower_80"),
            "upper_80": intervals.get("upper_80"),
            "lower_95": intervals.get("lower_95"),
            "upper_95": intervals.get("upper_95"),
        },
        "noted_limitations": limitations,
    }

    correction_block = ""
    if corrective_feedback:
        correction_block = f"""
CORRECTION REQUIRED FROM PREVIOUS ATTEMPT:
The previous response failed validation: {corrective_feedback}
Please correct this specific issue:
- Do not assert that any forecast is guaranteed, certain, or risk-free.
- Frame results as statistical estimates based on available data where actual outcomes may differ.
- Output valid JSON conforming exactly to the schema below.
"""

    return f"""Analyze the following validated forecasting evidence and produce an executive business explanation.
{correction_block}
EVIDENCE PAYLOAD:
{json.dumps(evidence_summary, indent=2, default=str)}

OUTPUT JSON FORMAT (Return exactly this JSON structure):
{{
  "summary": "Concise 2-sentence executive summary stating the projected {metric} trajectory, average value, horizon, and historical change.",
  "what_the_result_means": "Clear explanation of what this forecast trajectory implies for business operations, demand, or capacity.",
  "supporting_evidence": [
    "Bullet 1: Projected trajectory and magnitude with exact units.",
    "Bullet 2: Comparison against historical average.",
    "Bullet 3: Backtest model performance beating naive baseline."
  ],
  "evaluation_quality": "Assessment of model backtest reliability based strictly on holdout MAE, RMSE, and WAPE.",
  "uncertainty_and_limitations": [
    "Interval interpretation: Uncertainty bounds reflect statistical dispersion rather than fixed outcomes. These results are estimates based on available data; actual outcomes may differ.",
    "Limitation: Historical stability does not assure protection against sudden macroeconomic shocks or regime shifts."
  ],
  "suggested_verifications": [
    "Verification 1: Check capacity/inventory limits against upper and lower interval extremes.",
    "Verification 2: Verify data freshness and absence of regime shifts."
  ]
}}"""
