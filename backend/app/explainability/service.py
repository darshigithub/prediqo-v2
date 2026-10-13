"""Service layer coordinating local, global, and forecast explanations."""
from __future__ import annotations

import logging
from typing import Any, Optional
import duckdb
import pandas as pd

from ..forecasting.data_preparation import aggregate_time_series_from_parquet
from ..forecasting.model_store import get_forecast_metadata, list_forecast_models_for_dataset
from ..prediction.model_store import get_model_metadata, list_models_for_dataset, load_model, validate_model_version
from ..storage.dataset_store import get_metadata, get_parquet_path
from .forecasting_explainer import explain_forecast_model
from .global_explainer import explain_global_model
from .local_explainer import explain_local_prediction
from .models import (
    ExplainabilityFeasibilityResponse,
    ForecastExplanationResponse,
    GlobalExplanationResponse,
    LocalExplanationRequest,
    LocalExplanationResponse,
)

logger = logging.getLogger(__name__)


class ExplainabilityService:
    """Coordinates model explainability operations and version integrity validation."""

    @classmethod
    def get_feasibility(cls, dataset_id: str) -> ExplainabilityFeasibilityResponse:
        """Evaluates trained models available for explainability on a dataset."""
        ds_meta = get_metadata(dataset_id)
        if not ds_meta:
            raise KeyError(f"Dataset '{dataset_id}' not found.")

        current_ver = int(ds_meta.get("version", 1))
        pred_models = list_models_for_dataset(dataset_id, current_version=current_ver)
        fc_models = list_forecast_models_for_dataset(dataset_id)

        return ExplainabilityFeasibilityResponse(
            dataset_id=dataset_id,
            dataset_version=current_ver,
            has_trained_models=(len(pred_models) > 0 or len(fc_models) > 0),
            prediction_models_count=len(pred_models),
            forecast_models_count=len(fc_models),
            prediction_models=[m.model_dump() for m in pred_models],
            forecast_models=[m.model_dump() for m in fc_models],
        )

    @classmethod
    def explain_local(cls, model_id: str, request: LocalExplanationRequest) -> LocalExplanationResponse:
        """Generates local prediction attribution for a given feature record."""
        pipeline, metadata, feature_schema = load_model(model_id)

        # 1. Dataset version validation
        ds_meta = get_metadata(metadata.dataset_id)
        if ds_meta:
            cur_ver = int(ds_meta.get("version", 1))
            is_valid_ver, ver_err = validate_model_version(metadata, cur_ver)
            if not is_valid_ver:
                raise ValueError(ver_err)

        feat_cols = getattr(metadata, "feature_columns", getattr(metadata, "selected_features", []))

        # 2. Extract background reference sample from Parquet
        background_df = None
        parquet_path = get_parquet_path(metadata.dataset_id)
        if parquet_path and parquet_path.exists():
            try:
                p_str = str(parquet_path).replace("\\", "/")
                cols = ", ".join('"' + c.replace('"', '""') + '"' for c in feat_cols)
                con = duckdb.connect()
                background_df = con.execute(f"SELECT {cols} FROM read_parquet('{p_str}') LIMIT 50").df()
                con.close()
            except Exception as e:
                logger.debug("Failed loading background sample for local explanation: %s", e)

        # 3. Compute local attribution
        return explain_local_prediction(
            pipeline=pipeline,
            raw_feature_record=request.features,
            original_feature_names=feat_cols,
            problem_type=metadata.problem_type,
            algorithm=metadata.algorithm,
            model_id=model_id,
            dataset_id=metadata.dataset_id,
            dataset_version=metadata.dataset_version,
            background_df=background_df,
            target_class=request.target_class,
            method_preference=request.method_preference or "auto",
        )

    @classmethod
    def explain_global(cls, model_id: str, max_sample_rows: int = 100) -> GlobalExplanationResponse:
        """Generates global model feature influence across a sample of dataset records."""
        pipeline, metadata, _ = load_model(model_id)

        # 1. Dataset version validation
        ds_meta = get_metadata(metadata.dataset_id)
        if ds_meta:
            cur_ver = int(ds_meta.get("version", 1))
            is_valid_ver, ver_err = validate_model_version(metadata, cur_ver)
            if not is_valid_ver:
                raise ValueError(ver_err)

        feat_cols = getattr(metadata, "feature_columns", getattr(metadata, "selected_features", []))

        # 2. Load sample data from Parquet
        parquet_path = get_parquet_path(metadata.dataset_id)
        if not parquet_path or not parquet_path.exists():
            raise FileNotFoundError(f"Parquet storage not found for dataset '{metadata.dataset_id}'.")

        p_str = str(parquet_path).replace("\\", "/")
        cols = ", ".join('"' + c.replace('"', '""') + '"' for c in feat_cols)
        con = duckdb.connect()
        sample_df = con.execute(f"SELECT {cols} FROM read_parquet('{p_str}') LIMIT {max_sample_rows}").df()
        con.close()

        # 3. Compute global explanations
        return explain_global_model(
            pipeline=pipeline,
            original_feature_names=feat_cols,
            sample_df=sample_df,
            problem_type=metadata.problem_type,
            algorithm=metadata.algorithm,
            model_id=model_id,
            dataset_id=metadata.dataset_id,
            dataset_version=metadata.dataset_version,
            max_sample_rows=max_sample_rows,
        )

    @classmethod
    def explain_forecast(cls, model_id: str) -> ForecastExplanationResponse:
        """Generates structured explainability analysis for a trained forecast model."""
        metadata = get_forecast_metadata(model_id)
        if not metadata:
            raise KeyError(f"Forecasting model '{model_id}' not found.")

        # 1. Dataset version validation
        ds_meta = get_metadata(metadata.dataset_id)
        if ds_meta:
            cur_ver = int(ds_meta.get("version", 1))
            if metadata.dataset_version != cur_ver:
                raise ValueError(
                    f"Dataset version mismatch: Model was trained on v{metadata.dataset_version}, "
                    f"but dataset is currently on v{cur_ver}."
                )

        # 2. Load historical series if parquet exists
        hist_df = None
        parquet_path = get_parquet_path(metadata.dataset_id)
        if parquet_path and parquet_path.exists():
            try:
                imp_method = None
                if hasattr(metadata, "model_params") and isinstance(metadata.model_params, dict):
                    imp_method = metadata.model_params.get("imputation_method")
                elif hasattr(metadata, "imputation_method"):
                    imp_method = getattr(metadata, "imputation_method")

                hist_df, _, _ = aggregate_time_series_from_parquet(
                    parquet_path=parquet_path,
                    date_col=metadata.date_column,
                    metric_col=metadata.metric_column,
                    frequency=metadata.frequency,
                    aggregation=metadata.aggregation,
                    imputation_method=imp_method,
                )
            except Exception as e:
                logger.warning("Failed reconstructing historical series for forecast explanation: %s", e)

        # 3. Generate explanation
        return explain_forecast_model(
            model_id=model_id,
            metadata=metadata,
            historical_df=hist_df,
        )
