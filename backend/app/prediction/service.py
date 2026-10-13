"""PredictionService: High-level orchestration for supervised machine learning."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..storage.dataset_store import get_metadata, get_parquet_path
from .data_preparation import (
    build_full_preprocessing_pipeline,
    classify_feature_types,
    load_selected_columns_from_parquet,
    split_data,
)
from .evaluator import evaluate_models
from .feasibility import check_feasibility
from .feature_importance import extract_feature_importance
from .feature_selector import (
    check_correlation_leakage,
    check_leakage_warning,
    recommend_features,
    validate_selected_features,
)
from .model_store import (
    get_model_metadata,
    list_models_for_dataset,
    load_model,
    save_model,
    validate_model_version,
)
from .models import (
    ActualVsPredictedPoint,
    FeasibilityResponse,
    ModelListItem,
    ModelMetadata,
    PredictRequest,
    PredictResponse,
    TrainRequest,
    TrainResponse,
)
from .predictor import predict_single_record
from .target_detector import detect_target_candidates, validate_target
from .trainer import train_candidate_models

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PredictionService:
    """Orchestrator for prediction feasibility, training, evaluation, persistence, and inference."""

    @classmethod
    def get_feasibility(cls, dataset_id: str) -> FeasibilityResponse:
        """Analyzes prediction feasibility for a dataset."""
        meta = get_metadata(dataset_id)
        if not meta:
            raise KeyError(f"Dataset '{dataset_id}' not found.")
        return check_feasibility(meta, dataset_id)

    @classmethod
    def train_model(cls, request: TrainRequest) -> TrainResponse:
        """End-to-end model training, candidate evaluation, best model selection, and persistence."""
        meta = get_metadata(request.dataset_id)
        if not meta:
            raise KeyError(f"Dataset '{request.dataset_id}' not found.")

        dataset_version = int(meta.get("version", 1))
        columns_meta = meta.get("columns", [])
        all_col_names = [c.get("name") for c in columns_meta]

        # 1. Resolve Target and Problem Type
        target_col = request.target_column
        if target_col not in all_col_names:
            raise ValueError(f"Target column '{target_col}' not found in dataset.")

        t_meta = next((c for c in columns_meta if c.get("name") == target_col), {})
        t_sem_type = str(t_meta.get("semantic_type", "")).upper()
        t_dtype = str(t_meta.get("dtype", "")).lower()

        problem_type = request.problem_type
        if not problem_type:
            # Auto-detect problem type from metadata
            is_numeric = any(k in t_dtype for k in ("int", "float", "double", "decimal", "numeric"))
            if is_numeric and t_sem_type in ("MEASURE", "DIMENSION"):
                problem_type = "regression"
            else:
                problem_type = "classification"
        else:
            problem_type = problem_type.lower()

        if problem_type not in ("regression", "classification"):
            raise ValueError(f"Unsupported problem type '{problem_type}'. Must be 'regression' or 'classification'.")

        # 2. Resolve & Validate Features
        total_rows = int(meta.get("profile", {}).get("rows", 0))
        rec_features, excl_features, leakage_warnings = recommend_features(columns_meta, target_col, total_rows)

        selected_features = request.features
        if not selected_features:
            selected_features = rec_features

        is_valid_feat, feat_err = validate_selected_features(selected_features, all_col_names, target_col)
        if not is_valid_feat:
            raise ValueError(feat_err)

        # Collect any leakage warnings for user-selected features
        all_warnings: list[str] = []
        for feat in selected_features:
            leak_msg = check_leakage_warning(target_col, feat)
            if leak_msg and leak_msg not in all_warnings:
                all_warnings.append(leak_msg)

        # 3. Load Required Columns via DuckDB from Parquet
        parquet_path = get_parquet_path(request.dataset_id)
        if not parquet_path or not parquet_path.exists():
            raise FileNotFoundError(f"Parquet storage not found for dataset '{request.dataset_id}'.")

        load_cols = list(selected_features)
        if request.group_column and request.group_column in all_col_names and request.group_column not in load_cols:
            load_cols.append(request.group_column)

        df, sample_warnings = load_selected_columns_from_parquet(
            parquet_path, target_col, load_cols
        )
        all_warnings.extend(sample_warnings)

        # 4. Validate Target on Loaded Data
        is_valid_tgt, tgt_err = validate_target(df, target_col, problem_type)
        if not is_valid_tgt:
            raise ValueError(tgt_err)

        # Drop rows where target is NaN
        clean_df = df.dropna(subset=[target_col]).reset_index(drop=True)
        if len(clean_df) < 10:
            raise ValueError(f"Target '{target_col}' has fewer than 10 valid non-null rows.")

        # Check for suspiciously high correlation leakage
        corr_warnings = check_correlation_leakage(clean_df, target_col, selected_features)
        for cw in corr_warnings:
            if cw not in all_warnings:
                all_warnings.append(cw)

        X = clean_df[selected_features]
        y = clean_df[target_col]
        groups_series = clean_df[request.group_column] if (request.group_column and request.group_column in clean_df) else None

        # 5. Build Preprocessing Pipeline
        date_cols, num_cols, cat_cols = classify_feature_types(X, selected_features, columns_meta)
        preprocessor, expanded_numeric, prep_desc = build_full_preprocessing_pipeline(
            date_cols, num_cols, cat_cols
        )

        # 6. Split Data
        val_strategy = request.validation_strategy or "kfold"
        X_train, X_test, y_train, y_test = split_data(
            X,
            y,
            problem_type,
            test_size=request.test_size,
            random_state=request.random_state,
            validation_strategy=val_strategy,
            groups=groups_series,
        )

        groups_train = groups_series.iloc[X_train.index] if groups_series is not None else None

        # 7. Train Candidate Models
        candidate_models = train_candidate_models(
            preprocessor, X_train, y_train, problem_type, random_state=request.random_state
        )

        # 8. Evaluate Models and Select Best Model with Cross-Validation
        candidate_results, best_algo_name, best_summary, actual_vs_predicted, diagnostics = evaluate_models(
            candidate_models,
            X_test,
            y_test,
            problem_type,
            X_train=X_train,
            y_train=y_train,
            cv_folds=request.cv_folds,
            validation_strategy=val_strategy,
            random_state=request.random_state,
            groups_train=groups_train,
        )

        for rn in diagnostics.get("reliability_notes", []):
            if rn not in all_warnings:
                all_warnings.append(rn)

        winning_pipeline = candidate_models[best_algo_name]

        # 9. Extract Feature Importance
        feature_importance = extract_feature_importance(winning_pipeline, selected_features)

        # 10. Persist Model and Artifacts
        model_id = f"model_{uuid.uuid4().hex[:8]}"
        created_at = _now()

        # Build feature schema for inference validation
        sample_feature_values: dict[str, Any] = {}
        for feat in selected_features:
            s_val = clean_df[feat].dropna().iloc[0] if len(clean_df[feat].dropna()) > 0 else None
            # Convert non-JSON-compliant types
            if hasattr(s_val, "item"):
                s_val = s_val.item()
            elif isinstance(s_val, (pd.Timestamp, datetime)):
                s_val = str(s_val)
            sample_feature_values[feat] = s_val

        model_meta = ModelMetadata(
            model_id=model_id,
            dataset_id=request.dataset_id,
            dataset_version=dataset_version,
            target_column=target_col,
            problem_type=problem_type,
            feature_columns=selected_features,
            training_row_count=len(X_train),
            test_row_count=len(X_test),
            created_at=created_at,
            algorithm=best_algo_name,
            primary_metric=best_summary.primary_metric,
            primary_metric_value=best_summary.primary_metric_value,
            preprocessing_description=prep_desc,
            metrics=best_summary.metrics,
            cv_metrics=best_summary.cv_metrics,
            validation_strategy=val_strategy,
            cv_folds=request.cv_folds,
            actual_vs_predicted=actual_vs_predicted,
            candidate_models=candidate_results,
            feature_importance=feature_importance,
            is_reliable=diagnostics["is_reliable"],
            reliability_notes=diagnostics["reliability_notes"],
            class_distribution=diagnostics["class_distribution"],
            confusion_matrix=diagnostics["confusion_matrix"],
            class_labels=diagnostics["class_labels"],
            per_class_metrics=diagnostics["per_class_metrics"],
        )

        save_model(model_id, winning_pipeline, model_meta, sample_feature_values)

        return TrainResponse(
            model_id=model_id,
            dataset_id=request.dataset_id,
            dataset_version=dataset_version,
            target_column=target_col,
            problem_type=problem_type,
            selected_features=selected_features,
            best_model=best_summary,
            candidate_models=candidate_results,
            training_row_count=len(X_train),
            test_row_count=len(X_test),
            validation_strategy=val_strategy,
            cv_folds=request.cv_folds,
            actual_vs_predicted=actual_vs_predicted,
            training_time_ms=getattr(winning_pipeline, "_training_time_ms", None),
            feature_importance=feature_importance,
            is_reliable=diagnostics["is_reliable"],
            reliability_notes=diagnostics["reliability_notes"],
            class_distribution=diagnostics["class_distribution"],
            confusion_matrix=diagnostics["confusion_matrix"],
            class_labels=diagnostics["class_labels"],
            per_class_metrics=diagnostics["per_class_metrics"],
            baseline_algorithm=diagnostics.get("baseline_algorithm"),
            warnings=all_warnings,
        )



    @classmethod
    def list_models(cls, dataset_id: str, current_version_only: bool = False) -> list[ModelListItem]:
        """Lists models for a given dataset."""
        meta = get_metadata(dataset_id)
        current_version = int(meta.get("version", 1)) if (meta and current_version_only) else None
        return list_models_for_dataset(dataset_id, current_version=current_version)

    @classmethod
    def get_model(cls, model_id: str) -> ModelMetadata:
        """Retrieves details of a trained model."""
        meta = get_model_metadata(model_id)
        if not meta:
            raise KeyError(f"Model '{model_id}' not found.")
        return meta

    @classmethod
    def predict(cls, request: PredictRequest) -> PredictResponse:
        """Executes prediction for single input record using the stored model."""
        pipeline, metadata, feature_schema = load_model(request.model_id)

        # Check dataset version match
        ds_meta = get_metadata(metadata.dataset_id)
        if ds_meta:
            current_ds_version = int(ds_meta.get("version", 1))
            is_valid_ver, ver_err = validate_model_version(metadata, current_ds_version)
            if not is_valid_ver:
                raise ValueError(ver_err)

        return predict_single_record(pipeline, metadata, feature_schema, request.features)
