"""Comprehensive tests for the NLP AI Analyst module and Section 25 Acceptance Tests."""
import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.analyst import process_question
from app.ai.openai_client import OpenAIConfigError, OpenAIClient
from app.ai.query_planner import (
    ChartConfig,
    FilterSpec,
    MetricSpec,
    QueryPlan,
    SortSpec,
    build_query_plan,
)
from app.ai.query_validator import QueryValidationError, validate_query_plan
from app.ai.suggestion_engine import generate_deterministic_suggestions, get_dataset_suggestions
from app.standardization.standardizer import build_standard_dataset
from app.storage.dataset_store import _cache


@pytest.fixture(autouse=True)
def setup_ecommerce_dataset(monkeypatch):
    """Load ecommerce_sales.csv as standard dataset in storage and ensure isolated test env."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "uploads", "ecommerce_sales.csv"
    )
    df = pd.read_csv(csv_path)
    df["Order_Date"] = pd.to_datetime(df["Order_Date"])
    ds = build_standard_dataset("ds_ecommerce_test", "ecommerce_sales", "csv", df)
    _cache["ds_ecommerce_test"] = ds
    return ds


# ------------------ Section 25 Acceptance Tests ------------------

def test_acceptance_test_1_revenue_by_product_category():
    """Test 1: Show revenue by product category."""
    res = process_question("ds_ecommerce_test", "Show revenue by product category", allow_fallback=True)

    plan = res["query_plan"]
    assert "Product_Category" in plan["dimensions"]
    assert any(m["column"] == "Total_Amount" and m["aggregation"] == "SUM" for m in plan["metrics"])

    result = res["result"]
    assert len(result["rows"]) > 0
    # Table rows contain Product_Category and revenue metric
    assert "Product_Category" in result["rows"][0]
    assert any("revenue" in k.lower() or "total" in k.lower() or "amount" in k.lower() for k in result["rows"][0].keys())

    # Bar chart
    assert res["chart"]["type"] == "bar"

    # Insight produced
    assert len(res["insight"]) > 0


def test_acceptance_test_2_top_5_products_by_revenue():
    """Test 2: What are the top 5 products by revenue?"""
    res = process_question("ds_ecommerce_test", "What are the top 5 products by revenue?", allow_fallback=True)

    plan = res["query_plan"]
    assert "Product" in plan["dimensions"]
    assert any(m["column"] == "Total_Amount" and m["aggregation"] == "SUM" for m in plan["metrics"])
    assert plan["limit"] == 5
    assert any(s["direction"] == "DESC" for s in plan["sort"])

    result = res["result"]
    assert len(result["rows"]) <= 5
    # Verify rows are sorted descending by metric
    vals = [list(r.values())[1] for r in result["rows"] if len(r) > 1]
    assert vals == sorted(vals, reverse=True)


def test_acceptance_test_3_monthly_revenue():
    """Test 3: Show monthly revenue."""
    res = process_question("ds_ecommerce_test", "Show monthly revenue", allow_fallback=True)

    plan = res["query_plan"]
    assert "Order_Date" in plan["dimensions"]
    assert plan["time_grain"] == "month"
    assert any(m["column"] == "Total_Amount" and m["aggregation"] == "SUM" for m in plan["metrics"])

    # Line chart recommended for time trend
    assert res["chart"]["type"] == "line"

    result = res["result"]
    assert len(result["rows"]) > 0
    # Rows should have formatted month strings e.g. "May 2025"
    assert isinstance(result["rows"][0]["Order_Date"], str)


def test_acceptance_test_4_highest_average_rating_city():
    """Test 4: Which city has the highest average customer rating?"""
    res = process_question("ds_ecommerce_test", "Which city has the highest average customer rating?", allow_fallback=True)

    plan = res["query_plan"]
    assert "City" in plan["dimensions"]
    assert any(m["column"] == "Customer_Rating" and m["aggregation"] == "AVG" for m in plan["metrics"])
    assert plan["limit"] == 1
    assert any(s["direction"] == "DESC" for s in plan["sort"])

    result = res["result"]
    assert len(result["rows"]) == 1
    top_city = result["rows"][0]["City"]
    assert isinstance(top_city, str)


def test_acceptance_test_5_completed_orders_from_bengaluru():
    """Test 5: Show completed orders from Bengaluru."""
    res = process_question("ds_ecommerce_test", "Show completed orders from Bengaluru.", allow_fallback=True)

    plan = res["query_plan"]
    assert plan["intent"] == "filter"
    filters = {f["column"]: f["value"] for f in plan["filters"]}
    assert filters.get("City") == "Bengaluru"
    assert filters.get("Order_Status") == "Completed"

    result = res["result"]
    assert len(result["rows"]) > 0
    for r in result["rows"]:
        assert r["City"] == "Bengaluru"
        assert r["Order_Status"] == "Completed"


def test_acceptance_test_6_follow_up_conversation_context():
    """Test 6: Show revenue by city. Then: Only top 3."""
    # First turn
    turn1 = process_question("ds_ecommerce_test", "Show revenue by city", allow_fallback=True)
    conv_id = turn1["conversation_id"]
    assert "City" in turn1["query_plan"]["dimensions"]

    # Second turn with follow-up modifier
    turn2 = process_question("ds_ecommerce_test", "Only top 3.", conversation_id=conv_id, allow_fallback=True)
    plan2 = turn2["query_plan"]
    assert "City" in plan2["dimensions"]
    assert plan2["limit"] == 3
    assert len(turn2["result"]["rows"]) == 3
    # Same conversation ID preserved
    assert turn2["conversation_id"] == conv_id


# ------------------ Validator and Error Handling Tests ------------------

def test_validator_rejects_unknown_columns(setup_ecommerce_dataset):
    """Validator must reject non-existent columns with informative error."""
    ds = setup_ecommerce_dataset
    available = [c.name for c in ds.columns]

    bad_plan = QueryPlan(
        table="orders",
        dimensions=["NonExistentColumn"],
        metrics=[MetricSpec(column="Total_Amount", aggregation="SUM")],
    )

    with pytest.raises(QueryValidationError) as exc:
        validate_query_plan(bad_plan, available)
    assert "The dataset does not contain dimension column 'NonExistentColumn'" in str(exc.value)


def test_validator_rejects_unsupported_aggregation(setup_ecommerce_dataset):
    """Validator must reject unsupported aggregations."""
    ds = setup_ecommerce_dataset
    available = [c.name for c in ds.columns]

    bad_plan = QueryPlan(
        table="orders",
        dimensions=["City"],
        metrics=[MetricSpec(column="Total_Amount", aggregation="MEDIAN")],
    )

    with pytest.raises(QueryValidationError) as exc:
        validate_query_plan(bad_plan, available)
    assert "Unsupported aggregation 'MEDIAN'" in str(exc.value)


def test_missing_api_key_raises_error():
    """When allow_fallback=False and no OPENAI_API_KEY, must raise OpenAIConfigError."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
        with pytest.raises(OpenAIConfigError) as exc:
            process_question("ds_ecommerce_test", "Show revenue by city", allow_fallback=False)
        assert "OpenAI API key is not configured" in str(exc.value)


# ------------------ Suggestion Engine Tests ------------------

def test_dataset_specific_suggestions(setup_ecommerce_dataset):
    """Suggestion engine generates 5-8 relevant questions based on actual dataset metadata."""
    ds = setup_ecommerce_dataset
    suggestions = get_dataset_suggestions(ds, use_ai=False)

    assert 5 <= len(suggestions) <= 8
    # Suggestions should relate to actual fields
    s_text = " ".join(suggestions).lower()
    assert "revenue" in s_text or "total" in s_text
    assert "product" in s_text or "category" in s_text


# ------------------ OpenAI Mocking Test ------------------

def test_openai_structured_integration(setup_ecommerce_dataset):
    """Test full flow when OpenAI client returns structured JSON."""
    mock_openai_resp = {
        "intent": "aggregation",
        "table": "orders",
        "dimensions": ["Product_Category"],
        "metrics": [{"column": "Total_Amount", "aggregation": "SUM", "alias": "total_revenue"}],
        "filters": [],
        "sort": [{"column": "total_revenue", "direction": "DESC"}],
        "limit": 10,
        "chart": {"type": "bar", "x": "Product_Category", "y": "total_revenue"},
        "explanation": "Revenue aggregated by category.",
    }

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-mock"}):
        with patch.object(OpenAIClient, "generate_structured_query", return_value=mock_openai_resp):
            with patch.object(OpenAIClient, "generate_insight", return_value="Electronics generated the highest revenue."):
                res = process_question("ds_ecommerce_test", "Show revenue by category", allow_fallback=False)
                assert res["parser_used"] == "openai"
                assert res["chart"]["type"] == "bar"
                assert "Electronics" in res["insight"]
                assert len(res["result"]["rows"]) > 0


# ------------------ API Route HTTP Tests ------------------

def test_api_route_suggestions_endpoint(setup_ecommerce_dataset):
    """Test GET /api/ai/suggestions/{dataset_id}."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/ai/suggestions/ds_ecommerce_test")
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 5


def test_api_route_analyze_missing_key_error():
    """Test POST /api/ai/analyze returns 400 when API key is missing."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
        resp = client.post("/api/ai/analyze", json={
            "dataset_id": "ds_ecommerce_test",
            "question": "Show revenue by city",
            "allow_fallback": False,
        })
        assert resp.status_code == 400
        assert "OpenAI API key is not configured" in resp.json()["detail"]


def test_api_route_analyze_success():
    """Test POST /api/ai/analyze returns expected structure."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post("/api/ai/analyze", json={
        "dataset_id": "ds_ecommerce_test",
        "question": "Show revenue by product category",
        "allow_fallback": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["question"] == "Show revenue by product category"
    assert "query_plan" in data
    assert "result" in data
    assert "chart" in data
    assert "insight" in data
    assert data["chart"]["type"] == "bar"
    assert len(data["result"]["rows"]) > 0


# ------------------ Generic Multi-Provider Tests ------------------

def test_multi_provider_registry():
    """Verify provider instantiation and defaults for all supported providers."""
    from app.ai.llm_client import get_llm_provider, list_available_providers

    groq_p = get_llm_provider("groq")
    assert groq_p.provider_id == "groq"
    assert "groq.com" in groq_p.base_url

    gemini_p = get_llm_provider("gemini")
    assert gemini_p.provider_id == "gemini"
    assert "googleapis.com" in gemini_p.base_url

    anthropic_p = get_llm_provider("anthropic")
    assert anthropic_p.provider_id == "anthropic"

    custom_p = get_llm_provider("custom")
    assert custom_p.provider_id == "custom"

    openai_p = get_llm_provider("openai")
    assert openai_p.provider_id == "openai"

    providers = list_available_providers()
    assert len(providers) >= 5
    provider_ids = [p["id"] for p in providers]
    for expected in ["openai", "groq", "gemini", "anthropic", "custom"]:
        assert expected in provider_ids


def test_api_route_providers_endpoint():
    """Test GET /api/ai/providers returns supported providers."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/ai/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "active_provider" in data
    assert any(p["id"] == "groq" for p in data["providers"])
    assert any(p["id"] == "gemini" for p in data["providers"])
    assert any(p["id"] == "anthropic" for p in data["providers"])
