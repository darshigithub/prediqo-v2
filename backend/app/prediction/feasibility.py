"""Prediction feasibility analysis for datasets."""
from __future__ import annotations

from typing import Any
from .models import FeasibilityResponse
from .target_detector import detect_target_candidates


def check_feasibility(meta: dict, dataset_id: str) -> FeasibilityResponse:
    """Analyzes whether prediction is feasible for the given dataset metadata."""
    status = meta.get("status", "READY")
    version = int(meta.get("version", 1))
    profile = meta.get("profile", {})
    row_count = int(profile.get("rows", 0))
    columns = meta.get("columns", [])

    warnings: list[str] = []

    if status != "READY":
        return FeasibilityResponse(
            dataset_id=dataset_id,
            dataset_version=version,
            row_count=row_count,
            prediction_possible=False,
            warnings=[f"Dataset status is '{status}'. Prediction requires status to be 'READY'."],
        )

    if row_count < 10:
        return FeasibilityResponse(
            dataset_id=dataset_id,
            dataset_version=version,
            row_count=row_count,
            prediction_possible=False,
            warnings=[f"Dataset contains only {row_count} rows. At least 10 rows are required for ML training."],
        )

    if row_count < 30:
        warnings.append(
            f"Dataset has a small sample size ({row_count} rows). "
            "Model training will work, but model accuracy and generalization may be limited."
        )

    reg_targets, clf_targets = detect_target_candidates(columns, row_count)

    recommended_targets: list[str] = []
    # Pick top recommended targets
    for t in reg_targets[:3]:
        recommended_targets.append(t.name)
    for t in clf_targets[:3]:
        if t.name not in recommended_targets:
            recommended_targets.append(t.name)

    prediction_possible = len(reg_targets) > 0 or len(clf_targets) > 0
    if not prediction_possible:
        warnings.append("No suitable regression or classification target columns found in this dataset.")

    return FeasibilityResponse(
        dataset_id=dataset_id,
        dataset_version=version,
        row_count=row_count,
        prediction_possible=prediction_possible,
        regression_targets=reg_targets,
        classification_targets=clf_targets,
        recommended_targets=recommended_targets,
        warnings=warnings,
    )
