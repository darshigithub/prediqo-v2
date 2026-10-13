"""Inference and explanation generation using trained pipelines."""
from __future__ import annotations

import logging
from typing import Any, Optional
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from .models import ModelMetadata, PredictResponse

logger = logging.getLogger(__name__)


def infer_unit_from_target(target_name: str, problem_type: str) -> Optional[str]:
    """Infers display unit if target represents time, currency, or count."""
    t_lower = target_name.lower()
    if any(k in t_lower for k in ("revenue", "amount", "price", "cost", "sales", "spend", "salary", "fee", "budget")):
        return "$"
    if any(k in t_lower for k in ("days", "day")):
        return "days"
    if any(k in t_lower for k in ("hours", "hr", "hrs")):
        return "hours"
    if any(k in t_lower for k in ("minutes", "mins", "min")):
        return "mins"
    if any(k in t_lower for k in ("percent", "pct", "rate", "ratio", "margin")):
        return "%"
    if any(k in t_lower for k in ("count", "qty", "quantity", "units", "items", "volume")):
        return "units"
    if any(k in t_lower for k in ("score", "rating")):
        return "pts"
    return None


def predict_single_record(
    pipeline: Pipeline,
    metadata: ModelMetadata,
    feature_schema: dict[str, Any],
    input_features: dict[str, Any],
) -> PredictResponse:
    """Executes single-record inference, class probabilities, and human-readable explanation."""
    warnings: list[str] = []

    # 1. Validate features against schema
    expected_cols = metadata.feature_columns
    missing_cols = [c for c in expected_cols if c not in input_features]
    if missing_cols:
        warnings.append(
            f"Missing features {missing_cols[:3]} were automatically imputed using training statistics."
        )

    extra_cols = [c for c in input_features if c not in expected_cols]
    if extra_cols:
        warnings.append(f"Ignored {len(extra_cols)} extra feature(s) not in training schema: {extra_cols[:3]}.")

    # 2. Build single-row DataFrame with expected columns
    row_dict = {}
    for col in expected_cols:
        row_dict[col] = input_features.get(col, np.nan)

    input_df = pd.DataFrame([row_dict])

    # 3. Execute prediction
    raw_pred = pipeline.predict(input_df)[0]

    probabilities: dict[str, float] | None = None
    probability_note: Optional[str] = None
    problem_type = metadata.problem_type.lower()

    if problem_type == "regression":
        pred_value = round(float(raw_pred), 2)
        unit = infer_unit_from_target(metadata.target_column, problem_type)

        # Build explanation
        top_factors = [f"{fi.feature} ({int(fi.importance * 100)}%)" for fi in metadata.feature_importance[:2] if fi.importance > 0]
        factor_str = f" based on {', '.join(top_factors)}" if top_factors else ""
        explanation = (
            f"Predicted {metadata.target_column} is {pred_value}"
            f"{' ' + unit if unit else ''}{factor_str} using {metadata.algorithm}."
        )

    else:  # classification
        pred_value = str(raw_pred)
        unit = None

        # Check for class probabilities
        if hasattr(pipeline, "predict_proba"):
            try:
                proba_array = pipeline.predict_proba(input_df)[0]
                estimator = pipeline.named_steps.get("estimator")
                classes = getattr(estimator, "classes_", [])
                if len(classes) == len(proba_array):
                    probabilities = {
                        str(cls_name): round(float(prob), 4)
                        for cls_name, prob in zip(classes, proba_array)
                    }
                    probability_note = "Model probabilities represent uncalibrated relative class scores."
            except Exception as e:
                logger.debug("Failed to calculate predict_proba: %s", e)

        confidence_str = ""
        if probabilities and pred_value in probabilities:
            confidence_str = f" (estimated score: {round(probabilities[pred_value] * 100, 1)}%)"

        explanation = (
            f"Predicted {metadata.target_column} is '{pred_value}'{confidence_str} "
            f"using {metadata.algorithm}."
        )

    return PredictResponse(
        model_id=metadata.model_id,
        prediction=pred_value,
        unit=unit,
        problem_type=metadata.problem_type,
        probabilities=probabilities,
        probability_note=probability_note,
        explanation=explanation,
        warnings=warnings,
    )

