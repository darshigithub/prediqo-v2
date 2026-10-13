"""Candidate time-series forecasting algorithms and baselines."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BaseForecaster:
    """Abstract base class for time-series forecasters."""

    def __init__(self, name: str):
        self.name = name
        self.is_fitted = False
        self.training_time_ms: float = 0.0

    def fit(self, y: np.ndarray, ds: Optional[np.ndarray] = None) -> BaseForecaster:
        raise NotImplementedError

    def predict(self, horizon: int) -> np.ndarray:
        raise NotImplementedError

    def get_params(self) -> dict[str, Any]:
        return {}


class NaiveForecaster(BaseForecaster):
    """Naive baseline forecaster: projects the last observed value."""

    def __init__(self):
        super().__init__("Naive (Last Value)")
        self.last_value: float = 0.0

    def fit(self, y: np.ndarray, ds: Optional[np.ndarray] = None) -> BaseForecaster:
        t0 = time.perf_counter()
        if len(y) == 0:
            raise ValueError("Training series cannot be empty.")
        self.last_value = float(y[-1])
        self.is_fitted = True
        self.training_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return self

    def predict(self, horizon: int) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")
        return np.full(horizon, self.last_value, dtype=float)

    def get_params(self) -> dict[str, Any]:
        return {"last_value": self.last_value}


class SeasonalNaiveForecaster(BaseForecaster):
    """Seasonal naive forecaster: repeats the observations from the most recent cycle."""

    def __init__(self, season_length: int = 7):
        super().__init__(f"Seasonal Naive (Season {season_length})")
        self.season_length = season_length
        self.last_season: np.ndarray = np.array([])

    def fit(self, y: np.ndarray, ds: Optional[np.ndarray] = None) -> BaseForecaster:
        t0 = time.perf_counter()
        if len(y) < self.season_length:
            # Fall back to repeating available values
            self.last_season = np.asarray(y, dtype=float)
        else:
            self.last_season = np.asarray(y[-self.season_length:], dtype=float)
        self.is_fitted = True
        self.training_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return self

    def predict(self, horizon: int) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")
        m = len(self.last_season)
        if m == 0:
            return np.zeros(horizon, dtype=float)
        # Cycle through last season
        indices = np.arange(horizon) % m
        return self.last_season[indices]

    def get_params(self) -> dict[str, Any]:
        return {"season_length": self.season_length}


class MovingAverageForecaster(BaseForecaster):
    """Moving average forecaster: projects the mean of the last W observations."""

    def __init__(self, window: int = 7):
        super().__init__(f"Moving Average (Window {window})")
        self.window = window
        self.ma_value: float = 0.0

    def fit(self, y: np.ndarray, ds: Optional[np.ndarray] = None) -> BaseForecaster:
        t0 = time.perf_counter()
        w = min(self.window, len(y))
        if w == 0:
            raise ValueError("Training series cannot be empty.")
        self.ma_value = float(np.mean(y[-w:]))
        self.is_fitted = True
        self.training_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return self

    def predict(self, horizon: int) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")
        return np.full(horizon, self.ma_value, dtype=float)

    def get_params(self) -> dict[str, Any]:
        return {"window": self.window, "ma_value": self.ma_value}


class LinearTrendForecaster(BaseForecaster):
    """Linear trend forecaster: fits y = beta_0 + beta_1 * t via ordinary least squares."""

    def __init__(self, non_negative: bool = True):
        super().__init__("Linear Trend Regression")
        self.non_negative = non_negative
        self.slope: float = 0.0
        self.intercept: float = 0.0
        self.n_samples: int = 0

    def fit(self, y: np.ndarray, ds: Optional[np.ndarray] = None) -> BaseForecaster:
        t0 = time.perf_counter()
        self.n_samples = len(y)
        if self.n_samples < 2:
            self.slope = 0.0
            self.intercept = float(y[0]) if self.n_samples == 1 else 0.0
        else:
            t = np.arange(self.n_samples, dtype=float)
            # OLS
            p = np.polyfit(t, y, deg=1)
            self.slope = float(p[0])
            self.intercept = float(p[1])
        self.is_fitted = True
        self.training_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return self

    def predict(self, horizon: int) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")
        t_future = np.arange(self.n_samples, self.n_samples + horizon, dtype=float)
        preds = self.intercept + self.slope * t_future
        if self.non_negative:
            preds = np.clip(preds, a_min=0.0, a_max=None)
        return preds

    def get_params(self) -> dict[str, Any]:
        return {
            "slope": round(self.slope, 4),
            "intercept": round(self.intercept, 4),
            "n_samples": self.n_samples,
        }


class ExponentialSmoothingForecaster(BaseForecaster):
    """Simple Exponential Smoothing (SES) with grid-searched optimal alpha."""

    def __init__(self, alpha: Optional[float] = None):
        super().__init__("Exponential Smoothing")
        self.alpha = alpha
        self.optimal_alpha: float = 0.3
        self.level: float = 0.0

    def fit(self, y: np.ndarray, ds: Optional[np.ndarray] = None) -> BaseForecaster:
        t0 = time.perf_counter()
        n = len(y)
        if n == 0:
            raise ValueError("Training series cannot be empty.")
        if n == 1:
            self.level = float(y[0])
            self.optimal_alpha = 0.3
            self.is_fitted = True
            return self

        best_alpha = self.alpha if self.alpha is not None else 0.3
        best_sse = float("inf")

        candidate_alphas = [self.alpha] if self.alpha is not None else [0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9]

        for a in candidate_alphas:
            lvl = float(y[0])
            sse = 0.0
            for val in y[1:]:
                err = val - lvl
                sse += err * err
                lvl = a * val + (1.0 - a) * lvl
            if sse < best_sse:
                best_sse = sse
                best_alpha = a

        # Compute final level with best_alpha
        lvl = float(y[0])
        for val in y[1:]:
            lvl = best_alpha * val + (1.0 - best_alpha) * lvl

        self.optimal_alpha = float(best_alpha)
        self.level = float(lvl)
        self.is_fitted = True
        self.training_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return self

    def predict(self, horizon: int) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")
        return np.full(horizon, self.level, dtype=float)

    def get_params(self) -> dict[str, Any]:
        return {"alpha": round(self.optimal_alpha, 3), "level": round(self.level, 4)}


def get_candidate_forecasters(
    frequency: str, series_length: int, non_negative: bool = True
) -> dict[str, BaseForecaster]:
    """Returns candidate forecasters appropriate for frequency and length."""
    freq = frequency.lower()
    candidates: dict[str, BaseForecaster] = {
        "naive": NaiveForecaster(),
        "moving_average": MovingAverageForecaster(window=min(7, max(2, series_length // 4))),
        "linear_trend": LinearTrendForecaster(non_negative=non_negative),
        "exponential_smoothing": ExponentialSmoothingForecaster(),
    }

    # Seasonal Naive: check seasonality
    if freq == "daily" and series_length >= 14:
        candidates["seasonal_naive"] = SeasonalNaiveForecaster(season_length=7)
    elif freq == "weekly" and series_length >= 8:
        candidates["seasonal_naive"] = SeasonalNaiveForecaster(season_length=4)
    elif freq == "monthly" and series_length >= 24:
        candidates["seasonal_naive"] = SeasonalNaiveForecaster(season_length=12)

    return candidates
