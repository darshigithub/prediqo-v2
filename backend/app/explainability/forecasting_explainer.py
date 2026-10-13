"""Explainability generator for time-series forecasting models."""
from __future__ import annotations

import logging
from typing import Any, Optional
import numpy as np
import pandas as pd

from ..forecasting.model_store import get_forecast_metadata, load_forecast_model
from ..forecasting.models import ForecastModelMetadata
from .models import ForecastExplanationResponse

logger = logging.getLogger(__name__)


def explain_forecast_model(
    model_id: str,
    metadata: ForecastModelMetadata,
    historical_df: Optional[pd.DataFrame] = None,
) -> ForecastExplanationResponse:
    """Generates a structured, mathematically defensible explanation for a trained forecaster."""
    algo = metadata.algorithm
    limitations: list[str] = [
        "Historical trends and correlations do not prove causality or imply external causal mechanisms.",
        "Forecasting projections assume that historical patterns continue into the future without structural breaks.",
    ]
    data_quality_notes: list[str] = []

    # 1. Analyze historical series behavior if available
    historical_trend = "Historical trend evaluated over backtest horizon"
    trend_slope: Optional[float] = None
    trend_intercept: Optional[float] = None
    level_state: Optional[float] = None
    seasonal_cycle: Optional[int] = None
    recent_change_pct: Optional[float] = None
    recent_ref: Optional[float] = None

    if historical_df is not None and len(historical_df) >= 2 and "y" in historical_df.columns:
        y_vals = historical_df["y"].dropna().to_numpy(dtype=float)
        n = len(y_vals)
        if n >= 2:
            first_val = float(y_vals[0])
            last_val = float(y_vals[-1])
            recent_ref = round(last_val, 2)

            # Period-over-period change (last vs penultimate)
            penultimate_val = float(y_vals[-2])
            if abs(penultimate_val) > 1e-6:
                recent_change_pct = round(((last_val - penultimate_val) / abs(penultimate_val)) * 100.0, 2)

            # Overall trend change
            if abs(first_val) > 1e-6:
                tot_change_pct = ((last_val - first_val) / abs(first_val)) * 100.0
                dir_str = "Upward" if tot_change_pct > 2.0 else ("Downward" if tot_change_pct < -2.0 else "Stable")
                historical_trend = f"{dir_str} ({tot_change_pct:+.1f}% across {n} historical periods)"
            else:
                historical_trend = f"Series ended at {last_val:.1f} across {n} periods"

            # Linear trend fit across historical series
            t = np.arange(n, dtype=float)
            p = np.polyfit(t, y_vals, deg=1)
            trend_slope = round(float(p[0]), 4)
            trend_intercept = round(float(p[1]), 4)

    # 2. Extract model-specific parameters
    if "Linear Trend" in algo:
        selection_reason = (
            f"Fitted linear slope of {trend_slope if trend_slope is not None else 'estimated'} per {metadata.frequency} period, "
            "capturing continuous drift across historical observations."
        )
    elif "Exponential Smoothing" in algo:
        level_state = recent_ref
        selection_reason = (
            "Recursive exponential weighting adapts to recent shifts while damping historical noise."
        )
    elif "Moving Average" in algo:
        level_state = recent_ref
        selection_reason = (
            "Projects the rolling mean of recent historical observation window into the forecast horizon."
        )
    elif "Seasonal Naive" in algo:
        seasonal_cycle = 7 if metadata.frequency == "daily" else (12 if metadata.frequency == "monthly" else 4)
        selection_reason = (
            f"Projects values by repeating the historical observation from the corresponding period of the {seasonal_cycle}-step seasonal cycle."
        )
    else:  # Naive
        level_state = recent_ref
        selection_reason = (
            f"Naive persistence baseline: projects the most recent observation ({recent_ref if recent_ref is not None else 'last value'}) forward."
        )

    # 3. Compile empirical coverage and interval notes
    if metadata.empirical_coverage_80 is not None or metadata.empirical_coverage_95 is not None:
        cov_note = (
            f"Empirical backtest coverage: {metadata.empirical_coverage_80 or '-'}% (nominal 80%), "
            f"{metadata.empirical_coverage_95 or '-'}% (nominal 95%)."
        )
        data_quality_notes.append(cov_note)

    if metadata.interval_notes:
        data_quality_notes.append(metadata.interval_notes)

    vs_naive = getattr(metadata, "vs_naive_pct", None)
    if vs_naive is None and isinstance(metadata.metrics, dict):
        vs_naive = metadata.metrics.get("vs_naive_pct")

    if vs_naive is not None:
        if vs_naive > 0:
            data_quality_notes.append(f"Model demonstrated {vs_naive}% lower error than naive baseline during backtesting.")
        elif vs_naive < 0:
            data_quality_notes.append(f"Model showed {abs(vs_naive)}% higher error than naive baseline during backtesting.")

    mae_val = metadata.metrics.get("mae", getattr(metadata, "mae", 0.0)) if isinstance(metadata.metrics, dict) else getattr(metadata, "mae", 0.0)
    rmse_val = metadata.metrics.get("rmse", getattr(metadata, "rmse", 0.0)) if isinstance(metadata.metrics, dict) else getattr(metadata, "rmse", 0.0)

    return ForecastExplanationResponse(
        model_id=metadata.model_id,
        dataset_id=metadata.dataset_id,
        dataset_version=metadata.dataset_version,
        metric_column=metadata.metric_column,
        date_column=metadata.date_column,
        frequency=metadata.frequency,
        aggregation=metadata.aggregation,
        horizon=metadata.horizon,
        algorithm=algo,
        selection_reason=selection_reason,
        historical_trend=historical_trend,
        trend_slope=trend_slope,
        trend_intercept=trend_intercept,
        level_state=level_state,
        seasonal_cycle=seasonal_cycle,
        recent_change_pct=recent_change_pct,
        recent_observation_reference=recent_ref,
        backtest_strategy=metadata.backtest_strategy or "Rolling-Origin Multi-Window",
        evaluation_windows=metadata.evaluation_windows or 1,
        backtest_mae=float(mae_val),
        backtest_rmse=float(rmse_val),
        vs_naive_pct=vs_naive,
        empirical_coverage_80=metadata.empirical_coverage_80,
        empirical_coverage_95=metadata.empirical_coverage_95,
        interval_notes=metadata.interval_notes,
        data_quality_notes=data_quality_notes,
        limitations=limitations,
    )
