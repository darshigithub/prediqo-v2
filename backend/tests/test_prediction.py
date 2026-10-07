"""Tests for the Supervised Machine Learning Prediction Layer."""
import pytest
from pathlib import Path
import sys
import numpy as np
import pandas as pd

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.storage.dataset_store import create_dataset, get_metadata, delete_dataset
from app.prediction.service import PredictionService
from app.prediction.models import TrainRequest, PredictRequest
from app.prediction.target_detector import is_identifier_column, detect_target_candidates, validate_target
from app.prediction.feature_selector import recommend_features, check_leakage_warning
from app.prediction.data_preparation import (
    classify_feature_types,
    build_full_preprocessing_pipeline,
    split_data,
)
from app.prediction.model_store import (
    get_model_metadata,
    validate_model_version,
    load_model,
)
from app.ai.analyst import process_question


@pytest.fixture
def synthetic_ecommerce_df() -> pd.DataFrame:
    """Generates synthetic 100-row e-commerce dataset with regression and classification targets."""
    np.random.seed(42)
    n = 100
    cities = ["Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune"]
    categories = ["Electronics", "Clothing", "Home", "Books"]
    payment_methods = ["UPI", "Credit Card", "Debit Card", "Cash on Delivery"]
    statuses = ["Delivered", "Cancelled", "Pending", "Shipped"]

    data = {
        "Order_ID": [f"ORD_{1000 + i}" for i in range(n)],
        "Customer_ID": [f"CUST_{200 + (i % 25)}" for i in range(n)],
        "Customer_Age": np.random.randint(18, 70, size=n),
        "Gender": np.random.choice(["Male", "Female", "Other"], size=n),
        "City": np.random.choice(cities, size=n),
        "Product_Category": np.random.choice(categories, size=n),
        "Quantity": np.random.randint(1, 10, size=n),
        "Unit_Price": np.random.uniform(100.0, 5000.0, size=n).round(2),
        "Discount_Percent": np.random.choice([0, 5, 10, 15, 20], size=n),
        "Payment_Method": np.random.choice(payment_methods, size=n),
        "Order_Date": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
        "Delivery_Days": np.random.randint(1, 14, size=n),
        "Order_Status": np.random.choice(statuses, size=n),
        "Actual_Delivery_Date": pd.date_range("2024-01-05", periods=n, freq="D").strftime("%Y-%m-%d"),
    }
    return pd.DataFrame(data)


@pytest.fixture
def ecommerce_dataset(synthetic_ecommerce_df):
    """Creates StandardDataset in local test storage and cleans up after test."""
    ds = create_dataset("csv", "test_ecommerce_pred", synthetic_ecommerce_df)
    yield ds
    delete_dataset(ds.dataset_id)


# ---------- 1. Target Detection Tests ----------
def test_target_detection_regression_and_classification(ecommerce_dataset):
    meta = get_metadata(ecommerce_dataset.dataset_id)
    reg_targets, clf_targets = detect_target_candidates(meta["columns"], meta["profile"]["rows"])

    reg_names = [t.name for t in reg_targets]
    clf_names = [t.name for t in clf_targets]

    # Delivery_Days, Quantity, Unit_Price should be regression candidates
    assert "Delivery_Days" in reg_names
    assert "Unit_Price" in reg_names

    # Order_Status, Product_Category, Payment_Method should be classification candidates
    assert "Order_Status" in clf_names
    assert "Payment_Method" in clf_names


def test_id_exclusion_from_targets():
    assert is_identifier_column("Order_ID", "ID", "order_identifier") is True
    assert is_identifier_column("Customer_ID", "ID", "customer_identifier") is True
    assert is_identifier_column("uuid", "ID") is True
    assert is_identifier_column("Delivery_Days", "MEASURE", "duration") is False
    assert is_identifier_column("Order_Status", "CATEGORY", "status") is False


# ---------- 2. Feature Selection & Leakage Tests ----------
def test_feature_selection_and_leakage(ecommerce_dataset):
    meta = get_metadata(ecommerce_dataset.dataset_id)
    rec, excl, warnings = recommend_features(meta["columns"], "Delivery_Days", meta["profile"]["rows"])

    # Target and IDs must be excluded
    assert "Delivery_Days" in excl
    assert "Order_ID" in excl
    assert "Customer_ID" in excl

    # Useful features must be recommended
    assert "Customer_Age" in rec
    assert "City" in rec
    assert "Quantity" in rec
    assert "Unit_Price" in rec

    # Leakage check: Actual_Delivery_Date should trigger warning for Delivery_Days
    leak_warn = check_leakage_warning("Delivery_Days", "Actual_Delivery_Date")
    assert leak_warn is not None
    assert "data leakage" in leak_warn.lower()


# ---------- 3. Preprocessing & Data Preparation Tests ----------
def test_data_preparation_and_preprocessing(synthetic_ecommerce_df):
    date_cols, num_cols, cat_cols = classify_feature_types(
        synthetic_ecommerce_df,
        ["Customer_Age", "City", "Order_Date", "Quantity", "Payment_Method"],
        [{"name": "Order_Date", "semantic_type": "DATE"}],
    )
    assert "Order_Date" in date_cols
    assert "Customer_Age" in num_cols
    assert "Quantity" in num_cols
    assert "City" in cat_cols

    preprocessor, expanded, desc = build_full_preprocessing_pipeline(date_cols, num_cols, cat_cols)
    assert "Order_Date_year" in expanded
    assert "Order_Date_month" in expanded

    # Test fit and transform on sample
    X_sub = synthetic_ecommerce_df[["Customer_Age", "City", "Order_Date", "Quantity", "Payment_Method"]]
    transformed = preprocessor.fit_transform(X_sub)
    assert transformed.shape[0] == len(synthetic_ecommerce_df)
    assert transformed.shape[1] > 5  # Expanded one-hot columns


def test_missing_value_handling_in_pipeline():
    df_missing = pd.DataFrame({
        "age": [25.0, np.nan, 35.0, 40.0],
        "category": ["A", "B", None, "A"],
    })
    pipe, _, _ = build_full_preprocessing_pipeline([], ["age"], ["category"])
    res = pipe.fit_transform(df_missing)
    assert not np.isnan(res).any()


def test_stratified_train_test_split():
    X = pd.DataFrame({"feat": range(40)})
    y = pd.Series(["A"] * 20 + ["B"] * 20)
    X_tr, X_te, y_tr, y_te = split_data(X, y, "classification", test_size=0.25)
    assert len(X_tr) == 30
    assert len(X_te) == 10
    # Stratification preserves 50/50 ratio
    assert (y_te == "A").sum() == 5
    assert (y_te == "B").sum() == 5


# ---------- 4. Feasibility API Service Test ----------
def test_prediction_feasibility(ecommerce_dataset):
    feas = PredictionService.get_feasibility(ecommerce_dataset.dataset_id)
    assert feas.prediction_possible is True
    assert feas.row_count == 100
    assert len(feas.regression_targets) > 0
    assert len(feas.classification_targets) > 0
    assert "Delivery_Days" in feas.recommended_targets or "Order_Status" in feas.recommended_targets


# ---------- 5. End-to-End Regression Training & Evaluation ----------
def test_regression_training_evaluation_and_persistence(ecommerce_dataset):
    req = TrainRequest(
        dataset_id=ecommerce_dataset.dataset_id,
        target_column="Delivery_Days",
        problem_type="regression",
        features=["Customer_Age", "City", "Product_Category", "Quantity", "Unit_Price", "Discount_Percent"],
        test_size=0.2,
        random_state=42,
    )

    resp = PredictionService.train_model(req)
    assert resp.model_id.startswith("model_")
    assert resp.problem_type == "regression"
    assert resp.best_model.primary_metric == "mae"
    assert resp.best_model.metrics["mae"] >= 0.0
    assert "rmse" in resp.best_model.metrics
    assert "r2" in resp.best_model.metrics
    assert len(resp.candidate_models) == 3  # LinearRegression, RandomForestRegressor, GradientBoostingRegressor

    # Verify best candidate is marked
    bests = [c for c in resp.candidate_models if c.is_best]
    assert len(bests) == 1
    assert bests[0].algorithm == resp.best_model.algorithm

    # Verify feature importance
    assert len(resp.feature_importance) > 0
    top_fi = resp.feature_importance[0]
    assert top_fi.feature in req.features
    assert 0.0 <= top_fi.importance <= 1.0

    # Test model reloading from disk
    pipe, meta, schema = load_model(resp.model_id)
    assert meta.target_column == "Delivery_Days"
    assert meta.dataset_id == ecommerce_dataset.dataset_id

    # Test single prediction
    pred_req = PredictRequest(
        model_id=resp.model_id,
        features={
            "Customer_Age": 28,
            "City": "Bangalore",
            "Product_Category": "Electronics",
            "Quantity": 2,
            "Unit_Price": 1500.0,
            "Discount_Percent": 10,
        },
    )
    p_res = PredictionService.predict(pred_req)
    assert isinstance(p_res.prediction, (int, float))
    assert p_res.problem_type == "regression"
    assert p_res.unit == "days"
    assert "Predicted Delivery_Days" in p_res.explanation


# ---------- 6. End-to-End Classification Training & Evaluation ----------
def test_classification_training_evaluation_and_probabilities(ecommerce_dataset):
    req = TrainRequest(
        dataset_id=ecommerce_dataset.dataset_id,
        target_column="Order_Status",
        problem_type="classification",
        features=["Customer_Age", "City", "Product_Category", "Quantity", "Unit_Price"],
        test_size=0.2,
        random_state=42,
    )

    resp = PredictionService.train_model(req)
    assert resp.problem_type == "classification"
    assert resp.best_model.primary_metric == "f1"
    assert "accuracy" in resp.best_model.metrics
    assert "precision" in resp.best_model.metrics
    assert "recall" in resp.best_model.metrics
    assert "f1" in resp.best_model.metrics
    assert len(resp.candidate_models) == 3  # LogisticRegression, RandomForestClassifier, GradientBoostingClassifier

    # Test single classification prediction with probabilities
    pred_req = PredictRequest(
        model_id=resp.model_id,
        features={
            "Customer_Age": 35,
            "City": "Mumbai",
            "Product_Category": "Home",
            "Quantity": 3,
            "Unit_Price": 850.0,
        },
    )
    p_res = PredictionService.predict(pred_req)
    assert isinstance(p_res.prediction, str)
    assert p_res.problem_type == "classification"
    assert p_res.probabilities is not None
    assert len(p_res.probabilities) > 0
    # Sum of probabilities should approximate 1.0
    total_prob = sum(p_res.probabilities.values())
    assert 0.95 <= total_prob <= 1.05


# ---------- 7. Dataset Version Validation Test ----------
def test_dataset_version_safety(ecommerce_dataset):
    req = TrainRequest(
        dataset_id=ecommerce_dataset.dataset_id,
        target_column="Delivery_Days",
        problem_type="regression",
        features=["Customer_Age", "Quantity"],
    )
    resp = PredictionService.train_model(req)
    meta = get_model_metadata(resp.model_id)

    # Validate against same version (v1) -> Success
    valid, msg = validate_model_version(meta, 1)
    assert valid is True

    # Validate against updated version (v2) -> Mismatch rejected
    valid, msg = validate_model_version(meta, 2)
    assert valid is False
    assert "Dataset version mismatch" in msg


# ---------- 8. Target & Input Validation Errors ----------
def test_invalid_target_and_input_rejections(ecommerce_dataset):
    # Non-existent target
    with pytest.raises(ValueError, match="not found in dataset"):
        PredictionService.train_model(TrainRequest(
            dataset_id=ecommerce_dataset.dataset_id,
            target_column="Non_Existent_Column",
        ))

    # Identifier as target
    with pytest.raises(ValueError, match="is an identifier"):
        PredictionService.train_model(TrainRequest(
            dataset_id=ecommerce_dataset.dataset_id,
            target_column="Order_ID",
            problem_type="regression",
            features=["Quantity"],
        ))

    # Feature identical to target
    with pytest.raises(ValueError, match="cannot be identical to target"):
        PredictionService.train_model(TrainRequest(
            dataset_id=ecommerce_dataset.dataset_id,
            target_column="Delivery_Days",
            features=["Delivery_Days", "Quantity"],
        ))


# ---------- 9. AI Routing & Intent Separation Tests ----------
def test_ai_routing_prediction_intent(ecommerce_dataset):
    # Prediction intent
    res = process_question(ecommerce_dataset.dataset_id, "Predict delivery days for customer")
    assert res.get("query_plan", {}).get("intent") == "prediction"
    assert "Delivery_Days" in res.get("query_plan", {}).get("target", "")

    # Ambiguous target clarification
    res_ambig = process_question(ecommerce_dataset.dataset_id, "Predict amount")
    if res_ambig.get("query_plan", {}).get("intent") == "clarification":
        assert "Which one would you like to predict?" in res_ambig.get("insight", "")

    # Forecasting notice
    res_fc = process_question(ecommerce_dataset.dataset_id, "Predict next month's revenue")
    assert res_fc.get("query_plan", {}).get("intent") == "forecasting"
    assert "not supported in Phase 1" in res_fc.get("insight", "")

    # Regular analytics query must NOT trigger prediction
    res_analytics = process_question(ecommerce_dataset.dataset_id, "Show revenue by city")
    assert res_analytics.get("query_plan", {}).get("intent") != "prediction"
    assert "result" in res_analytics


# ---------- 10. REST API Endpoints Integration Test ----------
def test_prediction_rest_api_endpoints(ecommerce_dataset):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Feasibility endpoint
    r_feas = client.get(f"/api/prediction/feasibility/{ecommerce_dataset.dataset_id}")
    assert r_feas.status_code == 200
    feas_json = r_feas.json()
    assert feas_json["prediction_possible"] is True

    # 2. Train endpoint
    r_train = client.post("/api/prediction/train", json={
        "dataset_id": ecommerce_dataset.dataset_id,
        "target_column": "Delivery_Days",
        "problem_type": "regression",
        "features": ["Customer_Age", "Quantity", "Discount_Percent"],
        "test_size": 0.2,
    })
    assert r_train.status_code == 200
    train_json = r_train.json()
    model_id = train_json["model_id"]
    assert model_id.startswith("model_")
    assert train_json["best_model"]["primary_metric"] == "mae"

    # 3. Models list endpoint
    r_models = client.get(f"/api/prediction/models/{ecommerce_dataset.dataset_id}")
    assert r_models.status_code == 200
    models_json = r_models.json()
    assert len(models_json["models"]) >= 1

    # 4. Model details endpoint
    r_detail = client.get(f"/api/prediction/models/{model_id}")
    assert r_detail.status_code == 200
    detail_json = r_detail.json()
    assert detail_json["model_id"] == model_id
    assert detail_json["target_column"] == "Delivery_Days"

    # 5. Predict endpoint
    r_pred = client.post("/api/prediction/predict", json={
        "model_id": model_id,
        "features": {
            "Customer_Age": 30,
            "Quantity": 4,
            "Discount_Percent": 10,
        },
    })
    assert r_pred.status_code == 200
    pred_json = r_pred.json()
    assert pred_json["problem_type"] == "regression"
    assert isinstance(pred_json["prediction"], (int, float))
    assert pred_json["unit"] == "days"

