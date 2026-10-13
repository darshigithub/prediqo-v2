"""Phase 2 tests: Dataset flexibility, multiple schema variations, and capability detection."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.capabilities.registry import assess_capabilities, assess_dataset_granularity
from app.forecasting.service import ForecastingService
from app.forecasting.models import ForecastTrainRequest
from app.prediction.models import TrainRequest
from app.prediction.service import PredictionService
from app.storage.dataset_store import create_dataset, delete_dataset, get_parquet_path


# ---------- Deterministic Synthetic Datasets (A, B, C, D, E) ----------

@pytest.fixture
def dataset_a():
    """Dataset A — Standard transactional data."""
    np.random.seed(42)
    n = 60
    dates = pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "order_id": [f"ORD_{100 + i}" for i in range(n)],
        "order_date": dates,
        "customer_id": [f"CUST_{i % 10}" for i in range(n)],
        "quantity": np.random.randint(1, 10, size=n),
        "unit_price": np.random.uniform(50.0, 500.0, size=n).round(2),
        "sales_amount": np.random.uniform(100.0, 2000.0, size=n).round(2),
    })
    ds = create_dataset("csv", "test_dataset_a_standard", df)
    yield ds
    delete_dataset(ds.dataset_id)


@pytest.fixture
def dataset_b():
    """Dataset B — Alternative column names."""
    np.random.seed(42)
    n = 60
    dates = pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "invoice_number": [f"INV_{500 + i}" for i in range(n)],
        "purchased_on": dates,
        "buyer_id": [f"BUY_{i % 12}" for i in range(n)],
        "qty": np.random.randint(1, 8, size=n),
        "selling_price": np.random.uniform(40.0, 400.0, size=n).round(2),
        "net_sales": np.random.uniform(80.0, 1500.0, size=n).round(2),
    })
    ds = create_dataset("csv", "test_dataset_b_synonyms", df)
    yield ds
    delete_dataset(ds.dataset_id)


@pytest.fixture
def dataset_c():
    """Dataset C — Aggregated time series."""
    np.random.seed(42)
    n = 45
    dates = pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "date": dates,
        "daily_revenue": np.random.uniform(500.0, 3000.0, size=n).round(2),
    })
    ds = create_dataset("csv", "test_dataset_c_aggregated", df)
    yield ds
    delete_dataset(ds.dataset_id)


@pytest.fixture
def dataset_d():
    """Dataset D — Minimal generic numeric dataset (no dates)."""
    np.random.seed(42)
    n = 50
    df = pd.DataFrame({
        "feature_a": np.random.uniform(1.0, 50.0, size=n).round(2),
        "feature_b": np.random.uniform(10.0, 100.0, size=n).round(2),
        "target_value": np.random.uniform(100.0, 500.0, size=n).round(2),
    })
    ds = create_dataset("csv", "test_dataset_d_generic", df)
    yield ds
    delete_dataset(ds.dataset_id)


@pytest.fixture
def dataset_e():
    """Dataset E — Insufficient data (<10 rows) and missing dates."""
    df = pd.DataFrame({
        "category": ["A", "B", "C", "D"],
        "metric_x": [10.0, 20.0, 30.0, 40.0],
    })
    ds = create_dataset("csv", "test_dataset_e_insufficient", df)
    yield ds
    delete_dataset(ds.dataset_id)


@pytest.fixture
def dataset_order_items():
    """Dataset with line-item repeated orders (multiple rows per order_id)."""
    rows = []
    for order_num in range(20):
        # 3 items per order
        for item in range(3):
            rows.append({
                "order_id": f"ORD_{order_num}",
                "order_date": "2024-01-15",
                "item_name": f"Item_{item}",
                "quantity": 2,
                "total_order_amount": 150.0,  # repeated total for the whole order
            })
    df = pd.DataFrame(rows)
    ds = create_dataset("csv", "test_dataset_order_items", df)
    yield ds
    delete_dataset(ds.dataset_id)


# ---------- 1. Dataset A: Standard Transactional Tests ----------
def test_dataset_a_capabilities(dataset_a):
    caps = assess_capabilities(dataset_a.dataset_id)
    assert caps.capabilities["prediction"]["available"] is True
    assert caps.capabilities["forecasting"]["available"] is True
    assert caps.granularity.likely_granularity == "transaction"
    assert caps.detected_mappings.get("date") == "order_date"
    assert caps.detected_mappings.get("revenue") == "sales_amount"
    assert caps.detected_mappings.get("order") == "order_id"


# ---------- 2. Dataset B: Alternative Column Names Tests ----------
def test_dataset_b_synonyms_detection(dataset_b):
    caps = assess_capabilities(dataset_b.dataset_id)
    assert caps.capabilities["prediction"]["available"] is True
    assert caps.capabilities["forecasting"]["available"] is True

    # Synonyms should be mapped correctly
    assert caps.detected_mappings.get("date") == "purchased_on"
    assert caps.detected_mappings.get("revenue") == "net_sales"
    assert caps.detected_mappings.get("order") == "invoice_number"

    # End-to-end forecasting should succeed with alternative column names
    req = ForecastTrainRequest(
        dataset_id=dataset_b.dataset_id,
        date_column="purchased_on",
        metric_column="net_sales",
        frequency="daily",
        horizon=7,
    )
    res = ForecastingService.train_and_forecast(req)
    assert res.model_id.startswith("fc_")
    assert len(res.forecast_data) == 7

    # End-to-end regression should succeed with alternative column names
    pred_req = TrainRequest(
        dataset_id=dataset_b.dataset_id,
        target_column="net_sales",
        problem_type="regression",
        features=["qty", "selling_price"],
    )
    pred_res = PredictionService.train_model(pred_req)
    assert pred_res.model_id.startswith("model_")


# ---------- 3. Dataset C: Aggregated Time Series Tests ----------
def test_dataset_c_aggregated_series(dataset_c):
    caps = assess_capabilities(dataset_c.dataset_id)
    assert caps.granularity.likely_granularity == "daily_aggregated"
    assert caps.capabilities["forecasting"]["available"] is True

    # Run forecasting on aggregated daily series
    req = ForecastTrainRequest(
        dataset_id=dataset_c.dataset_id,
        date_column="date",
        metric_column="daily_revenue",
        frequency="daily",
        horizon=10,
    )
    res = ForecastingService.train_and_forecast(req)
    assert len(res.forecast_data) == 10


# ---------- 4. Dataset D: Generic Numeric Dataset (No Dates) ----------
def test_dataset_d_generic_numeric(dataset_d):
    caps = assess_capabilities(dataset_d.dataset_id)
    # Regression MUST be eligible
    assert caps.capabilities["prediction"]["available"] is True
    assert "target_value" in caps.capabilities["prediction"]["recommended_targets"]

    # Forecasting MUST NOT be eligible because no dates exist
    assert caps.capabilities["forecasting"]["available"] is False
    assert len(caps.capabilities["forecasting"]["missing_requirements"]) > 0

    # Training regression succeeds
    req = TrainRequest(
        dataset_id=dataset_d.dataset_id,
        target_column="target_value",
        problem_type="regression",
        features=["feature_a", "feature_b"],
    )
    res = PredictionService.train_model(req)
    assert res.best_model.primary_metric == "mae"


# ---------- 5. Dataset E: Insufficient / Incompatible Data ----------
def test_dataset_e_insufficient_handling(dataset_e):
    caps = assess_capabilities(dataset_e.dataset_id)
    # Both should be blocked gracefully due to < 10 rows
    assert caps.capabilities["prediction"]["available"] is False
    assert caps.capabilities["forecasting"]["available"] is False


# ---------- 6. Granularity and Line-Item Repeated Orders ----------
def test_order_item_repeated_totals_detection(dataset_order_items):
    caps = assess_capabilities(dataset_order_items.dataset_id)
    assert caps.granularity.likely_granularity == "order_item"
    assert caps.granularity.has_repeated_orders is True
    assert caps.granularity.distinct_id_ratio is not None
    assert caps.granularity.distinct_id_ratio < 0.5  # 20 orders across 60 rows
    assert "Do not sum repeated order totals directly" in caps.granularity.aggregation_policy_note


# ---------- 7. Manual Mapping Overrides & Invalid Rejections ----------
def test_manual_mapping_overrides(dataset_b):
    # Valid override
    overrides = {"date": "purchased_on", "target": "net_sales"}
    caps = assess_capabilities(dataset_b.dataset_id, manual_overrides=overrides)
    assert caps.detected_mappings["date"] == "purchased_on"
    assert caps.mapping_confidences["date"] == 1.0

    # Invalid override (column does not exist)
    with pytest.raises(ValueError, match="does not exist in dataset"):
        assess_capabilities(
            dataset_b.dataset_id,
            manual_overrides={"date": "completely_non_existent_column"},
        )


# ---------- 8. Capability REST API Endpoints ----------
def test_capability_api_endpoints(dataset_b):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # GET capabilities
    r_get = client.get(f"/api/capabilities/{dataset_b.dataset_id}")
    assert r_get.status_code == 200
    get_json = r_get.json()
    assert get_json["capabilities"]["forecasting"]["available"] is True
    assert get_json["capabilities"]["prediction"]["available"] is True

    # POST overrides
    r_post = client.post(
        f"/api/capabilities/{dataset_b.dataset_id}",
        json={"mappings": {"revenue": "net_sales"}},
    )
    assert r_post.status_code == 200
    post_json = r_post.json()
    assert post_json["detected_mappings"]["revenue"] == "net_sales"
    assert post_json["mapping_confidences"]["revenue"] == 1.0
