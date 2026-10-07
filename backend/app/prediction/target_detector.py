"""Target detection and validation using semantic intelligence."""
from __future__ import annotations

import re
from typing import Any, Optional
import numpy as np
import pandas as pd

from .models import TargetCandidate

# Patterns for obvious identifier columns that should NOT be prediction targets
_ID_PATTERNS = re.compile(
    r"\b(id|uuid|guid|key|code|hash|token|order_id|customer_id|user_id|client_id|"
    r"txn_id|transaction_id|item_id|sku|asin|session_id|invoice_id)\b",
    re.IGNORECASE,
)


def is_identifier_column(col_name: str, semantic_type: str = "", business_role: str = "") -> bool:
    """Checks whether a column represents an identifier."""
    if semantic_type == "ID":
        return True
    if "identifier" in (business_role or "").lower():
        return True
    norm_name = col_name.strip().lower()
    if _ID_PATTERNS.search(norm_name):
        return True
    if norm_name.endswith("_id") or norm_name.endswith("id"):
        return True
    return False


def detect_target_candidates(
    columns: list[dict], row_count: int
) -> tuple[list[TargetCandidate], list[TargetCandidate]]:
    """Analyzes dataset columns and identifies regression and classification targets."""
    regression_targets: list[TargetCandidate] = []
    classification_targets: list[TargetCandidate] = []

    for c in columns:
        name = c.get("name", "")
        dtype = str(c.get("dtype", "")).lower()
        sem_type = str(c.get("semantic_type", "")).upper()
        role = str(c.get("business_role", "unknown")).lower()
        disp_name = c.get("display_name") or name
        unique_cnt = int(c.get("unique_count") or 0)
        null_cnt = int(c.get("null_count") or 0)
        top_vals = c.get("top_values") or []

        # 1. Skip obvious identifiers and constant/empty columns
        if is_identifier_column(name, sem_type, role):
            continue
        if unique_cnt <= 1 or (row_count > 0 and null_cnt >= row_count):
            continue
        if sem_type == "DATE" or "date" in dtype or "time" in dtype:
            continue
        if sem_type == "TEXT" and unique_cnt > 50:
            continue

        # 2. Regression Candidates: Numeric MEASURE columns with continuous distribution
        is_numeric = any(k in dtype for k in ("int", "float", "double", "decimal", "numeric"))
        if is_numeric and sem_type in ("MEASURE", "DIMENSION"):
            # If unique_count > 5, it qualifies as regression target
            if unique_cnt > 5:
                sample_vals = None
                if c.get("min") is not None and c.get("max") is not None:
                    sample_vals = [c.get("min"), c.get("avg"), c.get("max")]
                regression_targets.append(
                    TargetCandidate(
                        name=name,
                        dtype=dtype,
                        semantic_type=sem_type,
                        business_role=role,
                        display_name=disp_name,
                        problem_type="regression",
                        sample_values=sample_vals,
                    )
                )

        # 3. Classification Candidates: Categorical or discrete discrete columns
        # Object/category or small-cardinality discrete numeric (2 <= unique <= 20)
        if sem_type in ("CATEGORY", "DIMENSION") or (is_numeric and 2 <= unique_cnt <= 10):
            if 2 <= unique_cnt <= 30:
                class_names = [str(tv.get("value")) for tv in top_vals] if top_vals else None
                classification_targets.append(
                    TargetCandidate(
                        name=name,
                        dtype=dtype,
                        semantic_type=sem_type,
                        business_role=role,
                        display_name=disp_name,
                        problem_type="classification",
                        classes=class_names,
                    )
                )

    # Sort targets by suitability priority
    def _reg_priority(cand: TargetCandidate) -> int:
        role = cand.business_role.lower()
        if role in ("duration", "revenue", "sales", "cost", "profit", "monetary_amount", "rating"):
            return 3
        if "amount" in cand.name.lower() or "days" in cand.name.lower() or "price" in cand.name.lower():
            return 2
        return 1

    def _clf_priority(cand: TargetCandidate) -> int:
        role = cand.business_role.lower()
        if role in ("status", "churn", "fraud", "risk"):
            return 3
        if "status" in cand.name.lower() or "churn" in cand.name.lower() or "risk" in cand.name.lower():
            return 3
        if role in ("category", "payment_method", "channel"):
            return 2
        return 1

    regression_targets.sort(key=_reg_priority, reverse=True)
    classification_targets.sort(key=_clf_priority, reverse=True)

    return regression_targets, classification_targets


def validate_target(
    df: pd.DataFrame, target_col: str, problem_type: str
) -> tuple[bool, str]:
    """Validates the target column against ML requirements."""
    if target_col not in df.columns:
        return False, f"Target column '{target_col}' does not exist in dataset."

    series = df[target_col].dropna()
    if len(series) < 10:
        return False, f"Target column '{target_col}' has fewer than 10 non-null values ({len(series)} found)."

    if is_identifier_column(target_col):
        return False, f"Column '{target_col}' is an identifier and cannot be used as a prediction target."

    unique_vals = series.nunique()
    if unique_vals <= 1:
        return False, f"Target column '{target_col}' has no variance (all values are identical: {series.iloc[0] if len(series) > 0 else 'null'})."

    p_type = problem_type.lower()
    if p_type == "regression":
        if not pd.api.types.is_numeric_dtype(series):
            return False, f"Target column '{target_col}' must be numeric for regression, but found {series.dtype}."
        if unique_vals < 3:
            return False, f"Target column '{target_col}' has only {unique_vals} unique values. Consider classification instead."

    elif p_type == "classification":
        if unique_vals > 50:
            return False, f"Target column '{target_col}' has {unique_vals} unique classes, which is too high for classification (max 50)."
        val_counts = series.value_counts()
        single_samples = (val_counts < 2).sum()
        if single_samples > 0 and len(series) >= 20:
            rare_classes = val_counts[val_counts < 2].index.tolist()
            return False, (
                f"Classification target '{target_col}' has classes with fewer than 2 samples: {rare_classes[:5]}. "
                "Each class requires at least 2 samples for reliable train/test evaluation."
            )
    else:
        return False, f"Unsupported problem type '{problem_type}'. Supported: 'regression', 'classification'."

    return True, ""
