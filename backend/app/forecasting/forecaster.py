"""Future forecast generation, interval estimation, and timestamp alignment."""
from __future__ import annotations

import logging
from typing import Optional
import numpy as np
import pandas as pd

from .data_preparation import get_pandas_freq_alias
from .models import BacktestPoint, ForecastPoint, HistoricalPoint
from .trainer import BaseForecaster

logger = logging.getLogger(__name__)


def generate_future_forecast(
    series_df: pd.DataFrame,
    winning_model: BaseForecaster,
    horizon: int,
    frequency: str,
    backtest_data: list[BacktestPoint],
    non_negative: bool = True,
) -> list[ForecastPoint]:
    """Fits the winning model on all historical data and generates future forecast points with intervals."""
    y_all = series_df["y"].to_numpy(dtype=float)
    winning_model.fit(y_all)
    forecast_values = winning_model.predict(horizon)

    # Compute empirical residual standard error for prediction intervals
    if backtest_data:
        residuals = [bp.residual for bp in backtest_data]
        sigma_e = float(np.sqrt(np.mean(np.array(residuals) ** 2)))
    else:
        sigma_e = float(np.std(y_all)) if len(y_all) > 1 else 1.0

    # Prevent zero sigma
    if sigma_e < 1e-4:
        sigma_e = max(1.0, float(np.mean(np.abs(y_all)) * 0.05))

    # Generate future timestamps
    last_ds = pd.to_datetime(series_df["ds"].max())
    freq_alias = get_pandas_freq_alias(frequency)
    future_dates = pd.date_range(start=last_ds, periods=horizon + 1, freq=freq_alias)[1:]

    forecast_points: list[ForecastPoint] = []
    for step_idx, (dt, f_val) in enumerate(zip(future_dates, forecast_values)):
        step_h = step_idx + 1
        # Uncertainty widens with forecast horizon sqrt(h)
        step_sigma = sigma_e * np.sqrt(1.0 + 0.08 * (step_h - 1))

        # 80% confidence interval (z = 1.282)
        l80 = f_val - 1.282 * step_sigma
        u80 = f_val + 1.282 * step_sigma

        # 95% confidence interval (z = 1.960)
        l95 = f_val - 1.960 * step_sigma
        u95 = f_val + 1.960 * step_sigma

        if non_negative:
            f_val = max(0.0, f_val)
            l80 = max(0.0, l80)
            u80 = max(0.0, u80)
            l95 = max(0.0, l95)
            u95 = max(0.0, u95)

        forecast_points.append(
            ForecastPoint(
                date=dt.strftime("%Y-%m-%d"),
                forecast=round(float(f_val), 2),
                lower_80=round(float(l80), 2),
                upper_80=round(float(u80), 2),
                lower_95=round(float(l95), 2),
                upper_95=round(float(u95), 2),
            )
        )

    return forecast_points


def prepare_historical_points(
    series_df: pd.DataFrame, max_points: int = 120
) -> list[HistoricalPoint]:
    """Prepares chronological historical points formatted for chart visualization."""
    subset = series_df.tail(max_points)
    points: list[HistoricalPoint] = []
    for _, row in subset.iterrows():
        d_str = pd.to_datetime(row["ds"]).strftime("%Y-%m-%d")
        points.append(HistoricalPoint(date=d_str, value=round(float(row["y"]), 2)))
    return points
