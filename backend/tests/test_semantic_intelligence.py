"""Comprehensive tests for Phase 2: Prediqo Semantic Intelligence."""
import os
import sys
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.ai.analyst import process_question
from app.ai.query_planner import MetricSpec, QueryPlan, SortSpec
from app.ai.query_validator import QueryValidationError, correct_identifier_aggregation, validate_query_plan
from app.ai.suggestion_engine import generate_deterministic_suggestions, get_dataset_suggestions
from app.standardization.semantics import (
    discover_derived_metrics,
    get_allowed_aggregations,
    get_display_name,
    get_semantic_model,
    infer_business_role,
)
from app.standardization.standardizer import build_standard_dataset
from app.storage.dataset_store import _cache


@pytest.fixture(autouse=True)
def setup_ecommerce_dataset(monkeypatch):
    """Load ecommerce_sales.csv and build StandardDataset with semantic intelligence."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)

    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "uploads", "ecommerce_sales.csv"
    )
    df = pd.read_csv(csv_path)
    df["Order_Date"] = pd.to_datetime(df["Order_Date"])
    ds = build_standard_dataset("ds_ecommerce_phase2", "ecommerce_sales", "csv", df)
    _cache["ds_ecommerce_phase2"] = ds
    return ds


# =====================================================================
# 1. Section 18 Acceptance Tests (Tests 1 to 10)
# =====================================================================

def test_phase2_acceptance_test_1_total_revenue():
    """Test 1: 'What is the total revenue?' -> SUM(total_amount), not COUNT."""
    res = process_question("ds_ecommerce_phase2", "What is the total revenue?", allow_fallback=True)
    plan = res["query_plan"]
    assert any(m["column"] == "Total_Amount" and m["aggregation"] == "SUM" for m in plan["metrics"])
    assert not any(m["column"] == "Total_Amount" and m["aggregation"] == "COUNT" for m in plan["metrics"])
    assert res["chart"]["type"] == "kpi"
    assert len(res["result"]["rows"]) == 1


def test_phase2_acceptance_test_2_how_many_orders():
    """Test 2: 'How many orders are there?' -> COUNT(order_id)."""
    res = process_question("ds_ecommerce_phase2", "How many orders are there?", allow_fallback=True)
    plan = res["query_plan"]
    assert any("order" in m["column"].lower() and m["aggregation"] == "COUNT" for m in plan["metrics"])
    assert res["chart"]["type"] == "kpi"
    assert len(res["result"]["rows"]) == 1


def test_phase2_acceptance_test_3_which_city_most_orders():
    """Test 3: 'Which city has the most orders?' -> GROUP BY city, COUNT(order_id), ORDER BY count DESC, LIMIT 1."""
    res = process_question("ds_ecommerce_phase2", "Which city has the most orders?", allow_fallback=True)
    plan = res["query_plan"]
    assert "City" in plan["dimensions"]
    assert any("order" in m["column"].lower() and m["aggregation"] == "COUNT" for m in plan["metrics"])
    assert plan["limit"] == 1
    assert any(s["direction"] == "DESC" for s in plan["sort"])
    assert len(res["result"]["rows"]) == 1


def test_phase2_acceptance_test_4_orders_change_over_time():
    """Test 4: 'How do orders change over time?' -> GROUP BY order_date, COUNT(order_id) with time grain."""
    res = process_question("ds_ecommerce_phase2", "How do orders change over time?", allow_fallback=True)
    plan = res["query_plan"]
    assert "Order_Date" in plan["dimensions"]
    assert any("order" in m["column"].lower() and m["aggregation"] == "COUNT" for m in plan["metrics"])
    assert plan["time_grain"] in ("month", "day", "year")
    assert res["chart"]["type"] == "line"


def test_phase2_acceptance_test_5_average_delivery_time():
    """Test 5: 'What is the average delivery time?' -> AVG(delivery_days)."""
    res = process_question("ds_ecommerce_phase2", "What is the average delivery time?", allow_fallback=True)
    plan = res["query_plan"]
    assert any(m["column"] == "Delivery_Days" and m["aggregation"] == "AVG" for m in plan["metrics"])
    assert res["chart"]["type"] == "kpi"


def test_phase2_acceptance_test_6_which_city_highest_revenue():
    """Test 6: 'Which city has the highest revenue?' -> GROUP BY city, SUM(total_amount), ORDER BY revenue DESC, LIMIT 1."""
    res = process_question("ds_ecommerce_phase2", "Which city has the highest revenue?", allow_fallback=True)
    plan = res["query_plan"]
    assert "City" in plan["dimensions"]
    assert any(m["column"] == "Total_Amount" and m["aggregation"] == "SUM" for m in plan["metrics"])
    assert plan["limit"] == 1
    assert any(s["direction"] == "DESC" for s in plan["sort"])


def test_phase2_acceptance_test_7_revenue_by_product_category():
    """Test 7: 'Show revenue by product category.' -> GROUP BY product_category, SUM(total_amount)."""
    res = process_question("ds_ecommerce_phase2", "Show revenue by product category", allow_fallback=True)
    plan = res["query_plan"]
    assert "Product_Category" in plan["dimensions"]
    assert any(m["column"] == "Total_Amount" and m["aggregation"] == "SUM" for m in plan["metrics"])
    assert res["chart"]["type"] == "bar"


def test_phase2_acceptance_test_8_total_order_id_interpreted_as_count():
    """Test 8: 'What is the total order ID?' -> COUNT(order_id) and explanation that order_id is an identifier."""
    res = process_question("ds_ecommerce_phase2", "What is the total order ID?", allow_fallback=True)
    plan = res["query_plan"]
    # Must NOT sum order_id
    assert not any(m["column"] == "Order_ID" and m["aggregation"] == "SUM" for m in plan["metrics"])
    # Must count order_id
    assert any("order" in m["column"].lower() and m["aggregation"] == "COUNT" for m in plan["metrics"])
    # Explanation must clarify that order_id is an identifier
    assert "identifier" in plan.get("explanation", "").lower()


def test_phase2_acceptance_test_9_average_order_id_rejected():
    """Test 9: 'Show the average order ID.' -> Do not execute AVG(order_id); raises informative error or clarifies."""
    with pytest.raises((ValueError, QueryValidationError)) as exc:
        process_question("ds_ecommerce_phase2", "Show the average order ID", allow_fallback=True)
    err = str(exc.value).lower()
    assert "identifier" in err or "cannot be average" in err or "cannot be averaged" in err


def test_phase2_acceptance_test_10_monthly_revenue():
    """Test 10: 'Show monthly revenue.' -> order_date, time_grain = month, SUM(total_amount)."""
    res = process_question("ds_ecommerce_phase2", "Show monthly revenue", allow_fallback=True)
    plan = res["query_plan"]
    assert "Order_Date" in plan["dimensions"]
    assert plan["time_grain"] == "month"
    assert any(m["column"] == "Total_Amount" and m["aggregation"] == "SUM" for m in plan["metrics"])
    assert res["chart"]["type"] == "line"


# =====================================================================
# 2. Business Role Inference Tests
# =====================================================================

def test_business_role_inference(setup_ecommerce_dataset):
    """Verify deterministic business role inference across diverse semantic columns."""
    ds = setup_ecommerce_dataset
    col_roles = {c.name: getattr(c, "business_role", "") for c in ds.columns}

    assert col_roles.get("Order_ID") == "order_identifier"
    assert col_roles.get("Customer_ID") == "customer_identifier"
    assert col_roles.get("Total_Amount") == "revenue"
    assert col_roles.get("Delivery_Days") == "duration"
    assert col_roles.get("Customer_Rating") == "rating"
    assert col_roles.get("City") == "geography"
    assert col_roles.get("Product_Category") == "category"


def test_business_role_unknown_fallback():
    """If confidence is low, role must be 'unknown' or generic, never fabricated."""
    role = infer_business_role("random_custom_header_xyz", dtype="object", semantic_type="DIMENSION")
    assert role in ("dimension", "unknown")


# =====================================================================
# 3. Aggregation Policy Tests
# =====================================================================

def test_aggregation_policy_for_identifiers():
    """IDs must allow COUNT and DISTINCT_COUNT, but forbid SUM, AVG, MIN, MAX."""
    aggs = get_allowed_aggregations(semantic_type="ID", business_role="order_identifier")
    assert "COUNT" in aggs
    assert "DISTINCT_COUNT" in aggs
    assert "SUM" not in aggs
    assert "AVG" not in aggs


def test_aggregation_policy_for_ratings():
    """Ratings must allow AVG, MIN, MAX, but forbid SUM."""
    aggs = get_allowed_aggregations(semantic_type="MEASURE", business_role="rating")
    assert "AVG" in aggs
    assert "MIN" in aggs
    assert "MAX" in aggs
    assert "SUM" not in aggs


def test_aggregation_policy_for_revenue():
    """Revenue measures must support SUM, AVG, MIN, MAX."""
    aggs = get_allowed_aggregations(semantic_type="MEASURE", business_role="revenue")
    assert "SUM" in aggs
    assert "AVG" in aggs


# =====================================================================
# 4. Metric Discovery Tests
# =====================================================================

def test_intelligent_metric_discovery(setup_ecommerce_dataset):
    """Verify analytical metrics are derived directly from dataset columns."""
    ds = setup_ecommerce_dataset
    derived = discover_derived_metrics(ds.columns)

    names = [d["name"] for d in derived]
    assert "total_orders" in names
    assert "total_revenue" in names
    assert "average_order_value" in names
    assert "avg_customer_rating" in names
    assert "avg_delivery_time" in names

    # All metrics reference columns that exist in the dataset
    col_names = {c.name for c in ds.columns}
    for d in derived:
        assert d["column"] in col_names


# =====================================================================
# 5. Suggestion Quality & Bad Suggestion Elimination Tests
# =====================================================================

def test_suggestions_eliminate_bad_questions(setup_ecommerce_dataset):
    """Suggestions must NEVER include 'total order id', 'average order id', or 'monthly order id'."""
    ds = setup_ecommerce_dataset
    suggestions = generate_deterministic_suggestions(ds)

    assert 6 <= len(suggestions) <= 10

    for s in suggestions:
        s_lower = s.lower()
        assert "total order id" not in s_lower
        assert "average order id" not in s_lower
        assert "monthly order id" not in s_lower
        assert "order id by" not in s_lower

    s_text = " ".join(suggestions).lower()
    assert "how many orders are there?" in s_text
    assert "what is the total revenue?" in s_text


# =====================================================================
# 6. Semantic Query Validation & Auto-Correction Tests
# =====================================================================

def test_validator_rejects_sum_of_identifier(setup_ecommerce_dataset):
    """Validator must reject SUM(Order_ID) with explicit reason."""
    ds = setup_ecommerce_dataset
    available = [c.name for c in ds.columns]

    bad_plan = QueryPlan(
        table="orders",
        dimensions=["City"],
        metrics=[MetricSpec(column="Order_ID", aggregation="SUM")],
    )

    with pytest.raises(QueryValidationError) as exc:
        validate_query_plan(bad_plan, available, columns_meta=ds.columns)
    assert "is an identifier and cannot be summed" in str(exc.value)


def test_validator_auto_corrects_identifier_aggregation(setup_ecommerce_dataset):
    """correct_identifier_aggregation must fix SUM(order_id) to COUNT(order_id)."""
    ds = setup_ecommerce_dataset
    bad_plan = QueryPlan(
        table="orders",
        dimensions=[],
        metrics=[MetricSpec(column="Order_ID", aggregation="SUM")],
    )

    corrected, was_corrected = correct_identifier_aggregation(bad_plan, ds.columns)
    assert was_corrected is True
    assert corrected.metrics[0].aggregation == "COUNT"
    assert "identifier" in corrected.explanation.lower()


# =====================================================================
# 7. Semantic Model API Endpoint Tests
# =====================================================================

def test_api_route_semantic_model_endpoint(setup_ecommerce_dataset):
    """Test GET /api/datasets/{dataset_id}/semantic-model."""
    client = TestClient(app)
    resp = client.get("/api/datasets/ds_ecommerce_phase2/semantic-model")
    assert resp.status_code == 200
    data = resp.json()

    assert data["dataset_id"] == "ds_ecommerce_phase2"
    assert len(data["columns"]) > 0
    assert len(data["derived_metrics"]) >= 4
    assert "dimensions" in data
    assert "measures" in data
    assert "identifiers" in data

    # Verify column meta in response contains business_role
    order_col = next(c for c in data["columns"] if c["name"] == "Order_ID")
    assert order_col["business_role"] == "order_identifier"
    assert "COUNT" in order_col["allowed_aggregations"]
