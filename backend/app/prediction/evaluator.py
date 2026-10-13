"""Evaluation, cross-validation, and selection of candidate machine learning models."""
from __future__ import annotations

import logging
from typing import Any, Optional
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold, TimeSeriesSplit
from sklearn.pipeline import Pipeline

from .models import ActualVsPredictedPoint, BestModelSummary, CandidateModelResult

logger = logging.getLogger(__name__)


def evaluate_models(
    models: dict[str, Pipeline],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    problem_type: str,
    X_train: Optional[pd.DataFrame] = None,
    y_train: Optional[pd.Series] = None,
    cv_folds: int = 5,
    validation_strategy: str = "kfold",
    random_state: int = 42,
    groups_train: Optional[pd.Series] = None,
) -> tuple[
    list[CandidateModelResult],
    str,
    BestModelSummary,
    list[ActualVsPredictedPoint],
    dict[str, Any],
]:
    """Evaluates candidate models using cross-validation and holdout test set, selecting the best model."""
    p_type = problem_type.lower()
    candidate_results: list[CandidateModelResult] = []

    best_name: str = ""
    best_primary_val: float = float("inf") if p_type == "regression" else -1.0
    best_metrics: dict[str, Any] = {}
    best_cv_metrics: Optional[dict[str, Any]] = None
    best_rationale: str = ""
    winning_test_preds: Optional[np.ndarray] = None

    # Reliability diagnostics
    reliability_notes: list[str] = []
    class_distribution: Optional[dict[str, int]] = None
    if p_type == "classification" and y_train is not None:
        vc = y_train.value_counts()
        class_distribution = {str(k): int(v) for k, v in vc.items()}
        counts = list(class_distribution.values())
        if len(counts) > 1:
            ratio = max(counts) / max(1, min(counts))
            if ratio > 10.0 or (min(counts) / max(1, len(y_train))) < 0.05:
                min_cls = min(class_distribution, key=class_distribution.get)
                reliability_notes.append(
                    f"Severe class imbalance: minority class '{min_cls}' represents only "
                    f"{round(min(counts)/max(1, len(y_train))*100, 1)}% of training data."
                )

    if X_train is not None and len(X_train) < 20:
        reliability_notes.append(
            f"Small sample size ({len(X_train)} training rows); cross-validation estimates have elevated variance."
        )

    # Setup Cross-Validation splitter if training data is provided
    can_cv = X_train is not None and y_train is not None and len(X_train) >= 6
    actual_folds = cv_folds
    cv_splitter = None

    if can_cv:
        n_samples = len(X_train)
        actual_folds = min(cv_folds, max(2, min(n_samples, n_samples // 3)))
        actual_folds = min(actual_folds, n_samples)
        if actual_folds < 2:
            can_cv = False
        elif validation_strategy == "time_aware":
            cv_splitter = TimeSeriesSplit(n_splits=actual_folds)
        elif validation_strategy == "group_kfold" and groups_train is not None:
            n_groups = len(groups_train.unique())
            if n_groups >= 2:
                actual_folds = min(actual_folds, n_groups)
                cv_splitter = GroupKFold(n_splits=actual_folds)
            else:
                cv_splitter = KFold(n_splits=actual_folds, shuffle=True, random_state=random_state)
        elif p_type == "classification":
            min_class_count = int(y_train.value_counts().min()) if len(y_train) > 0 else 0
            if min_class_count >= 2:
                cv_folds_strat = min(actual_folds, min_class_count)
                if cv_folds_strat >= 2:
                    cv_splitter = StratifiedKFold(n_splits=cv_folds_strat, shuffle=True, random_state=random_state)
                    actual_folds = cv_folds_strat
            if cv_splitter is None:
                cv_splitter = KFold(n_splits=actual_folds, shuffle=True, random_state=random_state)
        else:
            cv_splitter = KFold(n_splits=actual_folds, shuffle=True, random_state=random_state)

    baseline_primary_score: Optional[float] = None
    try:
        from .trainer import get_baseline_estimator
        base_est = get_baseline_estimator(problem_type)
        first_pipe = next(iter(models.values()))
        prep = clone(first_pipe.named_steps["preprocessor"])
        base_pipe = Pipeline([("prep", prep), ("est", base_est)])
        base_pipe.fit(X_train if X_train is not None else X_test, y_train if y_train is not None else y_test)
        if cv_splitter is not None and X_train is not None and y_train is not None:
            split_args = (X_train, y_train, groups_train) if isinstance(cv_splitter, GroupKFold) else (X_train, y_train)
            b_scores = []
            for tr_idx, val_idx in cv_splitter.split(*split_args):
                b_tr_X, b_tr_y = X_train.iloc[tr_idx], y_train.iloc[tr_idx]
                b_val_X, b_val_y = X_train.iloc[val_idx], y_train.iloc[val_idx]
                b_pipe = clone(base_pipe)
                b_pipe.fit(b_tr_X, b_tr_y)
                b_pr = b_pipe.predict(b_val_X)
                if p_type == "regression":
                    b_scores.append(float(mean_absolute_error(b_val_y, b_pr)))
                else:
                    b_scores.append(float(f1_score(b_val_y, b_pr, average="weighted", zero_division=0)))
            if b_scores:
                baseline_primary_score = float(np.mean(b_scores))
        else:
            b_pr = base_pipe.predict(X_test)
            if p_type == "regression":
                baseline_primary_score = float(mean_absolute_error(y_test, b_pr))
            else:
                baseline_primary_score = float(f1_score(y_test, b_pr, average="weighted", zero_division=0))
    except Exception as e:
        logger.debug("Failed to evaluate baseline estimator: %s", e)

    for name, pipe in models.items():
        try:
            training_time_ms = getattr(pipe, "_training_time_ms", None)
            is_baseline = "baseline" in name.lower() or "dummy" in name.lower()


            # 1. Cross-Validation
            cv_metrics: Optional[dict[str, Any]] = None
            if cv_splitter is not None and X_train is not None and y_train is not None:
                fold_maes: list[float] = []
                fold_rmses: list[float] = []
                fold_r2s: list[float] = []
                fold_f1s: list[float] = []
                fold_accs: list[float] = []

                split_args = (X_train, y_train, groups_train) if isinstance(cv_splitter, GroupKFold) else (X_train, y_train)

                for train_idx, val_idx in cv_splitter.split(*split_args):
                    X_f_tr, y_f_tr = X_train.iloc[train_idx], y_train.iloc[train_idx]
                    X_f_val, y_f_val = X_train.iloc[val_idx], y_train.iloc[val_idx]

                    fold_pipe = clone(pipe)
                    fold_pipe.fit(X_f_tr, y_f_tr)
                    f_preds = fold_pipe.predict(X_f_val)

                    if p_type == "regression":
                        f_mae = float(mean_absolute_error(y_f_val, f_preds))
                        f_mse = float(mean_squared_error(y_f_val, f_preds))
                        fold_maes.append(f_mae)
                        fold_rmses.append(float(np.sqrt(f_mse)))
                        if y_f_val.nunique() > 1:
                            r2_val = float(r2_score(y_f_val, f_preds))
                            fold_r2s.append(r2_val)
                    else:
                        fold_accs.append(float(accuracy_score(y_f_val, f_preds)))
                        fold_f1s.append(float(f1_score(y_f_val, f_preds, average="weighted", zero_division=0)))

                if p_type == "regression" and fold_maes:
                    cv_metrics = {
                        "cv_mae": round(float(np.mean(fold_maes)), 4),
                        "cv_mae_std": round(float(np.std(fold_maes)), 4),
                        "cv_rmse": round(float(np.mean(fold_rmses)), 4),
                        "cv_r2": round(float(np.mean(fold_r2s)), 4) if fold_r2s else None,
                        "fold_scores": [round(float(s), 4) for s in fold_maes],
                        "folds": len(fold_maes),
                        "strategy": validation_strategy,
                    }
                elif p_type == "classification" and fold_f1s:
                    cv_metrics = {
                        "cv_f1": round(float(np.mean(fold_f1s)), 4),
                        "cv_f1_std": round(float(np.std(fold_f1s)), 4),
                        "cv_accuracy": round(float(np.mean(fold_accs)), 4),
                        "fold_scores": [round(float(s), 4) for s in fold_f1s],
                        "folds": len(fold_f1s),
                        "strategy": validation_strategy,
                    }

            # 2. Holdout Test Evaluation
            preds = pipe.predict(X_test)

            if p_type == "regression":
                mae = float(mean_absolute_error(y_test, preds))
                mse = float(mean_squared_error(y_test, preds))
                rmse = float(np.sqrt(mse))
                r2 = float(r2_score(y_test, preds)) if y_test.nunique() > 1 else 0.0

                holdout_metrics = {
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "r2": round(r2, 4),
                }

                eval_metric_val = cv_metrics["cv_mae"] if (cv_metrics and "cv_mae" in cv_metrics) else mae
                if is_baseline:
                    baseline_primary_score = eval_metric_val

                # Prefer non-baseline model unless baseline is only candidate
                is_better = (eval_metric_val < best_primary_val) and (not is_baseline or not best_name)

                if is_better:
                    best_primary_val = eval_metric_val
                    best_name = name
                    best_metrics = holdout_metrics
                    best_cv_metrics = cv_metrics
                    winning_test_preds = preds
                    if cv_metrics:
                        best_rationale = (
                            f"{name} selected as best model with lowest cross-validation MAE "
                            f"({cv_metrics['cv_mae']} ± {cv_metrics['cv_mae_std']}) across {cv_metrics['folds']} folds."
                        )
                    else:
                        best_rationale = f"{name} selected with lowest holdout MAE ({round(mae, 4)})."

            else:  # classification
                acc = float(accuracy_score(y_test, preds))
                prec = float(precision_score(y_test, preds, average="weighted", zero_division=0))
                rec = float(recall_score(y_test, preds, average="weighted", zero_division=0))
                f1 = float(f1_score(y_test, preds, average="weighted", zero_division=0))

                holdout_metrics = {
                    "accuracy": round(acc, 4),
                    "precision": round(prec, 4),
                    "recall": round(rec, 4),
                    "f1": round(f1, 4),
                    "averaging": "weighted",
                }

                eval_metric_val = cv_metrics["cv_f1"] if (cv_metrics and "cv_f1" in cv_metrics) else f1
                if is_baseline:
                    baseline_primary_score = eval_metric_val

                is_better = (eval_metric_val > best_primary_val) and (not is_baseline or not best_name)

                if is_better:
                    best_primary_val = eval_metric_val
                    best_name = name
                    best_metrics = holdout_metrics
                    best_cv_metrics = cv_metrics
                    winning_test_preds = preds
                    if cv_metrics:
                        best_rationale = (
                            f"{name} selected as best model with highest cross-validation F1 score "
                            f"({cv_metrics['cv_f1']} ± {cv_metrics['cv_f1_std']}) across {cv_metrics['folds']} folds."
                        )
                    else:
                        best_rationale = f"{name} selected with highest holdout F1 ({round(f1, 4)})."

            candidate_results.append(
                CandidateModelResult(
                    algorithm=name,
                    metrics=holdout_metrics,
                    cv_metrics=cv_metrics,
                    training_time_ms=training_time_ms,
                    is_best=False,
                    is_baseline=is_baseline,
                )
            )

        except Exception as e:
            logger.warning("Evaluation failed for candidate %s: %s", name, e)

    if not best_name and candidate_results:
        best_name = candidate_results[0].algorithm
        best_metrics = candidate_results[0].metrics
        best_cv_metrics = candidate_results[0].cv_metrics
        best_primary_val = best_metrics.get("mae", 0.0) if p_type == "regression" else best_metrics.get("f1", 0.0)
        best_rationale = f"{best_name} selected as fallback candidate."

    # Compare candidates against baseline model
    for cand in candidate_results:
        if cand.algorithm == best_name:
            cand.is_best = True

        if baseline_primary_score is not None and baseline_primary_score > 0 and not cand.is_baseline:
            cand_score = cand.cv_metrics["cv_mae"] if (cand.cv_metrics and "cv_mae" in cand.cv_metrics) else cand.metrics.get("mae", 0.0)
            if p_type == "regression":
                # Lower MAE is better -> positive percentage is improvement over baseline
                imp = round(((baseline_primary_score - cand_score) / baseline_primary_score) * 100.0, 1)
                cand.vs_baseline_pct = imp
            else:
                cand_f1 = cand.cv_metrics["cv_f1"] if (cand.cv_metrics and "cv_f1" in cand.cv_metrics) else cand.metrics.get("f1", 0.0)
                imp = round(((cand_f1 - baseline_primary_score) / max(0.001, baseline_primary_score)) * 100.0, 1)
                cand.vs_baseline_pct = imp

    # Build Actual vs Predicted points for regression
    actual_vs_predicted: list[ActualVsPredictedPoint] = []
    if p_type == "regression" and winning_test_preds is not None and len(y_test) > 0:
        y_test_arr = np.asarray(y_test)
        limit_pts = min(60, len(y_test_arr))
        for a, p in zip(y_test_arr[:limit_pts], winning_test_preds[:limit_pts]):
            a_val = round(float(a), 4)
            p_val = round(float(p), 4)
            actual_vs_predicted.append(
                ActualVsPredictedPoint(
                    actual=a_val,
                    predicted=p_val,
                    residual=round(a_val - p_val, 4),
                )
            )

    # Classification diagnostics: confusion matrix & per-class metrics
    cm_list: Optional[list[list[int]]] = None
    class_labels: Optional[list[str]] = None
    per_class_metrics: Optional[dict[str, dict[str, float]]] = None

    if p_type == "classification" and winning_test_preds is not None and len(y_test) > 0:
        labels_arr = np.unique(np.concatenate([np.asarray(y_test), winning_test_preds]))
        class_labels = [str(l) for l in sorted(labels_arr)]
        cm = confusion_matrix(y_test, winning_test_preds, labels=labels_arr)
        cm_list = cm.tolist()

        try:
            rep = classification_report(y_test, winning_test_preds, output_dict=True, zero_division=0)
            per_class_metrics = {}
            for k, v in rep.items():
                if k not in ("accuracy", "macro avg", "weighted avg") and isinstance(v, dict):
                    per_class_metrics[str(k)] = {
                        "precision": round(float(v.get("precision", 0.0)), 4),
                        "recall": round(float(v.get("recall", 0.0)), 4),
                        "f1": round(float(v.get("f1-score", 0.0)), 4),
                        "support": int(v.get("support", 0)),
                    }
        except Exception as e:
            logger.debug("Failed to compute per-class classification report: %s", e)

    best_cand_obj = next((c for c in candidate_results if c.algorithm == best_name), None)
    best_vs_baseline = best_cand_obj.vs_baseline_pct if best_cand_obj else None

    primary_metric_name = "mae" if p_type == "regression" else "f1"
    best_summary = BestModelSummary(
        algorithm=best_name,
        primary_metric=primary_metric_name,
        primary_metric_value=round(best_primary_val, 4),
        metrics=best_metrics,
        cv_metrics=best_cv_metrics,
        selection_rationale=best_rationale,
        vs_baseline_pct=best_vs_baseline,
        confusion_matrix=cm_list,
        class_labels=class_labels,
        per_class_metrics=per_class_metrics,
        is_reliable=(len(reliability_notes) == 0),
        reliability_notes=reliability_notes,
    )

    diagnostics = {
        "class_distribution": class_distribution,
        "confusion_matrix": cm_list,
        "class_labels": class_labels,
        "per_class_metrics": per_class_metrics,
        "is_reliable": (len(reliability_notes) == 0),
        "reliability_notes": reliability_notes,
        "baseline_algorithm": "BaselineRegressor" if p_type == "regression" else "BaselineClassifier",
    }

    return candidate_results, best_name, best_summary, actual_vs_predicted, diagnostics


