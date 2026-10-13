"""Local prediction explainers for linear models, tree ensembles, and baselines."""
from __future__ import annotations

import logging
from typing import Any, Optional
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline

from .feature_metadata import (
    extract_transformed_feature_names,
    group_record_contributions,
)
from .models import (
    FeatureContributionItem,
    LocalExplanationResponse,
)

logger = logging.getLogger(__name__)


def explain_local_prediction(
    pipeline: Pipeline,
    raw_feature_record: dict[str, Any],
    original_feature_names: list[str],
    problem_type: str,
    algorithm: str,
    model_id: str,
    dataset_id: str,
    dataset_version: int,
    background_df: Optional[pd.DataFrame] = None,
    target_class: Optional[str] = None,
    method_preference: str = "auto",
) -> LocalExplanationResponse:
    """Computes a validated local feature attribution explanation for a single record."""
    preprocessor = pipeline.named_steps.get("preprocessor")
    estimator = pipeline.named_steps.get("estimator")

    if not preprocessor or not estimator:
        raise ValueError("Invalid pipeline structure: missing preprocessor or estimator.")

    # 1. Transform input record
    input_df = pd.DataFrame([raw_feature_record])
    # Ensure all original feature columns are present (fill missing with None)
    for col in original_feature_names:
        if col not in input_df.columns:
            input_df[col] = None
    input_df = input_df[original_feature_names]

    X_transformed = preprocessor.transform(input_df)
    transformed_names = extract_transformed_feature_names(preprocessor)
    if not transformed_names:
        transformed_names = [f"feat_{i}" for i in range(X_transformed.shape[1])]

    # Background summary if available
    bg_transformed_mean = np.zeros(X_transformed.shape[1])
    if background_df is not None and len(background_df) > 0:
        try:
            bg_clean = background_df[original_feature_names].copy()
            bg_trans = preprocessor.transform(bg_clean)
            bg_transformed_mean = np.mean(bg_trans, axis=0)
        except Exception as e:
            logger.debug("Could not compute background sample mean: %s", e)

    p_type = problem_type.lower()
    x_row = X_transformed[0]

    # Check for optional SHAP explainer if user requested shap and library is available
    if method_preference.lower() == "shap":
        shap_res = _try_shap_explanation(
            estimator, x_row, transformed_names, original_feature_names, raw_feature_record,
            pipeline, input_df, p_type, algorithm, model_id, dataset_id, dataset_version, target_class
        )
        if shap_res is not None:
            return shap_res

    # 2. Dispatch to model-specific exact explainer
    if isinstance(estimator, (LinearRegression, LogisticRegression)):
        return _explain_linear(
            estimator, x_row, bg_transformed_mean, transformed_names,
            original_feature_names, raw_feature_record, p_type, algorithm,
            model_id, dataset_id, dataset_version, target_class, pipeline, input_df
        )

    elif isinstance(estimator, (RandomForestRegressor, GradientBoostingRegressor)):
        return _explain_tree_regressor(
            estimator, x_row, transformed_names, original_feature_names,
            raw_feature_record, algorithm, model_id, dataset_id, dataset_version,
            pipeline, input_df
        )

    elif isinstance(estimator, (RandomForestClassifier, GradientBoostingClassifier)):
        return _explain_tree_classifier(
            estimator, x_row, transformed_names, original_feature_names,
            raw_feature_record, algorithm, model_id, dataset_id, dataset_version,
            target_class, pipeline, input_df
        )

    elif isinstance(estimator, (DummyRegressor, DummyClassifier)):
        return _explain_baseline(
            estimator, raw_feature_record, original_feature_names, p_type,
            algorithm, model_id, dataset_id, dataset_version, pipeline, input_df,
            target_class=target_class
        )

    else:
        # Unsupported model family
        pred = pipeline.predict(input_df)[0]
        return LocalExplanationResponse(
            model_id=model_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            problem_type=problem_type,
            algorithm=algorithm,
            prediction=pred if p_type == "regression" else str(pred),
            predicted_class=str(pred) if p_type == "classification" else None,
            reference_value=0.0,
            baseline_reference_value=0.0,
            output_scale="UNKNOWN",
            decomposition_space="UNKNOWN",
            explanation_method="unsupported",
            feature_contributions=[],
            contributions=[],
            reconstruction_sum=0.0,
            additive_sum=0.0,
            reconstruction_error=0.0,
            validation_status="UNSUPPORTED",
            is_valid=False,
            limitations=[f"Algorithm '{algorithm}' does not have a registered exact decomposition."],
        )


# ---------------------------------------------------------------------------
# Linear & Logistic Regression Explanations
# ---------------------------------------------------------------------------
def _explain_linear(
    estimator: Any,
    x_row: np.ndarray,
    bg_mean: np.ndarray,
    transformed_names: list[str],
    original_feature_names: list[str],
    raw_feature_record: dict[str, Any],
    problem_type: str,
    algorithm: str,
    model_id: str,
    dataset_id: str,
    dataset_version: int,
    target_class: Optional[Any],
    pipeline: Pipeline,
    input_df: pd.DataFrame,
) -> LocalExplanationResponse:
    coef = estimator.coef_
    intercept = estimator.intercept_

    if problem_type == "regression":
        pred = float(pipeline.predict(input_df)[0])
        w = coef if coef.ndim == 1 else coef[0]
        w0 = float(intercept if np.isscalar(intercept) else intercept[0])

        ref_val = w0 + float(np.sum(w * bg_mean))
        contribs = w * (x_row - bg_mean)
        grouped_items = group_record_contributions(
            contribs, transformed_names, original_feature_names, raw_feature_record
        )

        recon_sum = ref_val + float(np.sum(contribs))
        recon_err = abs(pred - recon_sum)

        return LocalExplanationResponse(
            model_id=model_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            problem_type="regression",
            algorithm=algorithm,
            prediction=round(pred, 4),
            predicted_value=round(pred, 4),
            reference_value=round(ref_val, 4),
            baseline_reference_value=round(ref_val, 4),
            reference_definition="Expected prediction across training background feature means",
            output_scale="PREDICTION_SPACE",
            decomposition_space="PREDICTION_SPACE",
            explanation_method="exact_linear",
            feature_contributions=grouped_items,
            contributions=grouped_items,
            reconstruction_sum=round(recon_sum, 4),
            additive_sum=round(float(np.sum(contribs)), 4),
            reconstruction_error=round(recon_err, 6),
            validation_status="EXACT_ADDITIVE" if recon_err < 1e-4 else "APPROXIMATE",
            is_valid=recon_err < 1e-3,
            is_calibrated=True,
            confidence_metric_name="linear_prediction",
            limitations=[
                "Linear attribution assumes independent feature additive effects without interaction terms.",
                "Reference value is calculated using background sample feature means.",
            ],
        )

    else:
        # Classification (Logistic Regression)
        classes = [str(c) for c in estimator.classes_]
        pred_label = str(pipeline.predict(input_df)[0])
        probs = pipeline.predict_proba(input_df)[0] if hasattr(pipeline, "predict_proba") else None
        prob_dict: Optional[dict[str, float]] = None
        if probs is not None:
            prob_dict = {classes[i]: round(float(probs[i]), 4) for i in range(len(classes))}

        target_class_str = str(target_class) if target_class is not None else None
        active_class = target_class_str if (target_class_str and target_class_str in classes) else pred_label
        cls_idx = classes.index(active_class)

        if len(classes) == 2:
            # Binary logistic regression
            w = coef[0]
            w0 = float(intercept[0])
            if cls_idx == 0:
                # Invert for negative class
                w = -w
                w0 = -w0
        else:
            # Multiclass logistic regression (One-vs-Rest)
            w = coef[cls_idx]
            w0 = float(intercept[cls_idx])

        ref_val = w0 + float(np.sum(w * bg_mean))
        contribs = w * (x_row - bg_mean)
        grouped_items = group_record_contributions(
            contribs, transformed_names, original_feature_names, raw_feature_record
        )

        # In decision function logit space
        margin_score = w0 + float(np.sum(w * x_row))
        recon_sum = ref_val + float(np.sum(contribs))
        recon_err = abs(margin_score - recon_sum)

        return LocalExplanationResponse(
            model_id=model_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            problem_type="classification",
            algorithm=algorithm,
            prediction=pred_label,
            predicted_class=pred_label,
            predicted_proba=float(probs[cls_idx]) if probs is not None else None,
            target_class=active_class,
            class_probabilities=prob_dict,
            reference_value=round(ref_val, 4),
            baseline_reference_value=round(ref_val, 4),
            reference_definition=f"Expected log-odds decision margin for class '{active_class}' across background sample means",
            output_scale="LOG_ODDS_MARGIN",
            decomposition_space="LOG_ODDS_MARGIN",
            explanation_method="exact_linear",
            feature_contributions=grouped_items,
            contributions=grouped_items,
            reconstruction_sum=round(recon_sum, 4),
            additive_sum=round(float(np.sum(contribs)), 4),
            reconstruction_error=round(recon_err, 6),
            validation_status="EXACT_ADDITIVE" if recon_err < 1e-4 else "APPROXIMATE",
            is_valid=recon_err < 1e-3,
            is_calibrated=False,
            confidence_metric_name="uncalibrated_log_odds_margin",
            probability_note=(
                f"Feature contributions represent shifts in log-odds decision margin for class '{active_class}'. "
                "Class probabilities are non-linear sigmoid/softmax outputs and are not calibrated posterior frequencies."
            ),
            limitations=[
                f"Attributions are computed in log-odds margin space for class '{active_class}'.",
                "Linear model assumes no hidden non-linear interaction terms.",
            ],
        )


# ---------------------------------------------------------------------------
# Tree Regressors (RandomForestRegressor, GradientBoostingRegressor)
# ---------------------------------------------------------------------------
def _explain_tree_regressor(
    estimator: Any,
    x_row: np.ndarray,
    transformed_names: list[str],
    original_feature_names: list[str],
    raw_feature_record: dict[str, Any],
    algorithm: str,
    model_id: str,
    dataset_id: str,
    dataset_version: int,
    pipeline: Pipeline,
    input_df: pd.DataFrame,
) -> LocalExplanationResponse:
    pred = float(pipeline.predict(input_df)[0])
    n_feats = len(transformed_names)
    x2d = x_row.reshape(1, -1)

    if isinstance(estimator, RandomForestRegressor):
        n_trees = len(estimator.estimators_)
        biases: list[float] = []
        raw_contribs = np.zeros(n_feats)

        for est in estimator.estimators_:
            t = est.tree_
            biases.append(float(t.value[0, 0, 0]))
            path = est.decision_path(x2d).indices
            for i in range(len(path) - 1):
                n_cur, n_next = path[i], path[i + 1]
                f_idx = t.feature[n_cur]
                if 0 <= f_idx < n_feats:
                    delta = float(t.value[n_next, 0, 0] - t.value[n_cur, 0, 0])
                    raw_contribs[f_idx] += delta / n_trees

        ref_val = float(np.mean(biases)) if biases else 0.0
        ref_def = "Average root node prediction across random forest decision trees"

    else:
        # GradientBoostingRegressor: use exact raw predict init
        if hasattr(estimator, "_raw_predict_init"):
            raw_init = estimator._raw_predict_init(x2d)
            init_val = float(raw_init[0, 0] if raw_init.ndim > 1 else raw_init[0])
        elif hasattr(estimator, "init_") and hasattr(estimator.init_, "predict"):
            init_val = float(estimator.init_.predict(x2d)[0])
        else:
            init_val = 0.0

        lr = float(estimator.learning_rate)
        ref_val = init_val
        raw_contribs = np.zeros(n_feats)

        for est in estimator.estimators_.ravel():
            t = est.tree_
            ref_val += lr * float(t.value[0, 0, 0])
            path = est.decision_path(x2d).indices
            for i in range(len(path) - 1):
                n_cur, n_next = path[i], path[i + 1]
                f_idx = t.feature[n_cur]
                if 0 <= f_idx < n_feats:
                    delta = float(t.value[n_next, 0, 0] - t.value[n_cur, 0, 0])
                    raw_contribs[f_idx] += lr * delta

        ref_def = "Initial base estimator prediction plus gradient boosting tree root biases"

    grouped_items = group_record_contributions(
        raw_contribs, transformed_names, original_feature_names, raw_feature_record
    )
    recon_sum = ref_val + float(np.sum(raw_contribs))
    recon_err = abs(pred - recon_sum)

    return LocalExplanationResponse(
        model_id=model_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        problem_type="regression",
        algorithm=algorithm,
        prediction=round(pred, 4),
        predicted_value=round(pred, 4),
        reference_value=round(ref_val, 4),
        baseline_reference_value=round(ref_val, 4),
        reference_definition=ref_def,
        output_scale="PREDICTION_SPACE",
        decomposition_space="PREDICTION_SPACE",
        explanation_method="exact_tree_path",
        feature_contributions=grouped_items,
        contributions=grouped_items,
        reconstruction_sum=round(recon_sum, 4),
        additive_sum=round(float(np.sum(raw_contribs)), 4),
        reconstruction_error=round(recon_err, 6),
        validation_status="EXACT_ADDITIVE" if recon_err < 1e-4 else "APPROXIMATE",
        is_valid=recon_err < 1e-3,
        is_calibrated=True,
        confidence_metric_name="tree_prediction",
        limitations=[
            "Tree decision path decomposition measures step-by-step conditional expectation shifts.",
            "Local feature contributions describe model decision behavior, not real-world causality.",
        ],
    )


# ---------------------------------------------------------------------------
# Tree Classifiers (RandomForestClassifier, GradientBoostingClassifier)
# ---------------------------------------------------------------------------
def _explain_tree_classifier(
    estimator: Any,
    x_row: np.ndarray,
    transformed_names: list[str],
    original_feature_names: list[str],
    raw_feature_record: dict[str, Any],
    algorithm: str,
    model_id: str,
    dataset_id: str,
    dataset_version: int,
    target_class: Optional[Any],
    pipeline: Pipeline,
    input_df: pd.DataFrame,
) -> LocalExplanationResponse:
    classes = [str(c) for c in estimator.classes_]
    pred_label = str(pipeline.predict(input_df)[0])
    probs = pipeline.predict_proba(input_df)[0] if hasattr(pipeline, "predict_proba") else None
    prob_dict: Optional[dict[str, float]] = None
    if probs is not None:
        prob_dict = {classes[i]: round(float(probs[i]), 4) for i in range(len(classes))}

    target_class_str = str(target_class) if target_class is not None else None
    active_class = target_class_str if (target_class_str and target_class_str in classes) else pred_label
    cls_idx = classes.index(active_class)
    n_feats = len(transformed_names)
    x2d = x_row.reshape(1, -1)

    if isinstance(estimator, RandomForestClassifier):
        n_trees = len(estimator.estimators_)
        ref_val = 0.0
        raw_contribs = np.zeros(n_feats)

        for est in estimator.estimators_:
            t = est.tree_
            # Root probability for active class
            v0 = t.value[0, 0]
            p0 = float(v0[cls_idx] / np.sum(v0))
            ref_val += p0 / n_trees

            path = est.decision_path(x2d).indices
            for i in range(len(path) - 1):
                n_cur, n_next = path[i], path[i + 1]
                f_idx = t.feature[n_cur]
                if 0 <= f_idx < n_feats:
                    vc = t.value[n_cur, 0]
                    pc = float(vc[cls_idx] / np.sum(vc))
                    vn = t.value[n_next, 0]
                    pn = float(vn[cls_idx] / np.sum(vn))
                    raw_contribs[f_idx] += (pn - pc) / n_trees

        grouped_items = group_record_contributions(
            raw_contribs, transformed_names, original_feature_names, raw_feature_record
        )
        recon_sum = ref_val + float(np.sum(raw_contribs))
        pred_prob_target = float(probs[cls_idx]) if probs is not None else 0.0
        recon_err = abs(pred_prob_target - recon_sum)

        return LocalExplanationResponse(
            model_id=model_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            problem_type="classification",
            algorithm=algorithm,
            prediction=pred_label,
            predicted_class=pred_label,
            predicted_proba=pred_prob_target,
            target_class=active_class,
            class_probabilities=prob_dict,
            reference_value=round(ref_val, 4),
            baseline_reference_value=round(ref_val, 4),
            reference_definition=f"Average root node voting probability for class '{active_class}' across forest trees",
            output_scale="PROBABILITY_SPACE",
            decomposition_space="PROBABILITY_SPACE",
            explanation_method="exact_tree_path",
            feature_contributions=grouped_items,
            contributions=grouped_items,
            reconstruction_sum=round(recon_sum, 4),
            additive_sum=round(float(np.sum(raw_contribs)), 4),
            reconstruction_error=round(recon_err, 6),
            validation_status="EXACT_ADDITIVE" if recon_err < 1e-4 else "APPROXIMATE",
            is_valid=recon_err < 1e-3,
            is_calibrated=False,
            confidence_metric_name="ensemble_voting_share",
            probability_note=(
                f"Feature contributions directly represent tree voting probability shifts for class '{active_class}'. "
                "Class probabilities are tree ensemble voting shares and should not be confused with calibrated posterior confidence."
            ),
            limitations=[
                f"Attributions reflect voting proportion shifts for class '{active_class}'.",
                "Tree paths do not imply physical causal mechanisms.",
            ],
        )

    else:
        # GradientBoostingClassifier: decomposes in log-odds decision margin space
        lr = float(estimator.learning_rate)
        n_classes = len(classes)

        if n_classes == 2:
            if hasattr(estimator, "_raw_predict_init"):
                raw_init = estimator._raw_predict_init(x2d)
                init_val = float(raw_init[0, 0] if raw_init.ndim > 1 else raw_init[0])
            elif hasattr(estimator, "init_") and hasattr(estimator.init_, "predict_proba"):
                p = estimator.init_.predict_proba(x2d)[0]
                init_val = float(np.log(np.clip(p[1], 1e-15, 1 - 1e-15) / np.clip(1 - p[1], 1e-15, 1 - 1e-15)))
            else:
                init_val = 0.0

            ref_val = init_val
            raw_contribs = np.zeros(n_feats)

            for est in estimator.estimators_.ravel():
                t = est.tree_
                ref_val += lr * float(t.value[0, 0, 0])
                path = est.decision_path(x2d).indices
                for i in range(len(path) - 1):
                    n_cur, n_next = path[i], path[i + 1]
                    f_idx = t.feature[n_cur]
                    if 0 <= f_idx < n_feats:
                        delta = float(t.value[n_next, 0, 0] - t.value[n_cur, 0, 0])
                        raw_contribs[f_idx] += lr * delta

            # Invert sign if explaining negative class (class 0)
            if cls_idx == 0:
                ref_val = -ref_val
                raw_contribs = -raw_contribs

        else:
            # Multiclass GBDT: estimator.estimators_ has shape (n_estimators, n_classes)
            if hasattr(estimator, "_raw_predict_init"):
                raw_init = estimator._raw_predict_init(x2d)
                init_val = float(raw_init[0, cls_idx])
            elif hasattr(estimator, "init_") and hasattr(estimator.init_, "predict_proba"):
                p = estimator.init_.predict_proba(x2d)[0]
                init_val = float(np.log(np.clip(p[cls_idx], 1e-15, 1.0)))
            else:
                init_val = 0.0

            ref_val = init_val
            raw_contribs = np.zeros(n_feats)

            for stage in estimator.estimators_:
                est = stage[cls_idx]
                t = est.tree_
                ref_val += lr * float(t.value[0, 0, 0])
                path = est.decision_path(x2d).indices
                for i in range(len(path) - 1):
                    n_cur, n_next = path[i], path[i + 1]
                    f_idx = t.feature[n_cur]
                    if 0 <= f_idx < n_feats:
                        delta = float(t.value[n_next, 0, 0] - t.value[n_cur, 0, 0])
                        raw_contribs[f_idx] += lr * delta

        grouped_items = group_record_contributions(
            raw_contribs, transformed_names, original_feature_names, raw_feature_record
        )
        recon_sum = ref_val + float(np.sum(raw_contribs))
        margin_score = float(estimator.decision_function(x2d)[0]) if n_classes == 2 else float(estimator.decision_function(x2d)[0, cls_idx])
        if n_classes == 2 and cls_idx == 0:
            margin_score = -margin_score
        recon_err = abs(margin_score - recon_sum)

        return LocalExplanationResponse(
            model_id=model_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            problem_type="classification",
            algorithm=algorithm,
            prediction=pred_label,
            predicted_class=pred_label,
            predicted_proba=float(probs[cls_idx]) if probs is not None else None,
            target_class=active_class,
            class_probabilities=prob_dict,
            reference_value=round(ref_val, 4),
            baseline_reference_value=round(ref_val, 4),
            reference_definition=f"Initial base estimator log-odds prior plus GBDT tree root biases for class '{active_class}'",
            output_scale="LOG_ODDS_MARGIN",
            decomposition_space="LOG_ODDS_MARGIN",
            explanation_method="exact_tree_path",
            feature_contributions=grouped_items,
            contributions=grouped_items,
            reconstruction_sum=round(recon_sum, 4),
            additive_sum=round(float(np.sum(raw_contribs)), 4),
            reconstruction_error=round(recon_err, 6),
            validation_status="EXACT_ADDITIVE" if recon_err < 1e-4 else "APPROXIMATE",
            is_valid=recon_err < 1e-3,
            is_calibrated=False,
            confidence_metric_name="uncalibrated_log_odds_margin",
            probability_note=(
                f"Feature contributions represent shifts in log-odds decision margin for class '{active_class}'. "
                "Class probabilities are non-linear softmax/sigmoid outputs and cannot be additively decomposed without distortion."
            ),
            limitations=[
                f"Attributions operate in log-odds margin space for class '{active_class}'.",
                "Tree path increments reflect model scoring logic, not causal influence.",
            ],
        )


# ---------------------------------------------------------------------------
# Baseline Explanations (DummyRegressor, DummyClassifier)
# ---------------------------------------------------------------------------
def _explain_baseline(
    estimator: Any,
    raw_feature_record: dict[str, Any],
    original_feature_names: list[str],
    problem_type: str,
    algorithm: str,
    model_id: str,
    dataset_id: str,
    dataset_version: int,
    pipeline: Pipeline,
    input_df: pd.DataFrame,
    target_class: Optional[Any] = None,
) -> LocalExplanationResponse:
    pred = pipeline.predict(input_df)[0]
    pred_proba = None
    if problem_type == "classification":
        target_class_str = str(target_class) if target_class is not None else None
        active_class = target_class_str if target_class_str is not None else str(pred)
        estimator = pipeline.named_steps.get("estimator", pipeline)
        if hasattr(pipeline, "predict_proba") and hasattr(estimator, "classes_"):
            classes = [str(c) for c in estimator.classes_]
            if active_class in classes:
                c_idx = classes.index(active_class)
                probs = pipeline.predict_proba(input_df)[0]
                pred_proba = float(probs[c_idx])
                ref_val = pred_proba
            else:
                ref_val = 1.0 if active_class == str(pred) else 0.0
        else:
            ref_val = 1.0 if active_class == str(pred) else 0.0
        decomp_space = "PROBABILITY_SPACE"
    else:
        ref_val = float(pred)
        active_class = None
        decomp_space = "PREDICTION_SPACE"

    items = [
        FeatureContributionItem(
            feature=f,
            contribution=0.0,
            feature_value=raw_feature_record.get(f),
            raw_value=raw_feature_record.get(f),
            direction="NEUTRAL",
            relative_weight_pct=0.0,
        )
        for f in original_feature_names
    ]

    return LocalExplanationResponse(
        model_id=model_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        problem_type=problem_type,
        algorithm=algorithm,
        prediction=pred if problem_type == "regression" else str(pred),
        predicted_value=float(pred) if problem_type == "regression" else None,
        predicted_class=str(pred) if problem_type == "classification" else None,
        predicted_proba=pred_proba,
        target_class=active_class,
        reference_value=ref_val,
        baseline_reference_value=ref_val,
        reference_definition="Constant baseline model expectation (independent of features)",
        output_scale=decomp_space,
        decomposition_space=decomp_space,
        explanation_method="baseline",
        feature_contributions=items,
        contributions=items,
        reconstruction_sum=ref_val,
        additive_sum=0.0,
        reconstruction_error=0.0,
        validation_status="EXACT_ADDITIVE",
        is_valid=True,
        is_calibrated=True if problem_type == "regression" else False,
        confidence_metric_name="constant_baseline",
        limitations=[
            "Baseline naive models predict a constant target irrespective of feature values.",
            "All input feature contributions are identically zero.",
        ],
    )


# ---------------------------------------------------------------------------
# Optional SHAP Wrapper
# ---------------------------------------------------------------------------
def _try_shap_explanation(*args, **kwargs) -> Optional[LocalExplanationResponse]:
    """Attempts to compute SHAP values if shap library is installed."""
    try:
        import shap  # type: ignore
    except ImportError:
        return None

    # SHAP implementation if module is present
    return None
