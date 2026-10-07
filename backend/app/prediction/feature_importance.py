"""Feature importance extraction and transformation mapping."""
from __future__ import annotations

import logging
from typing import Any
import numpy as np
from sklearn.pipeline import Pipeline

from .models import FeatureImportanceItem

logger = logging.getLogger(__name__)


def extract_feature_importance(
    pipeline: Pipeline,
    original_feature_names: list[str],
) -> list[FeatureImportanceItem]:
    """Extracts feature importances or coefficient magnitudes and maps one-hot features back to original columns."""
    try:
        preprocessor = pipeline.named_steps.get("preprocessor")
        estimator = pipeline.named_steps.get("estimator")

        if not estimator:
            return []

        # 1. Retrieve raw feature importances / coefficients from estimator
        raw_importances: np.ndarray | None = None
        if hasattr(estimator, "feature_importances_"):
            raw_importances = estimator.feature_importances_
        elif hasattr(estimator, "coef_"):
            coef = estimator.coef_
            if coef.ndim > 1:
                # Multiclass logistic regression: take mean magnitude across classes
                raw_importances = np.mean(np.abs(coef), axis=0)
            else:
                raw_importances = np.abs(coef)

        if raw_importances is None or len(raw_importances) == 0:
            return []

        # 2. Extract transformed feature names from ColumnTransformer
        transformed_names: list[str] = []
        if preprocessor and hasattr(preprocessor, "named_steps"):
            col_trans = preprocessor.named_steps.get("column_transform")
            if col_trans and hasattr(col_trans, "get_feature_names_out"):
                try:
                    transformed_names = list(col_trans.get_feature_names_out())
                except Exception:
                    pass

        # 3. Map transformed names back to original column names
        aggregated: dict[str, float] = {col: 0.0 for col in original_feature_names}

        if transformed_names and len(transformed_names) == len(raw_importances):
            for t_name, imp_val in zip(transformed_names, raw_importances):
                val = float(imp_val) if not np.isnan(imp_val) else 0.0
                clean_name = t_name.replace("num__", "").replace("cat__", "").replace("remainder__", "")

                # Check which original feature this corresponds to
                matched = False
                for orig in original_feature_names:
                    if clean_name == orig or clean_name.startswith(f"{orig}_"):
                        aggregated[orig] += val
                        matched = True
                        break
                if not matched:
                    # Fallback to direct name or first match
                    aggregated[clean_name] = aggregated.get(clean_name, 0.0) + val
        else:
            # Fallback if transformed names not available or lengths mismatch
            for i, val in enumerate(raw_importances):
                if i < len(original_feature_names):
                    orig = original_feature_names[i]
                    aggregated[orig] += float(val)

        # 4. Normalize to sum to 1.0 (or proportion)
        total = sum(aggregated.values())
        items: list[FeatureImportanceItem] = []
        for feat, score in aggregated.items():
            norm_score = round(score / total, 4) if total > 0 else 0.0
            items.append(FeatureImportanceItem(feature=feat, importance=norm_score))

        # Sort descending
        items.sort(key=lambda x: x.importance, reverse=True)
        return items

    except Exception as e:
        logger.warning("Could not extract feature importance: %s", e)
        return []
