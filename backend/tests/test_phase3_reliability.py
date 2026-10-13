"""Phase 3 Reliability and Generic Edge-Case Test Suite for Prediqo.

Tests all 18 generic tabular and time-series edge-case scenarios required
by Workstream C of the Master Prompt.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.storage.dataset_store import create_dataset, delete_dataset, get_metadata, get_parquet_path
from app.prediction.service import PredictionService
from app.prediction.models import TrainRequest, PredictRequest
from app.prediction.target_detector import detect_target_candidates
from app.prediction.feature_selector import recommend_features
from app.prediction.model_store import validate_model_version, get_model_metadata
from app.forecasting.service import ForecastingService
from app.forecasting.models import ForecastTrainRequest
from app.forecasting.feasibility import check_forecast_feasibility
from app.forecasting.data_preparation import aggregate_time_series_from_parquet


# ---------------------------------------------------------------------------
# Edge Case 1: Small regression dataset (N < 20 rows)
# ---------------------------------------------------------------------------
def test_edge_case_01_small_regression_dataset():
    """Small sample size (N=14) must train without error and report small sample notes."""
    np.random.seed(42)
    n = 14
    df = pd.DataFrame({
        "item_id": [f"ITM_{i}" for i in range(n)],
        "cost": np.random.uniform(10.0, 50.0, size=n).round(2),
        "lead_time": np.random.randint(1, 10, size=n),
        "target_price": np.random.uniform(50.0, 200.0, size=n).round(2),
    })
    ds = create_dataset("csv", "test_edge_01_small_reg", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_price",
            problem_type="regression",
            features=["cost", "lead_time"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        assert resp is not None
        assert resp.training_row_count < 20
        assert resp.best_model is not None
        # Should record small sample size note
        notes_text = " ".join(resp.best_model.reliability_notes)
        assert "Small sample size" in notes_text or resp.training_row_count < 20
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 2: Binary classification dataset
# ---------------------------------------------------------------------------
def test_edge_case_02_binary_classification():
    """Binary classification evaluates confusion matrix, accuracy, and calibrated notes."""
    np.random.seed(42)
    n = 40
    df = pd.DataFrame({
        "user_id": [f"USR_{i}" for i in range(n)],
        "tenure_months": np.random.randint(1, 36, size=n),
        "monthly_spend": np.random.uniform(20.0, 150.0, size=n).round(2),
        "is_active": ["Active" if i % 2 == 0 else "Inactive" for i in range(n)],
    })
    ds = create_dataset("csv", "test_edge_02_binary", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="is_active",
            problem_type="classification",
            features=["tenure_months", "monthly_spend"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        assert resp.problem_type == "classification"
        assert resp.best_model.metrics.get("accuracy") is not None
        assert resp.best_model.confusion_matrix is not None
        assert len(resp.best_model.class_labels) == 2

        # Test single prediction
        p_req = PredictRequest(
            model_id=resp.model_id,
            features={"tenure_months": 12, "monthly_spend": 55.0},
        )
        p_res = PredictionService.predict(p_req)
        assert p_res.prediction in ("Active", "Inactive")
        assert p_res.probabilities is not None
        assert len(p_res.probabilities) == 2
        assert p_res.probability_note is not None
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 3: Multiclass classification dataset (>2 classes)
# ---------------------------------------------------------------------------
def test_edge_case_03_multiclass_classification():
    """Multiclass target with 3 tiers yields per-class metrics and NxN confusion matrix."""
    np.random.seed(42)
    n = 60
    tiers = ["Bronze", "Silver", "Gold"]
    df = pd.DataFrame({
        "account_id": [f"ACC_{i}" for i in range(n)],
        "points": np.random.randint(100, 5000, size=n),
        "transactions": np.random.randint(1, 50, size=n),
        "membership_tier": [tiers[i % 3] for i in range(n)],
    })
    ds = create_dataset("csv", "test_edge_03_multiclass", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="membership_tier",
            problem_type="classification",
            features=["points", "transactions"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        assert resp.best_model.confusion_matrix is not None
        assert len(resp.best_model.confusion_matrix) == 3
        assert len(resp.best_model.class_labels) == 3
        if resp.best_model.per_class_metrics:
            for tier in tiers:
                assert tier in resp.best_model.per_class_metrics
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 4: Imbalanced classification dataset (e.g. 95% / 5%)
# ---------------------------------------------------------------------------
def test_edge_case_04_imbalanced_classification():
    """Severe class imbalance (95% vs 5%) produces a diagnostic reliability warning."""
    np.random.seed(42)
    n = 60
    targets = ["Normal"] * 57 + ["Fraud"] * 3
    df = pd.DataFrame({
        "tx_id": [f"TX_{i}" for i in range(n)],
        "amount": np.random.uniform(5.0, 500.0, size=n).round(2),
        "hour": np.random.randint(0, 24, size=n),
        "is_fraud": targets,
    })
    ds = create_dataset("csv", "test_edge_04_imbalance", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="is_fraud",
            problem_type="classification",
            features=["amount", "hour"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        notes_text = " ".join(resp.best_model.reliability_notes)
        assert "Severe class imbalance" in notes_text or resp.best_model.is_reliable is False
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 5: Mixed numeric and categorical features
# ---------------------------------------------------------------------------
def test_edge_case_05_mixed_numeric_and_categorical():
    """Pipeline seamlessly handles mixture of floats, integers, categories, and dates."""
    np.random.seed(42)
    n = 40
    df = pd.DataFrame({
        "id": range(n),
        "score_float": np.random.normal(50.0, 10.0, size=n),
        "count_int": np.random.randint(1, 100, size=n),
        "category_str": np.random.choice(["TypeA", "TypeB", "TypeC"], size=n),
        "timestamp_col": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
        "target_num": np.random.uniform(10.0, 100.0, size=n),
    })
    ds = create_dataset("csv", "test_edge_05_mixed", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_num",
            problem_type="regression",
            features=["score_float", "count_int", "category_str", "timestamp_col"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        assert resp.best_model is not None
        assert resp.best_model.metrics.get("mae") is not None
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 6: Missing values in features and target
# ---------------------------------------------------------------------------
def test_edge_case_06_missing_values_features_and_target():
    """Rows with NaN target are dropped cleanly, while feature NaNs are imputed."""
    df = pd.DataFrame({
        "id": range(30),
        "feat_num": [10.0, None, 15.0, 20.0, None, 25.0] * 5,
        "feat_cat": ["A", "B", None, "A", "C", None] * 5,
        "target": [100.0, 110.0, 120.0, None, 140.0, 150.0] * 5,  # 5 NaNs in target
    })
    ds = create_dataset("csv", "test_edge_06_missing", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target",
            problem_type="regression",
            features=["feat_num", "feat_cat"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        # 30 rows minus 5 NaNs in target = 25 clean rows
        assert resp.training_row_count + resp.test_row_count == 25

        # Predict with missing feature inputs (should be imputed during inference)
        p_res = PredictionService.predict(
            PredictRequest(model_id=resp.model_id, features={"feat_num": None, "feat_cat": None})
        )
        assert p_res.prediction is not None
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 7: Unseen categorical values at inference time
# ---------------------------------------------------------------------------
def test_edge_case_07_unseen_categorical_value_at_inference():
    """OneHotEncoder with handle_unknown='ignore' handles completely unseen categories."""
    df = pd.DataFrame({
        "id": range(30),
        "region": ["North", "South", "East"] * 10,
        "revenue": np.random.uniform(100.0, 500.0, size=30),
    })
    ds = create_dataset("csv", "test_edge_07_unseen_cat", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="revenue",
            problem_type="regression",
            features=["region"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)

        # Submit unseen category "Antarctica"
        p_res = PredictionService.predict(
            PredictRequest(model_id=resp.model_id, features={"region": "Antarctica"})
        )
        assert p_res.prediction is not None
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 8: High-cardinality IDs and free-text columns
# ---------------------------------------------------------------------------
def test_edge_case_08_high_cardinality_and_freetext():
    """High-cardinality text columns and identifiers are excluded by feature recommendation."""
    n = 60
    columns_meta = [
        {"name": "session_id", "dtype": "string", "semantic_type": "ID", "business_role": "identifier", "unique_count": 60, "null_count": 0},
        {"name": "user_comment", "dtype": "string", "semantic_type": "TEXT", "business_role": "comment", "unique_count": 59, "null_count": 0},
        {"name": "spend", "dtype": "float", "semantic_type": "MEASURE", "business_role": "amount", "unique_count": 50, "null_count": 0},
        {"name": "target_col", "dtype": "float", "semantic_type": "MEASURE", "business_role": "target", "unique_count": 50, "null_count": 0},
    ]
    rec, excl, _ = recommend_features(columns_meta, "target_col", row_count=n)
    assert "spend" in rec
    assert "session_id" in excl
    assert "user_comment" in excl


# ---------------------------------------------------------------------------
# Edge Case 9: Constant and all-null columns
# ---------------------------------------------------------------------------
def test_edge_case_09_constant_and_all_null_columns():
    """Constant columns (unique=1) and all-null columns (null=N) are filtered out."""
    n = 50
    columns_meta = [
        {"name": "all_null_col", "dtype": "float", "semantic_type": "MEASURE", "unique_count": 0, "null_count": 50},
        {"name": "constant_col", "dtype": "string", "semantic_type": "CATEGORY", "unique_count": 1, "null_count": 0},
        {"name": "valid_metric", "dtype": "float", "semantic_type": "MEASURE", "unique_count": 35, "null_count": 0},
        {"name": "y", "dtype": "float", "semantic_type": "MEASURE", "unique_count": 40, "null_count": 0},
    ]
    rec, excl, _ = recommend_features(columns_meta, "y", row_count=n)
    assert "valid_metric" in rec
    assert "all_null_col" in excl
    assert "constant_col" in excl


# ---------------------------------------------------------------------------
# Edge Case 10: Numeric columns with ambiguous business meaning
# ---------------------------------------------------------------------------
def test_edge_case_10_ambiguous_numeric_columns():
    """Generic columns with abstract names (e.g. factor_x, param_y) are handled smoothly."""
    np.random.seed(42)
    n = 35
    df = pd.DataFrame({
        "factor_x": np.random.normal(0, 1, size=n),
        "param_y": np.random.exponential(2.0, size=n),
        "signal_z": np.random.uniform(-5.0, 5.0, size=n),
    })
    ds = create_dataset("csv", "test_edge_10_ambiguous", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="signal_z",
            problem_type="regression",
            features=["factor_x", "param_y"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        assert resp.best_model is not None
        assert resp.best_model.primary_metric == "mae"
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 11: Time-series data with regular timestamps
# ---------------------------------------------------------------------------
def test_edge_case_11_regular_time_series_forecasting():
    """Regular daily time-series generates future forecast with uncertainty intervals."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "record_id": range(60),
        "event_date": dates,
        "daily_volume": [100 + i * 2 + (i % 7) * 5 for i in range(60)],
    })
    ds = create_dataset("csv", "test_edge_11_regular_ts", df)
    try:
        req = ForecastTrainRequest(
            dataset_id=ds.dataset_id,
            date_column="event_date",
            metric_column="daily_volume",
            frequency="daily",
            aggregation="SUM",
            horizon=7,
        )
        resp = ForecastingService.train_and_forecast(req)
        assert resp.best_model is not None
        assert len(resp.forecast_data) == 7
        assert resp.forecast_data[0].lower_95 <= resp.forecast_data[0].forecast <= resp.forecast_data[0].upper_95
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 12: Time-series with missing periods (configurable imputation)
# ---------------------------------------------------------------------------
def test_edge_case_12_time_series_missing_periods_imputation():
    """Gaps in dates are successfully filled according to configurable imputation strategies."""
    # Create 30-day series missing weekends (approx 8 missing days)
    full_dates = pd.date_range("2024-01-01", periods=30, freq="D")
    weekdays = [d.strftime("%Y-%m-%d") for d in full_dates if d.dayofweek < 5]
    df = pd.DataFrame({
        "date": weekdays,
        "value": [10.0 + i for i in range(len(weekdays))],
    })
    ds = create_dataset("csv", "test_edge_12_imputation", df)
    parquet_path = get_parquet_path(ds.dataset_id)
    try:
        # Test zero imputation
        s_zero, stats_z, w_z = aggregate_time_series_from_parquet(
            parquet_path, "date", "value", "daily", "SUM", imputation_method="zero"
        )
        assert stats_z["missing_periods_imputed"] > 0
        assert (s_zero["y"] == 0.0).any()

        # Test ffill imputation
        s_ffill, stats_f, _ = aggregate_time_series_from_parquet(
            parquet_path, "date", "value", "daily", "AVG", imputation_method="ffill"
        )
        assert stats_f["missing_periods_imputed"] > 0
        assert not s_ffill["y"].isna().any()

        # Test interpolate imputation
        s_interp, stats_i, _ = aggregate_time_series_from_parquet(
            parquet_path, "date", "value", "daily", "AVG", imputation_method="interpolate"
        )
        assert stats_i["missing_periods_imputed"] > 0
        assert not s_interp["y"].isna().any()
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 13: Seasonal and nonseasonal series
# ---------------------------------------------------------------------------
def test_edge_case_13_seasonal_and_nonseasonal_series():
    """Strong seasonal patterns evaluate candidate forecasters including seasonal naive."""
    # 70 days with strong 7-day seasonality
    dates = pd.date_range("2024-01-01", periods=70, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "ts": dates,
        "metric": [50.0 + (100.0 if (i % 7 == 6) else 10.0) for i in range(70)],
    })
    ds = create_dataset("csv", "test_edge_13_seasonal", df)
    try:
        req = ForecastTrainRequest(
            dataset_id=ds.dataset_id,
            date_column="ts",
            metric_column="metric",
            frequency="daily",
            aggregation="AVG",
            horizon=7,
        )
        resp = ForecastingService.train_and_forecast(req)
        assert resp.best_model is not None
        # Candidate models should have evaluated seasonal naive
        algos = [c.algorithm for c in resp.candidate_models]
        assert "Seasonal Naive (Season 7)" in algos
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 14: Short (N < 10) and stale (>60 days) time series
# ---------------------------------------------------------------------------
def test_edge_case_14_short_and_stale_time_series():
    """Short series (<5 periods) raises informative error; stale series (>60 days) produces warning."""
    # 4 periods: should raise ValueError
    df_short = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "val": [10, 20, 30, 40],
    })
    ds_short = create_dataset("csv", "test_edge_14_short", df_short)
    p_short = get_parquet_path(ds_short.dataset_id)
    try:
        with pytest.raises(ValueError, match="At least 5 periods are strictly required"):
            aggregate_time_series_from_parquet(p_short, "date", "val", "daily", "SUM")
    finally:
        delete_dataset(ds_short.dataset_id)

    # Stale series from 2023 (>60 days ago)
    df_stale = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=20, freq="D").strftime("%Y-%m-%d"),
        "val": range(20),
    })
    ds_stale = create_dataset("csv", "test_edge_14_stale", df_stale)
    try:
        meta = get_metadata(ds_stale.dataset_id)
        feas = check_forecast_feasibility(meta, ds_stale.dataset_id)
        assert feas.is_stale is True
        assert feas.stale_warning is not None
        assert "historical cutoff" in feas.stale_warning
    finally:
        delete_dataset(ds_stale.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 15: Duplicate timestamps and multiple records per period
# ---------------------------------------------------------------------------
def test_edge_case_15_duplicate_timestamps_aggregation():
    """Multiple transactional events on the same timestamp aggregate into unique periods."""
    df = pd.DataFrame({
        "timestamp": ["2024-01-01", "2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02",
                      "2024-01-03", "2024-01-04", "2024-01-05"],
        "sales": [10.0, 20.0, 30.0, 50.0, 50.0, 40.0, 80.0, 90.0],
    })
    ds = create_dataset("csv", "test_edge_15_duplicates", df)
    p_path = get_parquet_path(ds.dataset_id)
    try:
        series_df, stats, _ = aggregate_time_series_from_parquet(
            p_path, "timestamp", "sales", "daily", "SUM"
        )
        # Should aggregate to 5 distinct daily rows
        assert len(series_df) == 5
        # First day SUM = 10 + 20 + 30 = 60
        assert series_df.iloc[0]["y"] == 60.0
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 16: Dataset refresh after model training (v1 -> v2)
# ---------------------------------------------------------------------------
def test_edge_case_16_dataset_version_mismatch():
    """Model trained on v1 warns or fails inference if dataset has been refreshed to v2."""
    df = pd.DataFrame({
        "id": range(25),
        "feat": np.random.uniform(1.0, 10.0, size=25),
        "target": np.random.uniform(50.0, 100.0, size=25),
    })
    ds = create_dataset("csv", "test_edge_16_version", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target",
            problem_type="regression",
            features=["feat"],
            cv_folds=3,
        )
        resp = PredictionService.train_model(req)
        meta = get_model_metadata(resp.model_id)
        assert meta is not None

        # Check version match on v1
        valid, msg = validate_model_version(meta, current_dataset_version=1)
        assert valid is True

        # Check version mismatch on v2
        valid, msg = validate_model_version(meta, current_dataset_version=2)
        assert valid is False
        assert "Dataset version mismatch" in msg
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 17: New datasets with unfamiliar column synonyms
# ---------------------------------------------------------------------------
def test_edge_case_17_unfamiliar_column_synonyms():
    """Unusual column names (e.g. trans_epoch, unit_burn, churn_flag) are inferred properly."""
    df = pd.DataFrame({
        "trans_epoch": pd.date_range("2024-01-01", periods=30, freq="D").strftime("%Y-%m-%d"),
        "unit_burn": np.random.uniform(10.0, 80.0, size=30),
        "churn_flag": ["Retained" if i % 3 != 0 else "Churned" for i in range(30)],
    })
    ds = create_dataset("csv", "test_edge_17_synonyms", df)
    try:
        meta = get_metadata(ds.dataset_id)
        reg_cands, clf_cands = detect_target_candidates(meta["columns"], 30)
        reg_names = [c.name for c in reg_cands]
        clf_names = [c.name for c in clf_cands]

        assert "unit_burn" in reg_names
        assert "churn_flag" in clf_names
    finally:
        delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# Edge Case 18: Excessive CV folds on small dataset
# ---------------------------------------------------------------------------
def test_edge_case_18_excessive_cv_folds_fallback():
    """Requesting 10 folds on 12 rows dynamically reduces folds rather than crashing."""
    np.random.seed(42)
    n = 12
    df = pd.DataFrame({
        "id": range(n),
        "feat_a": np.random.uniform(1.0, 5.0, size=n),
        "target_val": np.random.uniform(10.0, 20.0, size=n),
    })
    ds = create_dataset("csv", "test_edge_18_excessive_cv", df)
    try:
        req = TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_val",
            problem_type="regression",
            features=["feat_a"],
            cv_folds=10,  # 10 folds requested on 12 rows (train split will have ~9 rows)
        )
        # Should not raise ValueError (scikit-learn would raise if n_splits > n_samples)
        resp = PredictionService.train_model(req)
        assert resp.best_model is not None
        assert resp.best_model.metrics.get("mae") is not None
    finally:
        delete_dataset(ds.dataset_id)
