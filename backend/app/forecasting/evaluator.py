"""Chronological backtesting, metric calculation, and baseline comparison."""
from __future__ import annotations

import copy
import logging
from typing import Any, Optional
import numpy as np
import pandas as pd

from .models import (
    BacktestPoint,
    BestForecastModelSummary,
    CandidateForecastModelResult,
)
from .trainer import BaseForecaster

logger = logging.getLogger(__name__)


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    """Calculates MAE, RMSE, WAPE, and MAPE with zero-safety."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    # WAPE (Weighted Absolute Percentage Error)
    sum_actual = float(np.sum(np.abs(y_true)))
    if sum_actual > 0:
        wape = round(float(np.sum(np.abs(y_true - y_pred)) / sum_actual * 100.0), 2)
    else:
        wape = None

    # MAPE: safe handling of zero or near-zero denominators
    near_zeros = np.sum(np.abs(y_true) < 1e-4)
    if near_zeros > 0:
        mape = None
        mape_note = "MAPE undefined: actual series contains zeros in validation window."
    else:
        mape_arr = np.abs((y_true - y_pred) / y_true) * 100.0
        mape = round(float(np.mean(mape_arr)), 2)
        mape_note = None

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "wape": wape,
        "mape": mape,
        "mape_note": mape_note,
    }


def evaluate_forecast_candidates(
    series_df: pd.DataFrame,
    candidate_models: dict[str, BaseForecaster],
    horizon: int = 14,
    backtest_strategy: str = "rolling_origin",
) -> tuple[
    list[CandidateForecastModelResult],
    str,
    BestForecastModelSummary,
    list[BacktestPoint],
    dict[str, np.ndarray],
    dict[str, Any],
]:
    """Evaluates candidate models using chronological rolling-origin backtesting."""
    y_all = series_df["y"].to_numpy(dtype=float)
    ds_all = series_df["ds"].to_numpy()
    n = len(y_all)

    # Determine backtest window size H
    h_backtest = min(horizon, max(2, n // 4))

    # Setup multi-window rolling origin when series length permits
    n_windows = 1
    eval_strategy = "single_cutoff"
    cutoffs = [n - h_backtest]

    if backtest_strategy == "rolling_origin" and n >= (2 * h_backtest + 4):
        n_windows = min(3, max(1, (n - h_backtest) // h_backtest))
        cutoffs = [n - (i * h_backtest) for i in range(n_windows, 0, -1)]
        eval_strategy = "rolling_origin"

    candidate_results: list[CandidateForecastModelResult] = []
    backtest_predictions: dict[str, np.ndarray] = {}
    naive_mae: Optional[float] = None

    # Final holdout window data for plotting and coverage
    final_cutoff = cutoffs[-1]
    y_final_val = y_all[final_cutoff : final_cutoff + h_backtest]
    ds_final_val = ds_all[final_cutoff : final_cutoff + h_backtest]

    # Evaluate each candidate across the evaluation window(s)
    for key, model in candidate_models.items():
        try:
            window_maes: list[float] = []
            window_rmses: list[float] = []
            window_wapes: list[float] = []
            window_mapes: list[float] = []
            last_preds: Optional[np.ndarray] = None

            for cutoff in cutoffs:
                y_tr = y_all[:cutoff]
                y_va = y_all[cutoff : cutoff + h_backtest]

                eval_model = copy.deepcopy(model)
                eval_model.fit(y_tr)
                preds = eval_model.predict(len(y_va))
                last_preds = preds

                m = calculate_metrics(y_va, preds)
                window_maes.append(m["mae"])
                window_rmses.append(m["rmse"])
                if m["wape"] is not None:
                    window_wapes.append(m["wape"])
                if m["mape"] is not None:
                    window_mapes.append(m["mape"])

            backtest_predictions[key] = last_preds if last_preds is not None else np.zeros(len(y_final_val))

            avg_metrics = {
                "mae": round(float(np.mean(window_maes)), 4),
                "rmse": round(float(np.mean(window_rmses)), 4),
                "wape": round(float(np.mean(window_wapes)), 2) if window_wapes else None,
                "mape": round(float(np.mean(window_mapes)), 2) if window_mapes else None,
                "mape_note": None if window_mapes else "MAPE undefined: actual series contains zeros in validation window.",
            }

            is_baseline = (key == "naive")
            if is_baseline:
                naive_mae = avg_metrics["mae"]

            candidate_results.append(
                CandidateForecastModelResult(
                    algorithm=model.name,
                    metrics=avg_metrics,
                    is_best=False,
                    is_baseline=is_baseline,
                    training_time_ms=getattr(model, "training_time_ms", None),
                )
            )
        except Exception as e:
            logger.warning("Backtesting failed for forecaster %s: %s", key, e)

    if not candidate_results:
        raise RuntimeError("All candidate forecasting models failed during backtesting.")

    # Compare against Naive baseline
    for cand in candidate_results:
        cand_mae = cand.metrics.get("mae", float("inf"))
        if naive_mae is not None and naive_mae > 0:
            imp_pct = round(((naive_mae - cand_mae) / naive_mae) * 100.0, 1)
            cand.vs_naive_pct = imp_pct

    # Select best model by lowest validation MAE
    best_cand = min(candidate_results, key=lambda c: c.metrics.get("mae", float("inf")))
    best_cand.is_best = True

    best_key = "naive"
    for k, m in candidate_models.items():
        if m.name == best_cand.algorithm:
            best_key = k
            break

    # Construct selection reason
    window_desc = f"{n_windows} rolling-origin window(s)" if n_windows > 1 else "chronological holdout window"
    if best_cand.is_baseline:
        selection_reason = (
            f"{best_cand.algorithm} selected as the most accurate predictor (MAE: {best_cand.metrics['mae']}) "
            f"across {window_desc}."
        )
    elif best_cand.vs_naive_pct is not None and best_cand.vs_naive_pct > 0:
        selection_reason = (
            f"{best_cand.algorithm} selected with lowest validation MAE ({best_cand.metrics['mae']}), "
            f"outperforming the naive benchmark by {best_cand.vs_naive_pct}% across {window_desc}."
        )
    else:
        selection_reason = (
            f"{best_cand.algorithm} selected with lowest validation MAE ({best_cand.metrics['mae']}) across {window_desc}."
        )

    # Generate Backtest points for charting from final holdout
    winning_preds = backtest_predictions.get(best_key, y_final_val)
    backtest_data: list[BacktestPoint] = []
    for d, a, p in zip(ds_final_val, y_final_val, winning_preds):
        d_str = pd.to_datetime(d).strftime("%Y-%m-%d")
        a_val = round(float(a), 2)
        p_val = round(float(p), 2)
        backtest_data.append(
            BacktestPoint(
                date=d_str,
                actual=a_val,
                predicted=p_val,
                residual=round(a_val - p_val, 2),
            )
        )

    # Measure empirical coverage of 80% and 95% intervals on final holdout
    resids = y_final_val - winning_preds
    sigma_e = float(np.sqrt(np.mean(resids**2))) if len(resids) > 0 else 1.0
    if sigma_e < 1e-4:
        sigma_e = max(1.0, float(np.mean(np.abs(y_all)) * 0.05))

    in_80 = 0
    in_95 = 0
    for idx, (act, pred) in enumerate(zip(y_final_val, winning_preds)):
        step_sigma = sigma_e * np.sqrt(1.0 + 0.08 * idx)
        if (pred - 1.282 * step_sigma) <= act <= (pred + 1.282 * step_sigma):
            in_80 += 1
        if (pred - 1.960 * step_sigma) <= act <= (pred + 1.960 * step_sigma):
            in_95 += 1

    emp_cov_80 = round(float(in_80 / max(1, len(y_final_val)) * 100.0), 1)
    emp_cov_95 = round(float(in_95 / max(1, len(y_final_val)) * 100.0), 1)

    interval_notes = (
        f"Prediction intervals are approximate (residual sigma scaled by sqrt(h)). "
        f"Holdout empirical coverage: nominal 80% achieved {emp_cov_80}%, nominal 95% achieved {emp_cov_95}% "
        f"(N={len(y_final_val)} observations)."
    )

    best_summary = BestForecastModelSummary(
        algorithm=best_cand.algorithm,
        primary_metric="mae",
        primary_metric_value=best_cand.metrics["mae"],
        metrics=best_cand.metrics,
        vs_naive_pct=best_cand.vs_naive_pct,
        selection_reason=selection_reason,
        evaluation_windows=n_windows,
        backtest_strategy=eval_strategy,
        empirical_coverage_80=emp_cov_80,
        empirical_coverage_95=emp_cov_95,
        coverage_sample_size=len(y_final_val),
        interval_notes=interval_notes,
    )

    return candidate_results, best_key, best_summary, backtest_data, backtest_predictions


