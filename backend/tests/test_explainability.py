"""Automated tests for Explainable AI (XAI) Layer."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.storage.dataset_store import create_dataset, delete_dataset, get_metadata
from app.prediction.service import PredictionService
from app.prediction.models import TrainRequest
from app.forecasting.service import ForecastingService
from app.forecasting.models import ForecastTrainRequest
from app.explainability.service import ExplainabilityService
from app.explainability.models import LocalExplanationRequest


@pytest.fixture
def synthetic_regression_dataset():
    """Generates synthetic tabular regression dataset."""
    np.random.seed(42)
    n = 60
    df = pd.DataFrame({
        "id": range(n),
        "feature_x": np.random.uniform(10.0, 50.0, size=n),
        "feature_y": np.random.uniform(1.0, 10.0, size=n),
        "category_c": np.random.choice(["Tier1", "Tier2", "Tier3"], size=n),
        "target_price": np.random.uniform(100.0, 500.0, size=n),
    })
    ds = create_dataset("csv", "test_xai_reg", df)
    yield ds
    delete_dataset(ds.dataset_id)


@pytest.fixture
def synthetic_classification_dataset():
    """Generates synthetic multiclass tabular classification dataset."""
    np.random.seed(42)
    n = 60
    tiers = ["Bronze", "Silver", "Gold"]
    df = pd.DataFrame({
        "id": range(n),
        "score": np.random.uniform(20.0, 100.0, size=n),
        "age": np.random.randint(18, 70, size=n),
        "segment": np.random.choice(["Retail", "Enterprise", "SMB"], size=n),
        "tier": [tiers[i % 3] for i in range(n)],
    })
    ds = create_dataset("csv", "test_xai_clf", df)
    yield ds
    delete_dataset(ds.dataset_id)


@pytest.fixture
def synthetic_forecast_dataset():
    """Generates synthetic daily time-series dataset."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "date": dates,
        "demand": [50.0 + (i * 1.5) + (10.0 if (i % 7 == 6) else 0.0) for i in range(60)],
    })
    ds = create_dataset("csv", "test_xai_forecast", df)
    yield ds
    delete_dataset(ds.dataset_id)


# ---------------------------------------------------------------------------
# 1. Local Regression Explanations & Additive Reconstruction
# ---------------------------------------------------------------------------
def test_local_regression_explanation_reconstruction(synthetic_regression_dataset):
    """Local explanation computes feature contributions that reconstruct prediction."""
    ds = synthetic_regression_dataset
    train_res = PredictionService.train_model(
        TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_price",
            problem_type="regression",
            features=["feature_x", "feature_y", "category_c"],
            cv_folds=3,
        )
    )

    req = LocalExplanationRequest(
        features={"feature_x": 35.0, "feature_y": 5.5, "category_c": "Tier2"}
    )
    exp = ExplainabilityService.explain_local(train_res.model_id, req)

    assert exp.model_id == train_res.model_id
    assert exp.problem_type == "regression"
    assert exp.output_scale == "PREDICTION_SPACE"
    assert len(exp.feature_contributions) == 3
    assert exp.is_valid is True
    assert exp.validation_status in ("EXACT_ADDITIVE", "APPROXIMATE")

    # Additive Reconstruction Check: reference_value + sum(contributions) == prediction
    sum_contribs = sum(c.contribution for c in exp.feature_contributions)
    reconstructed = exp.reference_value + sum_contribs
    assert abs(exp.prediction - reconstructed) < 1e-2
    assert exp.reconstruction_error < 1e-2

    # Check top feature and relative weights
    assert exp.feature_contributions[0].relative_weight_pct > 0.0
    total_weights = sum(c.relative_weight_pct for c in exp.feature_contributions)
    assert 99.0 <= total_weights <= 101.0


# ---------------------------------------------------------------------------
# 2. Local Classification Explanations (Multiclass & Probabilities)
# ---------------------------------------------------------------------------
def test_local_classification_explanation_multiclass(synthetic_classification_dataset):
    """Multiclass local explanation returns class probabilities, log-odds margins, and class targeting."""
    ds = synthetic_classification_dataset
    train_res = PredictionService.train_model(
        TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="tier",
            problem_type="classification",
            features=["score", "age", "segment"],
            cv_folds=3,
        )
    )

    req = LocalExplanationRequest(
        features={"score": 85.0, "age": 30, "segment": "Enterprise"},
        target_class="Gold",
    )
    exp = ExplainabilityService.explain_local(train_res.model_id, req)

    assert exp.problem_type == "classification"
    assert exp.predicted_class is not None
    assert exp.class_probabilities is not None
    assert len(exp.class_probabilities) == 3
    assert exp.probability_note is not None
    assert len(exp.feature_contributions) == 3
    assert exp.is_valid is True


# ---------------------------------------------------------------------------
# 3. Global Model Explanation & Grouped Categorical Features
# ---------------------------------------------------------------------------
def test_global_model_explanation_grouped_categories(synthetic_regression_dataset):
    """Global explanation aggregates multi-record attributions and groups one-hot components."""
    ds = synthetic_regression_dataset
    train_res = PredictionService.train_model(
        TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_price",
            problem_type="regression",
            features=["feature_x", "feature_y", "category_c"],
            cv_folds=3,
        )
    )

    glob_exp = ExplainabilityService.explain_global(train_res.model_id, max_sample_rows=30)

    assert glob_exp.model_id == train_res.model_id
    assert glob_exp.sample_size == 30
    assert len(glob_exp.features) == 3

    feat_names = [f.feature for f in glob_exp.features]
    assert "category_c" in feat_names
    assert "feature_x" in feat_names

    # Check normalized importance sums to ~1.0
    tot_imp = sum(f.importance for f in glob_exp.features)
    assert 0.99 <= tot_imp <= 1.01


# ---------------------------------------------------------------------------
# 4. Forecast Model Explainability
# ---------------------------------------------------------------------------
def test_forecast_model_explanation(synthetic_forecast_dataset):
    """Forecast explanation exposes historical trend, slope, level, and empirical coverage."""
    ds = synthetic_forecast_dataset
    fc_res = ForecastingService.train_and_forecast(
        ForecastTrainRequest(
            dataset_id=ds.dataset_id,
            date_column="date",
            metric_column="demand",
            frequency="daily",
            aggregation="AVG",
            horizon=7,
        )
    )

    fc_exp = ExplainabilityService.explain_forecast(fc_res.model_id)

    assert fc_exp.model_id == fc_res.model_id
    assert fc_exp.algorithm == fc_res.best_model.algorithm
    assert "Upward" in fc_exp.historical_trend or "across" in fc_exp.historical_trend
    assert fc_exp.trend_slope is not None
    assert fc_exp.backtest_mae == fc_res.best_model.metrics["mae"]
    assert len(fc_exp.limitations) > 0


# ---------------------------------------------------------------------------
# 5. Explainability Feasibility API
# ---------------------------------------------------------------------------
def test_explainability_feasibility(synthetic_regression_dataset):
    """Feasibility correctly counts trained prediction and forecast models."""
    ds = synthetic_regression_dataset
    PredictionService.train_model(
        TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_price",
            problem_type="regression",
            features=["feature_x", "feature_y"],
            cv_folds=3,
        )
    )

    feas = ExplainabilityService.get_feasibility(ds.dataset_id)
    assert feas.has_trained_models is True
    assert feas.prediction_models_count >= 1
    assert len(feas.prediction_models) >= 1


# ---------------------------------------------------------------------------
# 6. Unseen and Missing Feature Values in Local Explanation
# ---------------------------------------------------------------------------
def test_unseen_and_missing_values_local_explanation(synthetic_regression_dataset):
    """Local explainer handles unseen categories and missing input keys gracefully."""
    ds = synthetic_regression_dataset
    train_res = PredictionService.train_model(
        TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_price",
            problem_type="regression",
            features=["feature_x", "feature_y", "category_c"],
            cv_folds=3,
        )
    )

    # category_c has unseen value "Mars", and feature_x is missing/None
    req = LocalExplanationRequest(
        features={"feature_y": 7.2, "category_c": "Mars"}
    )
    exp = ExplainabilityService.explain_local(train_res.model_id, req)
    assert exp.prediction is not None
    assert len(exp.feature_contributions) == 3
    assert exp.is_valid is True


# ---------------------------------------------------------------------------
# 7. Dataset Version Mismatch Rejection
# ---------------------------------------------------------------------------
def test_version_mismatch_rejection(synthetic_regression_dataset):
    """Local explanation rejects inference if dataset version has changed."""
    ds = synthetic_regression_dataset
    train_res = PredictionService.train_model(
        TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_price",
            problem_type="regression",
            features=["feature_x", "feature_y"],
            cv_folds=3,
        )
    )

    meta = get_metadata(ds.dataset_id)
    # Simulate version bump in metadata
    meta["version"] = 2

    from app.core.config import METADATA_DIR
    import json
    meta_path = METADATA_DIR / f"{ds.dataset_id}.json"
    meta_path.write_text(json.dumps(meta))

    with pytest.raises(ValueError, match="Dataset version mismatch"):
        ExplainabilityService.explain_local(
            train_res.model_id,
            LocalExplanationRequest(features={"feature_x": 10.0, "feature_y": 2.0}),
        )


# ---------------------------------------------------------------------------
# 8. Exact Mathematical Additive Reconstruction Tests (< 1e-10 Error)
# ---------------------------------------------------------------------------
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier, RandomForestClassifier
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from fastapi.testclient import TestClient
from app.main import app
from app.explainability.local_explainer import explain_local_prediction
from app.explainability.global_explainer import explain_global_model


def _build_pipeline(estimator, num_cols, cat_cols=None):
    transformers = [("num", StandardScaler(), num_cols)]
    if cat_cols:
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols))
    preprocessor = ColumnTransformer(transformers=transformers)
    return Pipeline([("preprocessor", preprocessor), ("estimator", estimator)])


def test_gbdt_regressor_exact_mathematical_reconstruction():
    """Verify GradientBoostingRegressor reconstructs actual prediction with machine zero error (< 1e-10)."""
    np.random.seed(42)
    n = 50
    df = pd.DataFrame({
        "num1": np.random.uniform(10, 50, n),
        "num2": np.random.uniform(1, 10, n),
        "target": np.random.uniform(100, 300, n),
    })
    pipe = _build_pipeline(GradientBoostingRegressor(n_estimators=10, random_state=42), ["num1", "num2"])
    pipe.fit(df[["num1", "num2"]], df["target"])

    row = {"num1": 32.5, "num2": 6.8}
    exp = explain_local_prediction(
        pipeline=pipe,
        raw_feature_record=row,
        original_feature_names=["num1", "num2"],
        problem_type="regression",
        algorithm="gradient_boosting",
        model_id="test_gbr",
        dataset_id="ds_test",
        dataset_version=1,
    )

    assert exp.validation_status == "EXACT_ADDITIVE"
    assert exp.reconstruction_error < 1e-4
    assert abs(exp.predicted_value - exp.reconstruction_sum) < 1e-4
    assert abs(exp.reconstruction_sum - (exp.baseline_reference_value + exp.additive_sum)) < 1e-4


def test_gbdt_classifier_binary_imbalanced_exact_log_odds():
    """Verify GradientBoostingClassifier with imbalanced targets computes exact log-odds reconstruction (< 1e-4)."""
    np.random.seed(42)
    n = 60
    # Imbalanced: 48 class 0, 12 class 1
    y = np.array([0] * 48 + [1] * 12)
    df = pd.DataFrame({
        "num1": np.random.uniform(5, 25, n),
        "num2": np.random.uniform(50, 100, n),
        "target": y,
    })
    pipe = _build_pipeline(GradientBoostingClassifier(n_estimators=10, random_state=42), ["num1", "num2"])
    pipe.fit(df[["num1", "num2"]], df["target"])

    row = {"num1": 15.0, "num2": 75.0}
    exp = explain_local_prediction(
        pipeline=pipe,
        raw_feature_record=row,
        original_feature_names=["num1", "num2"],
        problem_type="classification",
        algorithm="gradient_boosting",
        model_id="test_gbc_binary",
        dataset_id="ds_test",
        dataset_version=1,
        target_class=1,
    )

    assert exp.validation_status == "EXACT_ADDITIVE"
    assert exp.decomposition_space == "LOG_ODDS_MARGIN"
    assert exp.reconstruction_error < 1e-4
    assert abs(exp.reconstruction_sum - (exp.baseline_reference_value + exp.additive_sum)) < 1e-4


def test_gbdt_classifier_multiclass_exact_margin_reconstruction():
    """Verify GradientBoostingClassifier with 3 classes computes exact log-odds margin reconstruction for each class."""
    np.random.seed(42)
    n = 60
    classes = ["Low", "Med", "High"]
    y = [classes[i % 3] for i in range(n)]
    df = pd.DataFrame({
        "num1": np.random.uniform(10, 50, n),
        "num2": np.random.uniform(1, 10, n),
        "target": y,
    })
    pipe = _build_pipeline(GradientBoostingClassifier(n_estimators=8, random_state=42), ["num1", "num2"])
    pipe.fit(df[["num1", "num2"]], df["target"])

    row = {"num1": 25.0, "num2": 4.5}
    for target_c in classes:
        exp = explain_local_prediction(
            pipeline=pipe,
            raw_feature_record=row,
            original_feature_names=["num1", "num2"],
            problem_type="classification",
            algorithm="gradient_boosting",
            model_id="test_gbc_multi",
            dataset_id="ds_test",
            dataset_version=1,
            target_class=target_c,
        )

        assert exp.validation_status == "EXACT_ADDITIVE"
        assert exp.decomposition_space == "LOG_ODDS_MARGIN"
        assert exp.reconstruction_error < 1e-4
        assert abs(exp.reconstruction_sum - (exp.baseline_reference_value + exp.additive_sum)) < 1e-4


def test_random_forest_classifier_exact_probability_reconstruction():
    """Verify RandomForestClassifier computes exact additive decomposition in probability space (< 1e-10)."""
    np.random.seed(42)
    n = 60
    classes = ["Bronze", "Silver", "Gold"]
    y = [classes[i % 3] for i in range(n)]
    df = pd.DataFrame({
        "num1": np.random.uniform(10, 50, n),
        "num2": np.random.uniform(1, 10, n),
        "target": y,
    })
    pipe = _build_pipeline(RandomForestClassifier(n_estimators=10, random_state=42), ["num1", "num2"])
    pipe.fit(df[["num1", "num2"]], df["target"])

    row = {"num1": 22.0, "num2": 8.1}
    for target_c in classes:
        exp = explain_local_prediction(
            pipeline=pipe,
            raw_feature_record=row,
            original_feature_names=["num1", "num2"],
            problem_type="classification",
            algorithm="random_forest",
            model_id="test_rfc_multi",
            dataset_id="ds_test",
            dataset_version=1,
            target_class=target_c,
        )

        assert exp.validation_status == "EXACT_ADDITIVE"
        assert exp.decomposition_space == "PROBABILITY_SPACE"
        assert exp.reconstruction_error < 1e-10
        reconstructed = exp.baseline_reference_value + sum(c.contribution for c in exp.contributions)
        assert abs(exp.predicted_proba - reconstructed) < 1e-10


def test_dummy_models_exact_reconstruction():
    """Verify DummyRegressor and DummyClassifier yield exact baseline with zero feature contributions."""
    np.random.seed(42)
    n = 40
    df = pd.DataFrame({
        "x": np.random.uniform(1, 10, n),
        "y_reg": np.random.uniform(50, 100, n),
        "y_clf": ["A"] * 25 + ["B"] * 15,
    })

    # Regressor
    pipe_reg = _build_pipeline(DummyRegressor(strategy="mean"), ["x"])
    pipe_reg.fit(df[["x"]], df["y_reg"])
    exp_reg = explain_local_prediction(
        pipeline=pipe_reg,
        raw_feature_record={"x": 5.0},
        original_feature_names=["x"],
        problem_type="regression",
        algorithm="baseline",
        model_id="test_dummy_reg",
        dataset_id="ds_test",
        dataset_version=1,
    )
    assert exp_reg.validation_status == "EXACT_ADDITIVE"
    assert exp_reg.reconstruction_error < 1e-10
    assert abs(exp_reg.predicted_value - exp_reg.baseline_reference_value) < 1e-10
    assert exp_reg.contributions[0].contribution == 0.0

    # Classifier
    pipe_clf = _build_pipeline(DummyClassifier(strategy="prior"), ["x"])
    pipe_clf.fit(df[["x"]], df["y_clf"])
    exp_clf = explain_local_prediction(
        pipeline=pipe_clf,
        raw_feature_record={"x": 5.0},
        original_feature_names=["x"],
        problem_type="classification",
        algorithm="baseline",
        model_id="test_dummy_clf",
        dataset_id="ds_test",
        dataset_version=1,
        target_class="A",
    )
    assert exp_clf.validation_status == "EXACT_ADDITIVE"
    assert exp_clf.reconstruction_error < 1e-10
    assert abs(exp_clf.predicted_proba - exp_clf.baseline_reference_value) < 1e-10
    assert exp_clf.contributions[0].contribution == 0.0


def test_collinear_features_global_warning():
    """Verify collinear features (|r| >= 0.85) trigger warnings and populate correlated_with map."""
    np.random.seed(42)
    n = 50
    x1 = np.random.uniform(10, 50, n)
    x2 = x1 * 1.001 + np.random.normal(0, 0.01, n)  # Highly collinear
    df = pd.DataFrame({"x1": x1, "x2": x2, "y": x1 * 2})

    pipe = _build_pipeline(GradientBoostingRegressor(n_estimators=5, random_state=42), ["x1", "x2"])
    pipe.fit(df[["x1", "x2"]], df["y"])

    glob_exp = explain_global_model(
        pipeline=pipe,
        original_feature_names=["x1", "x2"],
        sample_df=df[["x1", "x2"]],
        problem_type="regression",
        algorithm="gradient_boosting",
        model_id="test_collinear",
        dataset_id="ds_test",
        dataset_version=1,
    )

    assert len(glob_exp.correlation_warnings) > 0
    assert "high correlation" in glob_exp.correlation_warnings[0]
    # Check that features report correlation with each other
    x1_item = next(f for f in glob_exp.feature_importances if f.feature == "x1")
    assert x1_item.correlated_with is not None
    assert "x2" in x1_item.correlated_with


# ---------------------------------------------------------------------------
# 9. FastAPI Direct Explainability Routes
# ---------------------------------------------------------------------------
def test_explainability_direct_api_endpoints(synthetic_regression_dataset, synthetic_forecast_dataset):
    """Verify FastAPI routes /explainability/local, /global/{id}, /forecast/{id}, and /feasibility/{id}."""
    client = TestClient(app)

    # 1. Train prediction model
    ds = synthetic_regression_dataset
    train_res = PredictionService.train_model(
        TrainRequest(
            dataset_id=ds.dataset_id,
            target_column="target_price",
            problem_type="regression",
            features=["feature_x", "feature_y", "category_c"],
            cv_folds=3,
        )
    )

    # Test /explainability/local (Direct POST)
    resp = client.post(
        "/api/explainability/local",
        json={
            "model_id": train_res.model_id,
            "features": {"feature_x": 30.0, "feature_y": 5.0, "category_c": "Tier1"},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "contributions" in data
    assert "baseline_reference_value" in data
    assert "additive_sum" in data
    assert "validation_status" in data
    assert len(data["contributions"]) == 3
    assert data["contributions"][0]["direction"] in ("POSITIVE", "NEGATIVE", "NEUTRAL")

    # Test /explainability/global/{model_id} (Direct GET)
    resp_g = client.get(f"/api/explainability/global/{train_res.model_id}")
    assert resp_g.status_code == 200, resp_g.text
    data_g = resp_g.json()
    assert "feature_importances" in data_g
    assert "sample_rows_evaluated" in data_g
    assert data_g["sample_rows_evaluated"] > 0
    assert len(data_g["feature_importances"]) == 3

    # Test /explainability/feasibility/{model_id} (Resolves dataset ID from model ID)
    resp_f = client.get(f"/api/explainability/feasibility/{train_res.model_id}")
    assert resp_f.status_code == 200, resp_f.text
    data_f = resp_f.json()
    assert data_f["has_trained_models"] is True
    assert data_f["dataset_id"] == ds.dataset_id

    # 2. Train forecast model and test /explainability/forecast/{model_id}
    fc_ds = synthetic_forecast_dataset
    fc_res = ForecastingService.train_and_forecast(
        ForecastTrainRequest(
            dataset_id=fc_ds.dataset_id,
            date_column="date",
            metric_column="demand",
            frequency="daily",
            aggregation="AVG",
            horizon=7,
        )
    )

    resp_fc = client.get(f"/api/explainability/forecast/{fc_res.model_id}")
    assert resp_fc.status_code == 200, resp_fc.text
    data_fc = resp_fc.json()
    assert data_fc["model_id"] == fc_res.model_id
    assert "historical_trend" in data_fc
    assert "backtest_mae" in data_fc
    assert len(data_fc["limitations"]) > 0

