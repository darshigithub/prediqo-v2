"""Automated tests for Time-Series Forecasting Layer."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.forecasting.data_preparation import aggregate_time_series_from_parquet
from app.forecasting.evaluator import calculate_metrics, evaluate_forecast_candidates
from app.forecasting.forecaster import generate_future_forecast, prepare_historical_points
from app.forecasting.model_store import (
    get_forecast_metadata,
    list_forecast_models_for_dataset,
    load_forecast_model,
)
from app.forecasting.models import (
    ForecastPredictRequest,
    ForecastTrainRequest,
)
from app.forecasting.service import ForecastingService
from app.forecasting.trainer import (
    ExponentialSmoothingForecaster,
    LinearTrendForecaster,
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
    get_candidate_forecasters,
)
from app.storage.dataset_store import create_dataset, delete_dataset, get_parquet_path


@pytest.fixture
def synthetic_daily_sales_df() -> pd.DataFrame:
    """Creates a deterministic 60-day transactional dataset."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D").strftime("%Y-%m-%d")
    rows = []
    for i, d in enumerate(dates):
        # 1 to 3 transactions per day
        for t in range(2):
            rows.append({
                "order_id": f"ORD_{i}_{t}",
                "order_date": d,
                "customer_id": f"CUST_{i % 15}",
                "sales_amount": round(50.0 + (i * 1.5) + np.random.uniform(5.0, 20.0), 2),
                "quantity": int(np.random.randint(1, 5)),
            })
    return pd.DataFrame(rows)


@pytest.fixture
def sales_forecast_dataset(synthetic_daily_sales_df):
    """Creates dataset in store and cleans up afterward."""
    ds = create_dataset("csv", "test_sales_forecasting", synthetic_daily_sales_df)
    yield ds
    delete_dataset(ds.dataset_id)


# ---------- 1. Feasibility Tests ----------
def test_forecast_feasibility_detection(sales_forecast_dataset):
    feas = ForecastingService.get_feasibility(sales_forecast_dataset.dataset_id)
    assert feas.forecasting_possible is True
    assert feas.row_count == 120
    assert len(feas.recommended_date_columns) >= 1
    assert feas.recommended_date_columns[0].name == "order_date"

    metric_names = [m.name for m in feas.recommended_metrics]
    assert "sales_amount" in metric_names
    assert "quantity" in metric_names

    # Check stale warning detection (2024 dates vs current date)
    assert feas.is_stale is True
    assert feas.stale_warning is not None


# ---------- 2. DuckDB Aggregation Tests ----------
def test_duckdb_time_series_aggregation(sales_forecast_dataset):
    p_path = get_parquet_path(sales_forecast_dataset.dataset_id)

    # Daily aggregation
    df_daily, stats_daily, _ = aggregate_time_series_from_parquet(
        parquet_path=p_path,
        date_col="order_date",
        metric_col="sales_amount",
        frequency="daily",
        aggregation="SUM",
    )
    assert len(df_daily) == 60
    assert "ds" in df_daily.columns
    assert "y" in df_daily.columns
    assert stats_daily["total_periods"] == 60
    assert stats_daily["start_date"] == "2024-01-01"
    assert stats_daily["end_date"] == "2024-02-29"

    # Weekly aggregation
    df_weekly, stats_weekly, _ = aggregate_time_series_from_parquet(
        parquet_path=p_path,
        date_col="order_date",
        metric_col="sales_amount",
        frequency="weekly",
        aggregation="SUM",
    )
    assert len(df_weekly) >= 8
    assert stats_weekly["total_periods"] >= 8


# ---------- 3. Forecasting Candidate Algorithms Tests ----------
def test_candidate_forecaster_algorithms():
    y = np.array([10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0])
    h = 3

    # Naive
    naive = NaiveForecaster().fit(y)
    p_naive = naive.predict(h)
    assert len(p_naive) == h
    assert np.all(p_naive == 25.0)

    # Seasonal Naive
    s_naive = SeasonalNaiveForecaster(season_length=3).fit(y)
    p_s_naive = s_naive.predict(h)
    assert len(p_s_naive) == h
    assert np.allclose(p_s_naive, [20.0, 22.0, 25.0])

    # Moving Average
    ma = MovingAverageForecaster(window=3).fit(y)
    p_ma = ma.predict(h)
    expected_ma = np.mean([20.0, 22.0, 25.0])
    assert np.allclose(p_ma, expected_ma)

    # Linear Trend
    lt = LinearTrendForecaster(non_negative=True).fit(y)
    p_lt = lt.predict(h)
    assert len(p_lt) == h
    assert p_lt[0] > 25.0  # upward trend

    # Exponential Smoothing
    es = ExponentialSmoothingForecaster().fit(y)
    p_es = es.predict(h)
    assert len(p_es) == h


# ---------- 4. Chronological Backtesting & Metrics Tests ----------
def test_chronological_backtesting_evaluation():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    vals = np.array([100.0 + i * 2.0 for i in range(30)])
    series_df = pd.DataFrame({"ds": dates, "y": vals})

    candidates = get_candidate_forecasters("daily", len(series_df))
    results, best_key, best_summary, backtest_pts, _ = evaluate_forecast_candidates(
        series_df, candidates, horizon=7
    )

    assert len(results) >= 3
    assert any(c.is_best for c in results)
    assert best_summary.primary_metric == "mae"
    assert best_summary.primary_metric_value >= 0.0

    # Verify backtest points are chronological
    assert len(backtest_pts) == 7
    for bp in backtest_pts:
        assert bp.actual > 0
        assert bp.predicted > 0
        assert round(bp.residual, 2) == round(bp.actual - bp.predicted, 2)


def test_metric_zero_safety():
    # When actual values contain zeros, MAPE must be None and explained
    y_true = np.array([0.0, 10.0, 20.0])
    y_pred = np.array([5.0, 12.0, 18.0])
    m = calculate_metrics(y_true, y_pred)
    assert m["mape"] is None
    assert "undefined" in m["mape_note"]
    assert m["mae"] > 0
    assert m["wape"] > 0


# ---------- 5. Future Projection & Uncertainty Intervals ----------
def test_future_projection_and_intervals(sales_forecast_dataset):
    p_path = get_parquet_path(sales_forecast_dataset.dataset_id)
    series_df, _, _ = aggregate_time_series_from_parquet(
        parquet_path=p_path,
        date_col="order_date",
        metric_col="sales_amount",
        frequency="daily",
    )

    model = LinearTrendForecaster().fit(series_df["y"].to_numpy())
    pts = generate_future_forecast(
        series_df=series_df,
        winning_model=model,
        horizon=10,
        frequency="daily",
        backtest_data=[],
        non_negative=True,
    )

    assert len(pts) == 10
    # First forecast point should be strictly after the last historical date
    assert pts[0].date == "2024-03-01"
    assert pts[-1].date == "2024-03-10"

    # Intervals must widen or remain consistent
    for pt in pts:
        assert pt.lower_95 <= pt.lower_80 <= pt.forecast <= pt.upper_80 <= pt.upper_95


# ---------- 6. End-to-End Service Training & Model Persistence ----------
def test_forecasting_service_end_to_end(sales_forecast_dataset):
    req = ForecastTrainRequest(
        dataset_id=sales_forecast_dataset.dataset_id,
        date_column="order_date",
        metric_column="sales_amount",
        frequency="daily",
        aggregation="SUM",
        horizon=14,
    )

    resp = ForecastingService.train_and_forecast(req)
    assert resp.model_id.startswith("fc_")
    assert resp.horizon == 14
    assert resp.frequency == "daily"
    assert len(resp.forecast_data) == 14
    assert len(resp.backtest_data) > 0
    assert len(resp.historical_data) > 0
    assert resp.best_model.primary_metric_value >= 0.0
    assert resp.is_stale is True

    # Test loading from disk
    meta, pts = load_forecast_model(resp.model_id)
    assert meta.model_id == resp.model_id
    assert meta.dataset_id == sales_forecast_dataset.dataset_id
    assert len(pts) == 14

    # Test listing models
    models = list_forecast_models_for_dataset(sales_forecast_dataset.dataset_id)
    assert len(models) >= 1
    assert models[0].model_id == resp.model_id

    # Test predict re-use
    pred_res = ForecastingService.predict(
        ForecastPredictRequest(model_id=resp.model_id, horizon=7)
    )
    assert pred_res.model_id == resp.model_id
    assert len(pred_res.forecast_data) == 7


# ---------- 7. REST API Endpoints Integration Test ----------
def test_forecasting_rest_api_endpoints(sales_forecast_dataset):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Feasibility endpoint
    r_feas = client.get(f"/api/forecast/feasibility/{sales_forecast_dataset.dataset_id}")
    assert r_feas.status_code == 200
    f_json = r_feas.json()
    assert f_json["forecasting_possible"] is True

    # 2. Train endpoint
    r_train = client.post("/api/forecast/train", json={
        "dataset_id": sales_forecast_dataset.dataset_id,
        "date_column": "order_date",
        "metric_column": "sales_amount",
        "frequency": "daily",
        "aggregation": "SUM",
        "horizon": 10,
    })
    assert r_train.status_code == 200
    t_json = r_train.json()
    model_id = t_json["model_id"]
    assert model_id.startswith("fc_")
    assert len(t_json["forecast_data"]) == 10

    # 3. List models
    r_list = client.get(f"/api/forecast/models/{sales_forecast_dataset.dataset_id}")
    assert r_list.status_code == 200
    assert len(r_list.json()["models"]) >= 1

    # 4. Model details
    r_det = client.get(f"/api/forecast/models/{model_id}/details")
    assert r_det.status_code == 200
    assert r_det.json()["model_id"] == model_id

    # 5. Predict endpoint
    r_pred = client.post("/api/forecast/predict", json={
        "model_id": model_id,
        "horizon": 5,
    })
    assert r_pred.status_code == 200
    p_json = r_pred.json()
    assert len(p_json["forecast_data"]) == 5
