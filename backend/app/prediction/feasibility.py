"""Prediction feasibility analysis for datasets."""
from __future__ import annotations

from typing import Any
from .models import ColumnInfoItem, DataQualitySummary, FeasibilityResponse
from .target_detector import detect_target_candidates
from .predictor import infer_unit_from_target


def check_feasibility(meta: dict, dataset_id: str) -> FeasibilityResponse:
    """Analyzes whether prediction is feasible for the given dataset metadata."""
    status = meta.get("status", "READY")
    version = int(meta.get("version", 1))
    profile = meta.get("profile", {})
    row_count = int(profile.get("rows", 0))
    columns = meta.get("columns", [])

    warnings: list[str] = []

    # Calculate Data Quality & Column Details
    columns_info: list[ColumnInfoItem] = []
    cols_with_nulls = 0
    total_null_cells = 0
    total_cells = max(1, row_count * max(1, len(columns)))

    for c in columns:
        c_name = c.get("name", "")
        null_cnt = int(c.get("null_count") or 0)
        if null_cnt > 0:
            cols_with_nulls += 1
            total_null_cells += null_cnt
        null_pct = round((null_cnt / max(1, row_count)) * 100.0, 1)

        sample_vals = None
        if c.get("top_values"):
            sample_vals = [tv.get("value") for tv in c["top_values"][:3] if isinstance(tv, dict)]
        elif c.get("min") is not None and c.get("max") is not None:
            sample_vals = [c.get("min"), c.get("avg"), c.get("max")]

        columns_info.append(
            ColumnInfoItem(
                name=c_name,
                display_name=c.get("display_name") or c_name,
                dtype=str(c.get("dtype", "")).lower(),
                semantic_type=str(c.get("semantic_type", "")).upper() or "DIMENSION",
                business_role=str(c.get("business_role", "")).lower() or "attribute",
                unique_count=int(c.get("unique_count") or 0),
                null_count=null_cnt,
                null_percentage=null_pct,
                sample_values=sample_vals,
                unit=infer_unit_from_target(c_name, ""),
            )
        )

    completeness_pct = round(max(0.0, min(100.0, ((total_cells - total_null_cells) / total_cells) * 100.0)), 1)
    quality_notes: list[str] = [
        f"Dataset contains {row_count:,} observations across {len(columns)} tracked features.",
    ]
    if cols_with_nulls == 0:
        quality_grade = "Excellent" if row_count >= 50 else "Good"
        quality_notes.append("100% complete data cells with zero missing values.")
    elif completeness_pct >= 95.0:
        quality_grade = "Good"
        quality_notes.append(f"{cols_with_nulls} column(s) contain missing values (overall {completeness_pct}% cell completeness).")
    elif completeness_pct >= 80.0:
        quality_grade = "Needs Attention"
        quality_notes.append(f"Noticeable missing data: {cols_with_nulls} column(s) have empty cells ({completeness_pct}% cell completeness).")
    else:
        quality_grade = "Insufficient"
        quality_notes.append(f"High missingness: only {completeness_pct}% of cells are populated.")

    if row_count < 30:
        quality_notes.append(f"Small sample size ({row_count} rows); model predictions will have elevated uncertainty.")

    data_quality = DataQualitySummary(
        total_rows=row_count,
        total_columns=len(columns),
        complete_rows_pct=completeness_pct,
        columns_with_nulls=cols_with_nulls,
        quality_grade=quality_grade,
        quality_notes=quality_notes,
    )

    if status != "READY":
        return FeasibilityResponse(
            dataset_id=dataset_id,
            dataset_version=version,
            row_count=row_count,
            prediction_possible=False,
            data_quality=data_quality,
            columns_info=columns_info,
            warnings=[f"Dataset status is '{status}'. Prediction requires status to be 'READY'."],
        )

    if row_count < 10:
        return FeasibilityResponse(
            dataset_id=dataset_id,
            dataset_version=version,
            row_count=row_count,
            prediction_possible=False,
            data_quality=data_quality,
            columns_info=columns_info,
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
        data_quality=data_quality,
        columns_info=columns_info,
        warnings=warnings,
    )
