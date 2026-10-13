"""Feature recommendation, exclusion, and leakage prevention heuristics."""
from __future__ import annotations

import re
from typing import Any
from .target_detector import is_identifier_column

# Potential data leakage keyword heuristics based on common business processes
_LEAKAGE_PAIRS = [
    (r"\b(delivery_days|delivery_time|transit_days|shipping_days)\b",
     r"\b(actual_delivery_date|delivered_at|delivery_status|delivered_date|delivery_date|ship_date)\b"),
    (r"\b(order_status|status|payment_status)\b",
     r"\b(cancellation_reason|refund_amount|return_date|chargeback|delivered_date)\b"),
    (r"\b(churn|is_churn|churned)\b",
     r"\b(churn_date|churn_reason|cancellation_date|exit_date)\b"),
    (r"\b(fraud|is_fraud)\b",
     r"\b(fraud_reason|investigation_status|chargeback_flag)\b"),
]


def check_leakage_warning(target_col: str, feature_col: str) -> str | None:
    """Detects likely data leakage between a predictor feature and target."""
    t_clean = target_col.strip().lower()
    f_clean = feature_col.strip().lower()

    if t_clean == f_clean:
        return f"Feature '{feature_col}' is the target itself."

    for target_pattern, leak_pattern in _LEAKAGE_PAIRS:
        if re.search(target_pattern, t_clean):
            if re.search(leak_pattern, f_clean):
                return (
                    f"Warning: Column '{feature_col}' may cause data leakage when predicting '{target_col}' "
                    "as it appears to be a post-outcome or fulfillment timestamp/status."
                )

    # Substring check for post-outcome indicators
    if t_clean in f_clean and any(s in f_clean for s in ("actual", "final", "post", "result", "outcome")):
        return f"Warning: Column '{feature_col}' may contain post-outcome information related to '{target_col}'."

    return None


def check_correlation_leakage(
    df: Any, target_col: str, feature_cols: list[str], threshold: float = 0.98
) -> list[str]:
    """Detects suspiciously high numeric correlations between features and target."""
    warnings: list[str] = []
    if target_col not in df.columns:
        return warnings

    target_s = df[target_col]
    if not (hasattr(target_s, "dtype") and any(k in str(target_s.dtype).lower() for k in ("int", "float", "double"))):
        return warnings

    for feat in feature_cols:
        if feat == target_col or feat not in df.columns:
            continue
        feat_s = df[feat]
        if hasattr(feat_s, "dtype") and any(k in str(feat_s.dtype).lower() for k in ("int", "float", "double")):
            try:
                corr = float(target_s.corr(feat_s))
                if not (corr != corr) and abs(corr) >= threshold:  # check not NaN
                    warnings.append(
                        f"Warning: Feature '{feat}' has an extremely high correlation ({round(corr, 3)}) with target '{target_col}', "
                        "which may indicate direct mathematical derivation or target leakage."
                    )
            except Exception:
                pass

    return warnings



def recommend_features(
    columns: list[dict], target_col: str, row_count: int
) -> tuple[list[str], list[str], list[str]]:
    """Separates columns into recommended vs excluded features, and collects leakage warnings."""
    recommended: list[str] = []
    excluded: list[str] = []
    leakage_warnings: list[str] = []

    t_norm = target_col.strip().lower()

    for c in columns:
        name = c.get("name", "")
        n_norm = name.strip().lower()
        dtype = str(c.get("dtype", "")).lower()
        sem_type = str(c.get("semantic_type", "")).upper()
        role = str(c.get("business_role", "unknown")).lower()
        unique_cnt = int(c.get("unique_count") or 0)
        null_cnt = int(c.get("null_count") or 0)

        # 1. Target column must always be excluded
        if n_norm == t_norm:
            excluded.append(name)
            continue

        # 2. Exclude identifiers
        if is_identifier_column(name, sem_type, role):
            excluded.append(name)
            continue

        # 3. Exclude completely missing columns
        if row_count > 0 and null_cnt >= row_count:
            excluded.append(name)
            continue

        # 4. Exclude constant columns
        if unique_cnt <= 1:
            excluded.append(name)
            continue

        # 5. Exclude extreme-cardinality text columns
        is_numeric = any(k in dtype for k in ("int", "float", "double", "decimal", "numeric"))
        if not is_numeric and sem_type != "DATE":
            if unique_cnt > 100 or (row_count > 50 and unique_cnt / max(row_count, 1) > 0.8):
                excluded.append(name)
                continue

        # 6. Check potential data leakage
        leak_msg = check_leakage_warning(target_col, name)
        if leak_msg:
            leakage_warnings.append(leak_msg)

        # Column passes rules
        recommended.append(name)

    return recommended, excluded, leakage_warnings


def validate_selected_features(
    selected_features: list[str], available_columns: list[str], target_col: str
) -> tuple[bool, str]:
    """Validates user-selected feature names against dataset metadata."""
    if not selected_features:
        return False, "At least one feature column must be selected for model training."

    avail_set = set(available_columns)
    for feat in selected_features:
        if feat not in avail_set:
            return False, f"Selected feature '{feat}' does not exist in dataset."
        if feat.strip().lower() == target_col.strip().lower():
            return False, f"Feature '{feat}' cannot be identical to target column '{target_col}'."

    return True, ""
