"""Feature metadata extraction, pipeline column tracking, and parent feature grouping."""
from __future__ import annotations

import logging
from typing import Any, Optional
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from .models import FeatureContributionItem, GroupedFeatureImportanceItem, TransformedComponentItem

logger = logging.getLogger(__name__)


def extract_transformed_feature_names(preprocessor: Any) -> list[str]:
    """Retrieves output feature names produced by the ColumnTransformer in preprocessor."""
    try:
        if hasattr(preprocessor, "named_steps"):
            col_trans = preprocessor.named_steps.get("column_transform", preprocessor)
            if col_trans and hasattr(col_trans, "get_feature_names_out"):
                return list(col_trans.get_feature_names_out())
        if hasattr(preprocessor, "get_feature_names_out"):
            return list(preprocessor.get_feature_names_out())
    except Exception as e:
        logger.debug("Could not retrieve feature names out from column transformer: %s", e)
    return []


def map_transformed_to_original(
    transformed_name: str, original_feature_names: list[str]
) -> tuple[str, str]:
    """Maps a transformed column name (e.g., 'cat__city_Mumbai') back to original parent feature ('city').

    Returns:
        (parent_feature, sub_component_name)
    """
    clean = (
        transformed_name
        .replace("num__", "")
        .replace("cat__", "")
        .replace("remainder__", "")
    )

    # 1. Exact match with an original feature
    for orig in original_feature_names:
        if clean == orig:
            return orig, clean

    # 2. Check prefix match (e.g. city_Mumbai -> city, or date_year -> date)
    # Sort original names descending by length so longer column names match before substrings
    sorted_orig = sorted(original_feature_names, key=len, reverse=True)
    for orig in sorted_orig:
        if clean.startswith(f"{orig}_"):
            return orig, clean

    # 3. Check feat_X or feature_X index fallback
    if (clean.startswith("feat_") or clean.startswith("feature_")) and len(original_feature_names) > 0:
        try:
            idx = int(clean.split("_")[1])
            if 0 <= idx < len(original_feature_names):
                return original_feature_names[idx], clean
        except (ValueError, IndexError):
            pass

    # 4. Fallback: return clean name
    return clean, clean


def group_record_contributions(
    transformed_contributions: np.ndarray,
    transformed_names: list[str],
    original_feature_names: list[str],
    raw_feature_values: dict[str, Any],
) -> list[FeatureContributionItem]:
    """Aggregates transformed sub-feature contributions into parent original features for a single record."""
    grouped_map: dict[str, float] = {f: 0.0 for f in original_feature_names}
    components_map: dict[str, list[TransformedComponentItem]] = {f: [] for f in original_feature_names}

    if len(transformed_names) == len(transformed_contributions):
        for t_name, val in zip(transformed_names, transformed_contributions):
            contrib = float(val) if not np.isnan(val) else 0.0
            parent, sub = map_transformed_to_original(t_name, original_feature_names)
            if parent not in grouped_map:
                grouped_map[parent] = 0.0
                components_map[parent] = []
            grouped_map[parent] += contrib
            p_val = raw_feature_values.get(parent)
            components_map[parent].append(
                TransformedComponentItem(
                    name=sub,
                    component=sub,
                    contribution=round(contrib, 6),
                    value=p_val,
                    raw_value=p_val,
                )
            )
    else:
        # Fallback if names mismatch: map by index
        for idx, val in enumerate(transformed_contributions):
            contrib = float(val) if not np.isnan(val) else 0.0
            orig = original_feature_names[idx] if idx < len(original_feature_names) else f"feature_{idx}"
            grouped_map[orig] = grouped_map.get(orig, 0.0) + contrib

    total_abs = sum(abs(v) for v in grouped_map.values())
    items: list[FeatureContributionItem] = []

    for feat, contrib in grouped_map.items():
        val = round(contrib, 6)
        if abs(val) < 1e-9:
            direction = "NEUTRAL"
        elif val > 0:
            direction = "POSITIVE"
        else:
            direction = "NEGATIVE"

        rel_pct = round((abs(val) / total_abs) * 100.0, 2) if total_abs > 0 else 0.0
        comps = components_map.get(feat)
        raw_val = raw_feature_values.get(feat)
        items.append(
            FeatureContributionItem(
                feature=feat,
                contribution=val,
                feature_value=raw_val,
                raw_value=raw_val,
                direction=direction,
                relative_weight_pct=rel_pct,
                transformed_components=comps if comps and len(comps) > 1 else None,
            )
        )

    # Sort descending by absolute contribution magnitude
    items.sort(key=lambda x: abs(x.contribution), reverse=True)
    return items


def group_global_contributions(
    sample_grouped_matrix: np.ndarray,
    original_feature_names: list[str],
    correlated_map: Optional[dict[str, list[str]]] = None,
) -> list[GroupedFeatureImportanceItem]:
    """Aggregates multi-record local contributions into global feature importance.

    Computes Mean Absolute Contribution across sample records after summing
    one-hot components per record, adhering strictly to Phase 4A requirements.
    """
    n_samples, n_feats = sample_grouped_matrix.shape
    mean_abs_arr = np.mean(np.abs(sample_grouped_matrix), axis=0)
    total_mean_abs = float(np.sum(mean_abs_arr))

    items: list[GroupedFeatureImportanceItem] = []
    for i, orig in enumerate(original_feature_names):
        m_abs = float(mean_abs_arr[i])
        norm_imp = round(m_abs / total_mean_abs, 4) if total_mean_abs > 0 else 0.0
        rel_pct = round(norm_imp * 100.0, 2)
        corr_feats = correlated_map.get(orig) if correlated_map else None
        items.append(
            GroupedFeatureImportanceItem(
                feature=orig,
                importance=norm_imp,
                relative_share_pct=rel_pct,
                mean_abs_contribution=round(m_abs, 6),
                mean_absolute_contribution=round(m_abs, 6),
                correlated_with=corr_feats if corr_feats else None,
            )
        )

    items.sort(key=lambda x: x.importance, reverse=True)
    return items
