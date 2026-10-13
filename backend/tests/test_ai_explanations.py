"""Comprehensive test suite for the AI-Powered Business Explanation Layer.
Tests request validation, deterministic fallback generation, integrity validation,
disclaimer / negation recognition, bounded corrective retry with feedback,
cache behavior, provider listing, Ollama integration, and FastAPI endpoints.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.ai.explanation_models import (
    AIExplanationResponse,
    ForecastExplanationRequest,
    PredictionExplanationRequest,
)
from app.ai.explanation_service import (
    ExplanationService,
    _cache,
    generate_deterministic_forecast_explanation,
    generate_deterministic_prediction_explanation,
    generate_evidence_fingerprint,
    run_shared_explanation_pipeline,
)
from app.ai.explanation_validator import (
    validate_explanation_integrity,
    split_into_clauses,
    evaluate_clause_guarantees,
)
from app.ai.llm_client import (
    LLMConfigError,
    LLMServiceError,
    get_llm_provider,
    list_available_providers,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_explanation_cache():
    """Clear explanation cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


# ---------------------------------------------------------------------------
# 1. Deterministic Fallback Generation Tests
# ---------------------------------------------------------------------------

def test_deterministic_prediction_explanation_regression():
    evidence = {
        "target_name": "monthly_sales",
        "problem_type": "regression",
        "unit": "USD",
        "prediction": 45200.5,
        "baseline_reference_value": 38000.0,
        "decomposition_space": "ORIGINAL_TARGET_SPACE",
        "contributions": [
            {"feature": "marketing_spend", "contribution": 5200.5, "raw_value": 12000},
            {"feature": "store_traffic", "contribution": 2000.0, "raw_value": 450},
        ],
        "metrics": {"r2": 0.88, "mae": 1200.0, "rmse": 1500.0},
    }
    fingerprint = generate_evidence_fingerprint(evidence)
    res = generate_deterministic_prediction_explanation(evidence, fingerprint)

    assert isinstance(res, AIExplanationResponse)
    assert res.is_fallback is True
    assert res.provider == "deterministic_fallback"
    assert "45,200.50 USD" in res.summary
    assert "monthly_sales" in res.what_the_result_means
    assert len(res.supporting_evidence) >= 2
    assert "marketing_spend" in res.supporting_evidence[0]
    assert "0.88" in res.evaluation_quality
    assert len(res.uncertainty_and_limitations) >= 1
    assert len(res.suggested_verifications) >= 1
    assert res.evidence_fingerprint == fingerprint


def test_deterministic_prediction_explanation_classification():
    evidence = {
        "target_name": "customer_churn",
        "problem_type": "classification",
        "prediction": "High Risk",
        "probabilities": {"High Risk": 0.78, "Low Risk": 0.22},
        "decomposition_space": "LOG_ODDS_SPACE",
        "contributions": [
            {"feature": "support_tickets", "contribution": 1.45, "raw_value": 5},
            {"feature": "contract_length", "contribution": -0.85, "raw_value": 12},
        ],
        "metrics": {"f1_macro": 0.82, "roc_auc": 0.89},
    }
    fingerprint = generate_evidence_fingerprint(evidence)
    res = generate_deterministic_prediction_explanation(evidence, fingerprint)

    assert res.is_fallback is True
    assert "High Risk" in res.summary
    assert "78.0%" in res.summary
    assert "support_tickets" in res.supporting_evidence[0]
    assert len(res.uncertainty_and_limitations) >= 2
    has_prob_caveat = any("calibrated" in item.lower() or "probability" in item.lower() for item in res.uncertainty_and_limitations)
    assert has_prob_caveat is True


def test_deterministic_forecast_explanation():
    evidence = {
        "metric_column": "order_volume",
        "frequency": "daily",
        "horizon": 14,
        "aggregation": "SUM",
        "unit": "orders",
        "historical_summary": {
            "historical_mean": 150.0,
            "recent_mean": 165.0,
            "recent_trend": "upward",
        },
        "forecast_summary": {
            "forecast_mean": 175.0,
            "forecast_total": 2450.0,
            "trajectory": "increasing",
        },
        "backtest_metrics": {
            "mae": 12.5,
            "rmse": 16.2,
            "mape": 7.4,
            "directional_accuracy": 0.79,
        },
        "intervals": {
            "lower_bound_mean": 155.0,
            "upper_bound_mean": 195.0,
            "nominal_coverage_pct": 95,
        },
        "limitations": ["Limited historical holiday data"],
    }
    fingerprint = generate_evidence_fingerprint(evidence)
    res = generate_deterministic_forecast_explanation(evidence, fingerprint)

    assert res.is_fallback is True
    assert "order_volume" in res.summary
    assert "14 daily" in res.summary
    assert "2,450.00 orders" in res.summary
    assert "MAPE" in res.evaluation_quality
    assert "7.4%" in res.evaluation_quality
    assert any("not guaranteed" in lim.lower() or "non-guarantee" in lim.lower() for lim in res.uncertainty_and_limitations)
    assert any("Limited historical holiday data" in lim for lim in res.uncertainty_and_limitations)


# ---------------------------------------------------------------------------
# 2. Context-Aware Semantic Integrity & Negation Validator Tests
# ---------------------------------------------------------------------------

def test_validate_explanation_integrity_success():
    raw_exp = {
        "summary": "Predicted demand is 500 units based on seasonal factors.",
        "what_the_result_means": "Sales are expected to follow typical summer peaks.",
        "supporting_evidence": ["Temperature positively associates with unit sales."],
        "evaluation_quality": "Historical validation shows MAE of 15 units.",
        "uncertainty_and_limitations": ["Sudden weather anomalies could shift demand."],
        "suggested_verifications": ["Verify local warehouse inventory."],
    }
    is_valid, reason = validate_explanation_integrity(raw_exp, {}, "prediction")
    assert is_valid is True
    assert reason == ""


def test_validate_explanation_integrity_missing_keys():
    raw_exp = {
        "summary": "Demand is high.",
    }
    is_valid, reason = validate_explanation_integrity(raw_exp, {}, "prediction")
    assert is_valid is False
    assert "missing required explanation field" in reason.lower()


@pytest.mark.parametrize("positive_claim", [
    "This forecast guarantees the expected revenue.",
    "The predicted result is certain to happen.",
    "This strategy offers a guaranteed profit.",
    "Marketing spend directly causes customer signups.",
    "This feature is a proven cause of high retention.",
    "This outcome is 100% certain.",
    "Demand will definitely exceed the forecast.",
])
def test_validate_explanation_integrity_rejects_positive_guarantees(positive_claim):
    raw_exp = {
        "summary": positive_claim,
        "what_the_result_means": "Operational expansion projected.",
        "supporting_evidence": ["Attributed to historical observations."],
        "evaluation_quality": "Backtest validation shows stable MAE.",
        "uncertainty_and_limitations": ["External market risks."],
        "suggested_verifications": ["Audit inventory levels."],
    }
    is_valid, reason = validate_explanation_integrity(raw_exp, {}, "prediction")
    assert is_valid is False
    assert "guarantee" in reason.lower() or "claim" in reason.lower()


@pytest.mark.parametrize("negated_disclaimer", [
    "This forecast is not a guaranteed outcome.",
    "Forecast intervals do not imply a guaranteed outcome.",
    "Actual results may differ from this forecast.",
    "This prediction is an estimate based on the available data.",
    "Historical stability does not guarantee future results.",
    "Feature contributions represent statistical associations and do not directly cause changes.",
    "These bounds represent statistical distribution intervals, not guaranteed boundaries.",
    "Results are not 100% certain.",
    "These results are estimates based on the available data. Actual outcomes may differ.",
])
def test_validate_explanation_integrity_accepts_negated_disclaimers(negated_disclaimer):
    raw_exp = {
        "summary": "Projected volume is 1,200 units for the upcoming period.",
        "what_the_result_means": "In an operational context, this projection guides inventory planning.",
        "supporting_evidence": ["Feature 'store_traffic' contributed positively."],
        "evaluation_quality": "Holdout evaluation demonstrates consistent historical accuracy.",
        "uncertainty_and_limitations": [negated_disclaimer],
        "suggested_verifications": ["Verify current operational constraints with warehouse teams."],
    }
    is_valid, reason = validate_explanation_integrity(raw_exp, {}, "forecast")
    assert is_valid is True, f"Failed on disclaimer: '{negated_disclaimer}' -> reason: {reason}"


def test_validate_explanation_integrity_rejects_uncalibrated_probability_claim():
    raw_exp = {
        "summary": "Predicted churn risk is High.",
        "what_the_result_means": "The customer scored high churn likelihood.",
        "supporting_evidence": ["Late tickets increased risk."],
        "evaluation_quality": "Model achieves 0.85 F1 score.",
        "uncertainty_and_limitations": ["Output reflects calibrated true probability with zero error."],
        "suggested_verifications": ["Review account."],
    }
    evidence = {"problem_type": "classification"}
    is_valid, reason = validate_explanation_integrity(raw_exp, evidence, "prediction")
    assert is_valid is False
    assert "uncalibrated" in reason.lower()


# ---------------------------------------------------------------------------
# 3. Evidence Fingerprinting and Caching Tests
# ---------------------------------------------------------------------------

def test_evidence_fingerprint_deterministic():
    ev1 = {"target": "revenue", "value": 100, "metrics": {"mae": 5}}
    ev2 = {"metrics": {"mae": 5}, "value": 100, "target": "revenue"}
    ev3 = {"target": "revenue", "value": 101, "metrics": {"mae": 5}}

    assert generate_evidence_fingerprint(ev1) == generate_evidence_fingerprint(ev2)
    assert generate_evidence_fingerprint(ev1) != generate_evidence_fingerprint(ev3)


def test_explanation_service_caching():
    req = PredictionExplanationRequest(
        target_name="sales",
        prediction=100.0,
        unit="USD",
        force_fallback=True,
    )

    # First call - generated with fallback
    res1 = ExplanationService.explain_prediction(req)
    assert res1.cache_hit is False

    # Second call without bypass_cache - should return cache hit
    res2 = ExplanationService.explain_prediction(req)
    assert res2.cache_hit is True
    assert res2.summary == res1.summary

    # Third call with bypass_cache=True - should regenerate (cache_hit is False)
    req.bypass_cache = True
    res3 = ExplanationService.explain_prediction(req)
    assert res3.cache_hit is False


# ---------------------------------------------------------------------------
# 4. Corrective Retry & Shared Pipeline Reliability Tests
# ---------------------------------------------------------------------------

def test_corrective_retry_succeeds_on_second_attempt():
    """Verifies that an initial validation failure triggers a retry with corrective feedback and succeeds."""
    mock_provider = MagicMock()
    mock_provider.provider_id = "test_provider"
    mock_provider.display_name = "Test Provider"
    mock_provider.default_model = "test-model"

    # Attempt 1: Returns a positive guarantee claim
    bad_attempt = {
        "summary": "This forecast guarantees the expected revenue.",
        "what_the_result_means": "Meaning",
        "supporting_evidence": ["Evidence"],
        "evaluation_quality": "Quality",
        "uncertainty_and_limitations": ["Limit"],
        "suggested_verifications": ["Verify"],
    }

    # Attempt 2: Corrects the claim to a valid estimate
    good_attempt = {
        "summary": "The model projects an estimated revenue increase based on historical trends.",
        "what_the_result_means": "Operational revenue is expected to trend upward.",
        "supporting_evidence": ["Prior promotional lift supports projection."],
        "evaluation_quality": "Holdout MAE is 5.2%.",
        "uncertainty_and_limitations": ["These results are estimates based on available data; actual outcomes may differ."],
        "suggested_verifications": ["Review cash flow assumptions."],
    }

    recorded_feedback = []

    def mock_gen(explanation_type, evidence, max_tokens=650, corrective_feedback=None):
        recorded_feedback.append(corrective_feedback)
        if len(recorded_feedback) == 1:
            return bad_attempt
        return good_attempt

    mock_provider.generate_business_explanation.side_effect = mock_gen

    with patch("app.ai.explanation_service.get_llm_provider", return_value=mock_provider):
        req = ForecastExplanationRequest(
            metric_column="revenue",
            horizon=14,
            unit="USD",
            provider="test_provider",
            model="test-model",
            bypass_cache=True,
        )
        res = ExplanationService.explain_forecast(req)

        # 1. Output succeeded without falling back
        assert res.is_fallback is False
        assert "revenue is expected to trend upward" in res.what_the_result_means

        # 2. Retry was called with corrective feedback
        assert len(recorded_feedback) == 2
        assert recorded_feedback[0] is None
        assert recorded_feedback[1] is not None
        assert "guarantee" in recorded_feedback[1].lower() or "claim" in recorded_feedback[1].lower()


def test_repeated_validation_failure_produces_deterministic_fallback():
    """Verifies that repeated validation failures after max retries return deterministic fallback."""
    mock_provider = MagicMock()
    mock_provider.provider_id = "failing_provider"
    mock_provider.display_name = "Failing Provider"
    mock_provider.default_model = "failing-model"

    # Always returns a forbidden guarantee claim
    mock_provider.generate_business_explanation.return_value = {
        "summary": "This forecast guarantees the expected revenue.",
        "what_the_result_means": "Meaning",
        "supporting_evidence": ["Evidence"],
        "evaluation_quality": "Quality",
        "uncertainty_and_limitations": ["Limit"],
        "suggested_verifications": ["Verify"],
    }

    with patch("app.ai.explanation_service.get_llm_provider", return_value=mock_provider):
        req = ForecastExplanationRequest(
            metric_column="order_count",
            horizon=7,
            unit="orders",
            forecast_summary={"forecast_mean": 100.0, "forecast_total": 700.0},
            provider="failing_provider",
            bypass_cache=True,
        )
        res = ExplanationService.explain_forecast(req)

        # Fallback returned safely
        assert res.is_fallback is True
        assert res.provider == "deterministic_fallback"
        assert "order_count" in res.summary
        assert "700.00 orders" in res.summary


def test_provider_timeout_produces_deterministic_fallback():
    """Verifies that provider timeout raises no unhandled exception and yields fallback."""
    mock_provider = MagicMock()
    mock_provider.provider_id = "slow_provider"
    mock_provider.display_name = "Slow Provider"
    mock_provider.generate_business_explanation.side_effect = LLMServiceError("Slow Provider request timed out after 30s.")

    with patch("app.ai.explanation_service.get_llm_provider", return_value=mock_provider):
        req = PredictionExplanationRequest(
            target_name="delay_minutes",
            prediction=15.0,
            unit="mins",
            provider="slow_provider",
            bypass_cache=True,
        )
        res = ExplanationService.explain_prediction(req)

        assert res.is_fallback is True
        assert res.provider == "deterministic_fallback"
        assert "15.00 mins" in res.summary


def test_provider_auth_failure_produces_deterministic_fallback():
    """Verifies that provider authentication/config error yields deterministic fallback."""
    mock_provider = MagicMock()
    mock_provider.provider_id = "unauth_provider"
    mock_provider.display_name = "Unauth Provider"
    mock_provider.generate_business_explanation.side_effect = LLMConfigError("API key unauthorized")

    with patch("app.ai.explanation_service.get_llm_provider", return_value=mock_provider):
        req = PredictionExplanationRequest(
            target_name="demand",
            prediction=88.0,
            provider="unauth_provider",
            bypass_cache=True,
        )
        res = ExplanationService.explain_prediction(req)

        assert res.is_fallback is True
        assert res.provider == "deterministic_fallback"


# ---------------------------------------------------------------------------
# 5. Provider Listing & Ollama Support Tests
# ---------------------------------------------------------------------------

def test_list_available_providers_includes_ollama():
    raw_providers = list_available_providers()
    raw_ids = [p["id"] for p in raw_providers]
    assert "ollama" in raw_ids
    assert "openai" in raw_ids
    assert "groq" in raw_ids
    assert "anthropic" in raw_ids
    assert "gemini" in raw_ids

    status = ExplanationService.get_status()
    enriched_providers = status["providers"]
    provider_ids = [p["provider_id"] for p in enriched_providers]

    assert "ollama" in provider_ids
    assert "openai" in provider_ids
    assert "groq" in provider_ids

    ollama_info = next(p for p in enriched_providers if p["provider_id"] == "ollama")
    assert ollama_info["display_name"] == "Ollama (Local)"


def test_ollama_provider_resolution():
    with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1"}):
        provider = get_llm_provider("ollama", model="llama3.2")
        assert provider.provider_id == "ollama"
        assert provider.model == "llama3.2"
        assert "11434" in provider.base_url


def test_ollama_unreachable_graceful_fallback():
    req = PredictionExplanationRequest(
        target_name="units_sold",
        prediction=55.0,
        unit="units",
        provider="ollama",
        model="llama3.2",
    )

    with patch("app.ai.llm_client.OpenAICompatibleProvider.generate_business_explanation") as mock_gen:
        mock_gen.side_effect = LLMServiceError(
            "Ollama server is unreachable at http://localhost:11434/v1. Ensure Ollama is running ('ollama serve')."
        )
        res = ExplanationService.explain_prediction(req)

        assert res.is_fallback is True
        assert res.provider == "deterministic_fallback"
        assert "55.00 units" in res.summary


# ---------------------------------------------------------------------------
# 6. FastAPI Endpoints Tests
# ---------------------------------------------------------------------------

def test_status_endpoint():
    resp1 = client.get("/api/ai/explain/status")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "providers" in data1
    assert "cached_explanations_count" in data1

    resp2 = client.get("/api/v1/ai/explain/status")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["prompt_version"] == data1["prompt_version"]


def test_prediction_explanation_endpoint():
    payload = {
        "target_name": "quarterly_revenue",
        "problem_type": "regression",
        "unit": "kUSD",
        "prediction": 820.0,
        "baseline_reference_value": 750.0,
        "contributions": [
            {"feature": "marketing", "contribution": 50.0, "raw_value": 100},
            {"feature": "seasonality", "contribution": 20.0, "raw_value": 4},
        ],
        "metrics": {"r2": 0.91, "mae": 15.0},
        "force_fallback": True,
    }

    resp1 = client.post("/api/ai/explain/prediction", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["summary"] != ""
    assert data1["what_the_result_means"] != ""
    assert len(data1["supporting_evidence"]) >= 1
    assert data1["is_fallback"] is True
    assert data1["evidence_fingerprint"] != ""

    resp2 = client.post("/api/v1/ai/explain/prediction", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["evidence_fingerprint"] == data1["evidence_fingerprint"]


def test_forecast_explanation_endpoint():
    payload = {
        "metric_column": "web_visitors",
        "frequency": "daily",
        "horizon": 7,
        "unit": "visits",
        "forecast_summary": {"forecast_mean": 1200.0, "forecast_total": 8400.0, "trajectory": "stable"},
        "backtest_metrics": {"mae": 50.0, "mape": 4.2},
        "force_fallback": True,
    }

    resp1 = client.post("/api/ai/explain/forecast", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "web_visitors" in data1["summary"]
    assert "8,400.00 visits" in data1["summary"]
    assert data1["is_fallback"] is True

    resp2 = client.post("/api/v1/ai/explain/forecast", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_fallback"] is True
