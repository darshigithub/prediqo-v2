"""Evaluation and selection of candidate machine learning models."""
from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.pipeline import Pipeline

from .models import BestModelSummary, CandidateModelResult

logger = logging.getLogger(__name__)


def evaluate_models(
    models: dict[str, Pipeline],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    problem_type: str,
) -> tuple[list[CandidateModelResult], str, BestModelSummary]:
    """Evaluates candidate models on the test set and selects the best model."""
    p_type = problem_type.lower()
    candidate_results: list[CandidateModelResult] = []

    best_name: str = ""
    best_primary_val: float = float("inf") if p_type == "regression" else -1.0
    best_metrics: dict[str, Any] = {}

    for name, pipe in models.items():
        try:
            preds = pipe.predict(X_test)

            if p_type == "regression":
                mae = float(mean_absolute_error(y_test, preds))
                mse = float(mean_squared_error(y_test, preds))
                rmse = float(np.sqrt(mse))
                r2 = float(r2_score(y_test, preds))

                metrics = {
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "r2": round(r2, 4),
                }

                # Lowest MAE is best
                is_better = mae < best_primary_val
                if is_better:
                    best_primary_val = mae
                    best_name = name
                    best_metrics = metrics

            else:  # classification
                acc = float(accuracy_score(y_test, preds))
                prec = float(precision_score(y_test, preds, average="weighted", zero_division=0))
                rec = float(recall_score(y_test, preds, average="weighted", zero_division=0))
                f1 = float(f1_score(y_test, preds, average="weighted", zero_division=0))

                metrics = {
                    "accuracy": round(acc, 4),
                    "precision": round(prec, 4),
                    "recall": round(rec, 4),
                    "f1": round(f1, 4),
                    "averaging": "weighted",
                }

                # Highest F1 is best
                is_better = f1 > best_primary_val
                if is_better:
                    best_primary_val = f1
                    best_name = name
                    best_metrics = metrics

            candidate_results.append(
                CandidateModelResult(
                    algorithm=name,
                    metrics=metrics,
                    is_best=False,
                )
            )

        except Exception as e:
            logger.warning("Evaluation failed for candidate %s: %s", name, e)

    if not best_name and candidate_results:
        best_name = candidate_results[0].algorithm
        best_metrics = candidate_results[0].metrics
        best_primary_val = best_metrics.get("mae", 0.0) if p_type == "regression" else best_metrics.get("f1", 0.0)

    # Mark is_best on the winning candidate
    for cand in candidate_results:
        if cand.algorithm == best_name:
            cand.is_best = True

    primary_metric_name = "mae" if p_type == "regression" else "f1"
    best_summary = BestModelSummary(
        algorithm=best_name,
        primary_metric=primary_metric_name,
        primary_metric_value=round(best_primary_val, 4),
        metrics=best_metrics,
    )

    return candidate_results, best_name, best_summary
