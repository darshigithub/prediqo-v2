"""ForecastingService: End-to-end orchestration for time-series forecasting."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import pandas as pd

from ..storage.dataset_store import get_metadata, get_parquet_path
from .data_preparation import aggregate_time_series_from_parquet
from .evaluator import evaluate_forecast_candidates
from .feasibility import check_forecast_feasibility
from .forecaster import generate_future_forecast, prepare_historical_points
from .model_store import (
    get_forecast_metadata,
    list_forecast_models_for_dataset,
    load_forecast_model,
    save_forecast_model,
)
from .models import (
    ForecastFeasibilityResponse,
    ForecastModelListItem,
    ForecastModelMetadata,
    ForecastPredictRequest,
    ForecastPredictResponse,
    ForecastTrainRequest,
    ForecastTrainResponse,
)
from .trainer import get_candidate_forecasters

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ForecastingService:
    """High-level orchestration for time-series forecasting."""

    @classmethod
    def get_feasibility(cls, dataset_id: str) -> ForecastFeasibilityResponse:
        """Analyzes forecasting feasibility for a dataset."""
        meta = get_metadata(dataset_id)
        if not meta:
            raise KeyError(f"Dataset '{dataset_id}' not found.")
        return check_forecast_feasibility(meta, dataset_id)

    @classmethod
    def train_and_forecast(cls, request: ForecastTrainRequest) -> ForecastTrainResponse:
        """Runs end-to-end time series aggregation, backtesting, model selection, projection, and persistence."""
        meta = get_metadata(request.dataset_id)
        if not meta:
            raise KeyError(f"Dataset '{request.dataset_id}' not found.")

        dataset_version = int(meta.get("version", 1))
        columns_meta = meta.get("columns", [])
        all_col_names = [c.get("name") for c in columns_meta]

        if request.date_column not in all_col_names:
            raise ValueError(f"Date column '{request.date_column}' not found in dataset.")
        if request.metric_column not in all_col_names:
            raise ValueError(f"Metric column '{request.metric_column}' not found in dataset.")

        parquet_path = get_parquet_path(request.dataset_id)
        if not parquet_path or not parquet_path.exists():
            raise FileNotFoundError(f"Parquet storage not found for dataset '{request.dataset_id}'.")

        # 1. Aggregate Time Series via DuckDB
        series_df, stats, warnings = aggregate_time_series_from_parquet(
            parquet_path=parquet_path,
            date_col=request.date_column,
            metric_col=request.metric_column,
            frequency=request.frequency,
            aggregation=request.aggregation,
            group_col=request.group_column,
            imputation_method=request.imputation_method,
        )

        has_negatives = bool((series_df["y"] < 0).any())
        non_neg = request.non_negative if request.non_negative is not None else (not has_negatives)

        # 2. Candidate Models
        candidate_models = get_candidate_forecasters(
            frequency=request.frequency,
            series_length=len(series_df),
            non_negative=non_neg,
        )

        # 3. Chronological Rolling-Origin Backtesting & Evaluation
        b_strategy = request.backtest_strategy or "rolling_origin"
        candidate_results, best_key, best_summary, backtest_data, _ = evaluate_forecast_candidates(
            series_df=series_df,
            candidate_models=candidate_models,
            horizon=request.horizon,
            backtest_strategy=b_strategy,
        )

        if best_summary.interval_notes:
            warnings.append(best_summary.interval_notes)

        # 4. Generate Future Forecasts using winning model
        winning_model = candidate_models[best_key]
        forecast_data = generate_future_forecast(
            series_df=series_df,
            winning_model=winning_model,
            horizon=request.horizon,
            frequency=request.frequency,
            backtest_data=backtest_data,
            non_negative=non_neg,
        )

        # 5. Prepare Historical Points for visualization
        historical_data = prepare_historical_points(series_df)

        # 6. Staleness Check
        is_stale = False
        stale_warning = None
        end_date_str = stats["end_date"]
        try:
            end_dt = pd.to_datetime(end_date_str)
            days_ago = (pd.Timestamp.now() - end_dt).days
            if days_ago > 60:
                is_stale = True
                stale_warning = (
                    f"Dataset historical observations end on {end_date_str} ({days_ago} days ago). "
                    "Future forecast starts from the historical cutoff and represents a historical projection."
                )
                warnings.append(stale_warning)
        except Exception:
            pass

        # 7. Persist Model
        model_id = f"fc_{uuid.uuid4().hex[:8]}"
        created_at = _now()

        model_meta = ForecastModelMetadata(
            model_id=model_id,
            dataset_id=request.dataset_id,
            dataset_version=dataset_version,
            date_column=request.date_column,
            metric_column=request.metric_column,
            frequency=request.frequency,
            aggregation=request.aggregation,
            horizon=request.horizon,
            created_at=created_at,
            historical_start_date=stats["start_date"],
            historical_end_date=stats["end_date"],
            total_historical_periods=stats["total_periods"],
            algorithm=best_summary.algorithm,
            primary_metric=best_summary.primary_metric,
            primary_metric_value=best_summary.primary_metric_value,
            metrics=best_summary.metrics,
            candidate_models=candidate_results,
            model_params=winning_model.get_params(),
            evaluation_windows=best_summary.evaluation_windows,
            backtest_strategy=best_summary.backtest_strategy,
            empirical_coverage_80=best_summary.empirical_coverage_80,
            empirical_coverage_95=best_summary.empirical_coverage_95,
            coverage_sample_size=best_summary.coverage_sample_size,
            interval_notes=best_summary.interval_notes,
        )

        save_forecast_model(model_id, model_meta, forecast_data)

        return ForecastTrainResponse(
            model_id=model_id,
            dataset_id=request.dataset_id,
            dataset_version=dataset_version,
            date_column=request.date_column,
            metric_column=request.metric_column,
            frequency=request.frequency,
            aggregation=request.aggregation,
            horizon=request.horizon,
            historical_start_date=stats["start_date"],
            historical_end_date=stats["end_date"],
            total_historical_periods=stats["total_periods"],
            is_stale=is_stale,
            stale_warning=stale_warning,
            best_model=best_summary,
            candidate_models=candidate_results,
            historical_data=historical_data,
            backtest_data=backtest_data,
            forecast_data=forecast_data,
            evaluation_windows=best_summary.evaluation_windows,
            backtest_strategy=best_summary.backtest_strategy,
            empirical_coverage_80=best_summary.empirical_coverage_80,
            empirical_coverage_95=best_summary.empirical_coverage_95,
            coverage_sample_size=best_summary.coverage_sample_size,
            interval_notes=best_summary.interval_notes,
            warnings=warnings,
        )



    @classmethod
    def list_models(cls, dataset_id: str) -> list[ForecastModelListItem]:
        """Lists trained forecast models for a dataset."""
        return list_forecast_models_for_dataset(dataset_id)

    @classmethod
    def get_model(cls, model_id: str) -> ForecastModelMetadata:
        """Retrieves details of a trained forecast model."""
        meta = get_forecast_metadata(model_id)
        if not meta:
            raise KeyError(f"Forecasting model '{model_id}' not found.")
        return meta

    @classmethod
    def predict(cls, request: ForecastPredictRequest) -> ForecastPredictResponse:
        """Retrieves or re-computes forecast points for a saved forecasting model."""
        meta, points = load_forecast_model(request.model_id)

        # If custom horizon is requested, re-predict with saved model configuration
        if request.horizon is not None and request.horizon != meta.horizon:
            # Reconstruct series from dataset
            parquet_path = get_parquet_path(meta.dataset_id)
            if parquet_path and parquet_path.exists():
                series_df, stats, _ = aggregate_time_series_from_parquet(
                    parquet_path=parquet_path,
                    date_col=meta.date_column,
                    metric_col=meta.metric_column,
                    frequency=meta.frequency,
                    aggregation=meta.aggregation,
                )
                candidate_models = get_candidate_forecasters(
                    frequency=meta.frequency,
                    series_length=len(series_df),
                    non_negative=True,
                )
                # Find matching model
                match_model = next(
                    (m for m in candidate_models.values() if m.name == meta.algorithm),
                    candidate_models.get("naive"),
                )
                points = generate_future_forecast(
                    series_df=series_df,
                    winning_model=match_model,
                    horizon=request.horizon,
                    frequency=meta.frequency,
                    backtest_data=[],
                    non_negative=True,
                )
            else:
                # Truncate or extend existing points if parquet not found
                if request.horizon < len(points):
                    points = points[:request.horizon]

        # Check staleness
        is_stale = False
        warnings: list[str] = []
        try:
            end_dt = pd.to_datetime(meta.historical_end_date)
            days_ago = (pd.Timestamp.now() - end_dt).days
            if days_ago > 60:
                is_stale = True
                warnings.append(
                    f"Model historical data ends on {meta.historical_end_date} ({days_ago} days ago)."
                )
        except Exception:
            pass

        return ForecastPredictResponse(
            model_id=meta.model_id,
            dataset_id=meta.dataset_id,
            algorithm=meta.algorithm,
            horizon=len(points),
            frequency=meta.frequency,
            forecast_data=points,
            historical_end_date=meta.historical_end_date,
            is_stale=is_stale,
            warnings=warnings,
        )
