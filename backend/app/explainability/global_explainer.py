"""Global model explainability, sample attribution aggregation, and correlation diagnostics."""
from __future__ import annotations

import logging
from typing import Any, Optional
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from .feature_metadata import (
    extract_transformed_feature_names,
    group_global_contributions,
    map_transformed_to_original,
)
from .models import (
    GlobalExplanationResponse,
    GroupedFeatureImportanceItem,
)

logger = logging.getLogger(__name__)


def explain_global_model(
    pipeline: Pipeline,
    original_feature_names: list[str],
    sample_df: pd.DataFrame,
    problem_type: str,
    algorithm: str,
    model_id: str,
    dataset_id: str,
    dataset_version: int,
    max_sample_rows: int = 100,
) -> GlobalExplanationResponse:
    """Computes global feature attribution importance by aggregating grouped record-level contributions."""
    preprocessor = pipeline.named_steps.get("preprocessor")
    estimator = pipeline.named_steps.get("estimator")

    if not preprocessor or not estimator:
        raise ValueError("Invalid pipeline structure: missing preprocessor or estimator.")

    # Bound sample size
    df_eval = sample_df[original_feature_names].copy()
    if len(df_eval) > max_sample_rows:
        df_eval = df_eval.sample(n=max_sample_rows, random_state=42).reset_index(drop=True)

    n_samples = len(df_eval)
    limitations: list[str] = [
        "Global feature importance reflects model decision logic across the sample, not real-world causation.",
    ]
    if n_samples < 20:
        limitations.append(
            f"Evaluated on a small sample of {n_samples} records; importance estimates have elevated variance."
        )

    # Correlation warnings
    corr_warnings: list[str] = []
    correlated_map: dict[str, list[str]] = {}
    num_cols = [c for c in original_feature_names if pd.api.types.is_numeric_dtype(df_eval[c])]
    if len(num_cols) >= 2 and n_samples >= 5:
        try:
            corr_mat = df_eval[num_cols].corr()
            for i in range(len(num_cols)):
                for j in range(i + 1, len(num_cols)):
                    c1, c2 = num_cols[i], num_cols[j]
                    val = corr_mat.loc[c1, c2]
                    if not np.isnan(val) and abs(val) >= 0.85:
                        corr_warnings.append(
                            f"Features '{c1}' and '{c2}' have high correlation (r = {round(val, 2)}). "
                            "Model attribution may be distributed arbitrarily between them."
                        )
                        correlated_map.setdefault(c1, []).append(c2)
                        correlated_map.setdefault(c2, []).append(c1)
        except Exception as e:
            logger.debug("Failed computing correlation warnings: %s", e)

    # 1. Transform sample
    try:
        X_trans = preprocessor.transform(df_eval)
    except Exception as e:
        logger.warning("Failed to transform sample data for global explanation: %s", e)
        # Fall back to Gini / coefficient importance if transform fails
        return _fallback_global_explanation(
            estimator, original_feature_names, algorithm, model_id,
            dataset_id, dataset_version, problem_type, n_samples, corr_warnings, limitations
        )

    transformed_names = extract_transformed_feature_names(preprocessor)
    if not transformed_names:
        transformed_names = [f"feat_{i}" for i in range(X_trans.shape[1])]

    # 2. Compute sample contributions matrix (N x P_original)
    P_orig = len(original_feature_names)
    sample_grouped_matrix = np.zeros((n_samples, P_orig))

    try:
        if hasattr(estimator, "coef_"):
            # Linear / Logistic Regression
            coef = estimator.coef_
            w = coef[0] if coef.ndim > 1 and len(estimator.classes_) == 2 else (coef if coef.ndim == 1 else np.mean(np.abs(coef), axis=0))
            bg_mean = np.mean(X_trans, axis=0)

            # Transformed contribution for each record: (N, n_transformed)
            trans_contribs = (X_trans - bg_mean) * w

            # Group each record into original features
            for row_idx in range(n_samples):
                row_tc = trans_contribs[row_idx]
                for t_name, val in zip(transformed_names, row_tc):
                    parent, _ = map_transformed_to_original(t_name, original_feature_names)
                    if parent in original_feature_names:
                        orig_idx = original_feature_names.index(parent)
                        sample_grouped_matrix[row_idx, orig_idx] += float(val)

            explanation_method = "mean_absolute_linear_attribution"

        elif hasattr(estimator, "estimators_"):
            # Tree Ensembles (RandomForest, GradientBoosting)
            is_rf_reg = hasattr(estimator, "estimators_") and not hasattr(estimator, "classes_") and not hasattr(estimator, "learning_rate")
            is_rf_clf = hasattr(estimator, "estimators_") and hasattr(estimator, "classes_")
            is_gbr = hasattr(estimator, "learning_rate") and not hasattr(estimator, "classes_")
            is_gbc = hasattr(estimator, "learning_rate") and hasattr(estimator, "classes_")

            n_trees = len(estimator.estimators_) if not hasattr(estimator.estimators_, "ravel") else len(estimator.estimators_.ravel())

            for row_idx in range(n_samples):
                x_row = X_trans[row_idx].reshape(1, -1)
                row_raw_contribs = np.zeros(len(transformed_names))

                if is_rf_reg:
                    for est in estimator.estimators_:
                        t = est.tree_
                        path = est.decision_path(x_row).indices
                        for i in range(len(path) - 1):
                            n_cur, n_next = path[i], path[i + 1]
                            f_idx = t.feature[n_cur]
                            if 0 <= f_idx < len(transformed_names):
                                delta = float(t.value[n_next, 0, 0] - t.value[n_cur, 0, 0])
                                row_raw_contribs[f_idx] += delta / n_trees

                elif is_rf_clf:
                    for est in estimator.estimators_:
                        t = est.tree_
                        path = est.decision_path(x_row).indices
                        for i in range(len(path) - 1):
                            n_cur, n_next = path[i], path[i + 1]
                            f_idx = t.feature[n_cur]
                            if 0 <= f_idx < len(transformed_names):
                                # Max class delta shift
                                vc = t.value[n_cur, 0] / np.sum(t.value[n_cur, 0])
                                vn = t.value[n_next, 0] / np.sum(t.value[n_next, 0])
                                delta = float(np.max(np.abs(vn - vc)))
                                row_raw_contribs[f_idx] += delta / n_trees

                elif is_gbr or is_gbc:
                    lr = float(estimator.learning_rate)
                    ests = estimator.estimators_.ravel()
                    for est in ests:
                        t = est.tree_
                        path = est.decision_path(x_row).indices
                        for i in range(len(path) - 1):
                            n_cur, n_next = path[i], path[i + 1]
                            f_idx = t.feature[n_cur]
                            if 0 <= f_idx < len(transformed_names):
                                delta = float(t.value[n_next, 0, 0] - t.value[n_cur, 0, 0])
                                row_raw_contribs[f_idx] += lr * delta

                # Group row
                for t_name, val in zip(transformed_names, row_raw_contribs):
                    parent, _ = map_transformed_to_original(t_name, original_feature_names)
                    if parent in original_feature_names:
                        orig_idx = original_feature_names.index(parent)
                        sample_grouped_matrix[row_idx, orig_idx] += float(val)

            explanation_method = "mean_absolute_tree_path_attribution"

        else:
            return _fallback_global_explanation(
                estimator, original_feature_names, algorithm, model_id,
                dataset_id, dataset_version, problem_type, n_samples, corr_warnings, limitations,
                correlated_map=correlated_map,
            )

        # 3. Aggregate across records
        grouped_items = group_global_contributions(
            sample_grouped_matrix, original_feature_names, correlated_map=correlated_map
        )

        return GlobalExplanationResponse(
            model_id=model_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            problem_type=problem_type,
            algorithm=algorithm,
            explanation_method=explanation_method,
            sample_size=n_samples,
            sample_rows_evaluated=n_samples,
            features=grouped_items,
            feature_importances=grouped_items,
            correlated_features_warning=corr_warnings if corr_warnings else None,
            correlation_warnings=corr_warnings,
            limitations=limitations,
        )

    except Exception as e:
        logger.warning("Error during global attribution calculation: %s", e)
        return _fallback_global_explanation(
            estimator, original_feature_names, algorithm, model_id,
            dataset_id, dataset_version, problem_type, n_samples, corr_warnings, limitations,
            correlated_map=correlated_map,
        )


def _fallback_global_explanation(
    estimator: Any,
    original_feature_names: list[str],
    algorithm: str,
    model_id: str,
    dataset_id: str,
    dataset_version: int,
    problem_type: str,
    sample_size: int,
    corr_warnings: list[str],
    limitations: list[str],
    correlated_map: Optional[dict[str, list[str]]] = None,
) -> GlobalExplanationResponse:
    """Fallback using standard Gini/coefficient importances when sample evaluation cannot run."""
    items: list[GroupedFeatureImportanceItem] = []
    limitations_ext = list(limitations)
    limitations_ext.append("Global importance fell back to tree MDI / coefficient magnitude.")

    raw_scores: np.ndarray = np.ones(len(original_feature_names))
    if hasattr(estimator, "feature_importances_"):
        raw_scores = estimator.feature_importances_
    elif hasattr(estimator, "coef_"):
        coef = estimator.coef_
        raw_scores = np.mean(np.abs(coef), axis=0) if coef.ndim > 1 else np.abs(coef)

    total = float(np.sum(raw_scores))
    for i, orig in enumerate(original_feature_names):
        sc = float(raw_scores[i]) if i < len(raw_scores) else 0.0
        norm_sc = round(sc / total, 4) if total > 0 else 0.0
        corr_feats = correlated_map.get(orig) if correlated_map else None
        items.append(
            GroupedFeatureImportanceItem(
                feature=orig,
                importance=norm_sc,
                relative_share_pct=round(norm_sc * 100.0, 2),
                mean_abs_contribution=round(sc, 6),
                mean_absolute_contribution=round(sc, 6),
                correlated_with=corr_feats,
            )
        )

    items.sort(key=lambda x: x.importance, reverse=True)
    return GlobalExplanationResponse(
        model_id=model_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        problem_type=problem_type,
        algorithm=algorithm,
        explanation_method="model_feature_importance_fallback",
        sample_size=sample_size,
        sample_rows_evaluated=sample_size,
        features=items,
        feature_importances=items,
        correlated_features_warning=corr_warnings if corr_warnings else None,
        correlation_warnings=corr_warnings,
        limitations=limitations_ext,
    )
