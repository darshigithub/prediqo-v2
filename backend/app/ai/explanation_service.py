"""AI-Powered Business Explanation Layer Service.

Orchestrates structured, verified, non-causal business explanations for ML Predictions
and Time-Series Forecasts, supporting multi-LLM providers (including local Ollama)
with fingerprint-based caching, numerical integrity validation, and deterministic fallbacks.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import threading
from typing import Any, Optional

from .explanation_models import (
    AIExplanationResponse,
    ForecastExplanationRequest,
    PredictionExplanationRequest,
)
from .explanation_prompts import PROMPT_VERSION
from .llm_client import (
    BaseLLMProvider,
    LLMConfigError,
    LLMServiceError,
    get_llm_provider,
    list_available_providers,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-Memory Thread-Safe Fingerprint Cache
# ---------------------------------------------------------------------------
class ExplanationCache:
    """Thread-safe LRU-capped in-memory cache for generated explanations."""

    def __init__(self, max_size: int = 250):
        self._max_size = max_size
        self._store: dict[str, AIExplanationResponse] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[AIExplanationResponse]:
        with self._lock:
            val = self._store.get(key)
            if val:
                # Return a copy marked with cache_hit = True
                copy_val = val.model_copy()
                copy_val.cache_hit = True
                return copy_val
            return None

    def set(self, key: str, value: AIExplanationResponse) -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                # Evict oldest inserted key
                first_key = next(iter(self._store))
                self._store.pop(first_key, None)
            self._store[key] = value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# Global explanation cache instance
_cache = ExplanationCache(max_size=250)


def generate_evidence_fingerprint(evidence: dict[str, Any]) -> str:
    """Computes a deterministic SHA256 hex digest of the canonical evidence JSON."""
    raw = json.dumps(evidence, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Numerical and Semantic Integrity Validator (Imported & Re-exported)
# ---------------------------------------------------------------------------
from .explanation_validator import (
    FORBIDDEN_GUARANTEE_TERMS,
    validate_explanation_integrity,
)



# ---------------------------------------------------------------------------
# Deterministic Rule-Based Fallback Generators
# ---------------------------------------------------------------------------
def format_val(v: Any, unit: Optional[str] = None) -> str:
    """Formats a numeric or string value with optional unit."""
    if v is None:
        return "unspecified"
    if isinstance(v, (int, float)):
        formatted_num = f"{v:,.2f}" if isinstance(v, float) else f"{v:,}"
        return f"{formatted_num} {unit}".strip() if unit else formatted_num
    return f"{v} {unit}".strip() if unit else str(v)


def generate_deterministic_prediction_explanation(
    evidence: dict[str, Any],
    fingerprint: str,
) -> AIExplanationResponse:
    """Generates an authoritative, factual prediction explanation using rule-based templates."""
    target = evidence.get("target_name", "Target")
    prob_type = evidence.get("problem_type", "regression")
    unit = evidence.get("unit")
    prediction = evidence.get("prediction")
    baseline = evidence.get("baseline_reference_value")
    decomp_space = evidence.get("decomposition_space", "ORIGINAL_TARGET_SPACE")
    contributions = evidence.get("contributions", [])
    metrics = evidence.get("metrics", {})
    model_meta = evidence.get("model_metadata", {})

    pos = [c for c in contributions if (c.get("contribution") or 0) > 0.0001]
    neg = [c for c in contributions if (c.get("contribution") or 0) < -0.0001]
    pos_sorted = sorted(pos, key=lambda x: x.get("contribution", 0), reverse=True)
    neg_sorted = sorted(neg, key=lambda x: x.get("contribution", 0))

    # 1. Summary
    pred_str = format_val(prediction, unit)
    if baseline is not None and prob_type == "regression":
        base_str = format_val(baseline, unit)
        diff = float(prediction) - float(baseline)
        diff_str = f"{'+' if diff >= 0 else ''}{format_val(diff, unit)}"
        summary = (
            f"The model predicts {target} will be {pred_str}, representing a {diff_str} shift "
            f"relative to the historical baseline of {base_str}."
        )
    else:
        probs = evidence.get("probabilities") or {}
        top_prob = probs.get(str(prediction))
        top_prob_str = f" ({top_prob * 100:.1f}% estimated probability)" if top_prob is not None else ""
        summary = (
            f"The model predicts a {prob_type} outcome of {pred_str}{top_prob_str} for target {target}."
        )


    # 2. What the result means
    if prob_type == "classification":
        probs = evidence.get("probabilities") or {}
        prob_parts = [f"{cls}: {p * 100:.1f}%" for cls, p in probs.items()]
        probs_str = f" Probability breakdown: {', '.join(prob_parts)}." if prob_parts else ""
        what_means = (
            f"The record has been classified as '{prediction}'.{probs_str} "
            f"This category reflects the highest scoring likelihood based on historical training patterns."
        )
    else:
        what_means = (
            f"In an operational context, an estimated {target} of {pred_str} provides a point projection "
            f"for planning, budget allocation, and capacity estimation."
        )

    # 3. Supporting evidence
    evidence_bullets = []
    if pos_sorted:
        top_p = pos_sorted[0]
        c_val = top_p.get("contribution", 0)
        c_str = f"+{c_val:.2f}" if decomp_space == "LOG_ODDS_MARGIN" else f"+{format_val(c_val, unit)}"
        raw_val = top_p.get("raw_value")
        val_note = f" (input value: {raw_val})" if raw_val is not None else ""
        evidence_bullets.append(
            f"Positive Driver: Feature '{top_p.get('feature')}' increased prediction by {c_str}{val_note}."
        )
    if neg_sorted:
        top_n = neg_sorted[0]
        c_val = top_n.get("contribution", 0)
        c_str = f"{c_val:.2f}" if "LOG_ODDS" in str(decomp_space).upper() else format_val(c_val, unit)
        raw_val = top_n.get("raw_value")
        val_note = f" (input value: {raw_val})" if raw_val is not None else ""
        evidence_bullets.append(
            f"Negative Driver: Feature '{top_n.get('feature')}' decreased prediction by {c_str}{val_note}."
        )
    if baseline is not None:
        evidence_bullets.append(
            f"Baseline Reference: Model neutral baseline reference point is {format_val(baseline, unit)}."
        )
    if not evidence_bullets:
        evidence_bullets.append("Feature contributions were neutral or not available for this record.")

    # 4. Evaluation quality
    algo = model_meta.get("algorithm", "Supervised ML")
    cv_r2 = metrics.get("r2") or metrics.get("cv_r2")
    cv_mae = metrics.get("mae") or metrics.get("cv_mae")
    cv_rmse = metrics.get("rmse") or metrics.get("cv_rmse")
    cv_f1 = metrics.get("f1") or metrics.get("cv_f1") or metrics.get("f1_macro")
    roc_auc = metrics.get("roc_auc") or metrics.get("cv_roc_auc")
    vs_base = metrics.get("vs_baseline_pct")

    eval_parts = [f"Trained using {algo}."]
    if cv_r2 is not None:
        eval_parts.append(f"Holdout/CV R² is {cv_r2:.2f}." if isinstance(cv_r2, (int, float)) else f"Holdout/CV R² is {cv_r2}.")
    if cv_mae is not None:
        eval_parts.append(f"Holdout/CV MAE is {cv_mae}.")
    if cv_rmse is not None:
        eval_parts.append(f"Holdout/CV RMSE is {cv_rmse}.")
    if cv_f1 is not None:
        eval_parts.append(f"Holdout/CV F1 score is {cv_f1}.")
    if roc_auc is not None:
        eval_parts.append(f"Holdout/CV ROC AUC is {roc_auc}.")
    if vs_base is not None:
        eval_parts.append(f"Performance improves upon the naive baseline by {vs_base}%.")
    evaluation_quality = " ".join(eval_parts)

    # 5. Uncertainty & limitations
    limitations = [
        "Non-Causal Relationship: Feature attributions represent statistical associations across training data, not direct causal control levers.",
    ]
    if "LOG_ODDS" in str(decomp_space).upper():
        limitations.append(
            "Scale Notice: Explanations are computed in log-odds decision margin space, not linear percentage points."
        )
    if prob_type == "classification":
        limitations.append(
            "Calibration Notice: Output probabilities reflect model decision tree votes/scoring scores; they are not strictly calibrated frequencies."
        )

    # 6. Suggested verifications
    verifications = [
        "Verify that current input parameters reflect real operational conditions and have not undergone recent regime shifts.",
        "Cross-reference key driver values with domain specialists before executing large commitments.",
    ]

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return AIExplanationResponse(
        summary=summary,
        what_the_result_means=what_means,
        supporting_evidence=evidence_bullets,
        evaluation_quality=evaluation_quality,
        uncertainty_and_limitations=limitations,
        suggested_verifications=verifications,
        provider="deterministic_fallback",
        model="rules_engine_v1",
        generated_at=now_iso,
        is_fallback=True,
        cache_hit=False,
        evidence_fingerprint=fingerprint,
        raw_evidence=evidence,
    )


def generate_deterministic_forecast_explanation(
    evidence: dict[str, Any],
    fingerprint: str,
) -> AIExplanationResponse:
    """Generates an authoritative, factual forecasting explanation using rule-based templates."""
    metric = evidence.get("metric_column", "Metric")
    freq = evidence.get("frequency", "daily")
    horizon = evidence.get("horizon", 14)
    unit = evidence.get("unit")
    hist = evidence.get("historical_summary", {})
    fc = evidence.get("forecast_summary", {})
    metrics = evidence.get("backtest_metrics", {})
    intervals = evidence.get("intervals", {})

    proj_avg = fc.get("projected_avg") if fc.get("projected_avg") is not None else (fc.get("forecast_mean") if fc.get("forecast_mean") is not None else fc.get("mean"))
    proj_tot = fc.get("projected_cumulative") if fc.get("projected_cumulative") is not None else (fc.get("forecast_total") if fc.get("forecast_total") is not None else fc.get("total"))
    traj = fc.get("trajectory", "stable")
    pct_chg = fc.get("change_pct_vs_historical")

    # 1. Summary
    avg_str = format_val(proj_avg, unit)
    tot_str = format_val(proj_tot, unit)
    chg_note = f" ({'+' if pct_chg and pct_chg > 0 else ''}{pct_chg}% vs recent history)" if pct_chg is not None else ""
    summary = (
        f"Over the next {horizon} {freq} periods, {metric} is projected to follow a {traj} trajectory, "
        f"averaging {avg_str} per period (cumulative {tot_str}){chg_note}."
    )

    # 2. What the result means
    what_means = (
        f"For demand and operational planning, this {traj} trend indicates an expected cumulative requirement "
        f"of {tot_str} across the {horizon}-{freq} horizon."
    )

    # 3. Supporting evidence
    evidence_bullets = [
        f"Trajectory Direction: Model projects a {traj} trend averaging {avg_str} per {freq} period.",
    ]
    hist_mean = hist.get("mean_value") if hist.get("mean_value") is not None else (hist.get("historical_mean") if hist.get("historical_mean") is not None else hist.get("mean"))
    if hist_mean is not None:
        evidence_bullets.append(
            f"Historical Context: Average historical value was {format_val(hist_mean, unit)}."
        )
    mae = metrics.get("mae")
    vs_naive = metrics.get("vs_naive_pct")
    if mae is not None:
        naive_str = f" ({'+' if vs_naive and vs_naive > 0 else ''}{vs_naive}% vs naive baseline)" if vs_naive is not None else ""
        evidence_bullets.append(
            f"Backtest Verification: Rolling-origin backtest holdout MAE was {mae}{naive_str}."
        )

    # 4. Evaluation quality
    algo = metrics.get("best_algorithm", "Time-Series Model")
    wape = metrics.get("wape")
    mape = metrics.get("mape")
    rmse = metrics.get("rmse")
    dir_acc = metrics.get("directional_accuracy")

    eval_parts = [f"Selected algorithm is {algo} based on chronological backtesting."]
    if wape is not None:
        eval_parts.append(f"Holdout WAPE is {wape}%.")
    if mape is not None:
        eval_parts.append(f"Holdout MAPE is {mape}%.")
    if mae is not None:
        eval_parts.append(f"Holdout MAE is {mae}.")
    if rmse is not None:
        eval_parts.append(f"Holdout RMSE is {rmse}.")
    if dir_acc is not None:
        acc_str = f"{dir_acc * 100:.1f}%" if isinstance(dir_acc, (int, float)) and dir_acc <= 1.0 else f"{dir_acc}%"
        eval_parts.append(f"Directional accuracy is {acc_str}.")
    eval_parts.append("Historical backtest accuracy demonstrates model consistency but does not guarantee future precision.")
    eval_text = " ".join(eval_parts)

    # 5. Uncertainty & limitations
    limitations = [
        "Non-Guarantee: Time-series forecasts extrapolate historical patterns. External macroeconomic shocks, supply disruptions, or regime changes are not accounted for.",
    ]
    if intervals:
        l95 = intervals.get("lower_95") if intervals.get("lower_95") is not None else (intervals.get("lower_bound_mean") if intervals.get("lower_bound_mean") is not None else intervals.get("lower"))
        u95 = intervals.get("upper_95") if intervals.get("upper_95") is not None else (intervals.get("upper_bound_mean") if intervals.get("upper_bound_mean") is not None else intervals.get("upper"))
        if l95 is not None and u95 is not None:
            limitations.append(
                f"Uncertainty Bounds: 95% forecast interval spans from {format_val(l95, unit)} to {format_val(u95, unit)}. "
                "These represent statistical distribution intervals, not guaranteed boundaries."
            )
    # Add any explicit limitations passed in evidence
    for lim in evidence.get("limitations", []):
        if lim and lim not in limitations:
            limitations.append(lim)

    # 6. Suggested verifications
    verifications = [
        f"Validate inventory buffer and supplier lead times against the 95% upper bound to prevent shortages.",
        f"Monitor actuals weekly against the projected {traj} trajectory to detect early drift.",
    ]

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return AIExplanationResponse(
        summary=summary,
        what_the_result_means=what_means,
        supporting_evidence=evidence_bullets,
        evaluation_quality=eval_text,
        uncertainty_and_limitations=limitations,
        suggested_verifications=verifications,
        provider="deterministic_fallback",
        model="rules_engine_v1",
        generated_at=now_iso,
        is_fallback=True,
        cache_hit=False,
        evidence_fingerprint=fingerprint,
        raw_evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Main Explanation Service
# ---------------------------------------------------------------------------
class ExplanationService:
    """Enterprise coordinator for AI business explanations with multi-LLM, Ollama, and fallback support."""

    @classmethod
    def get_status(cls) -> dict[str, Any]:
        """Returns provider availability and cache statistics."""
        raw_providers = list_available_providers()
        enriched = []
        for p in raw_providers:
            enriched.append({
                **p,
                "provider_id": p.get("id"),
                "display_name": p.get("name"),
            })
        return {
            "cached_explanations_count": _cache.size(),
            "providers": enriched,
            "prompt_version": PROMPT_VERSION,
        }


def run_shared_explanation_pipeline(
    explanation_type: str,
    compact_evidence: dict[str, Any],
    requested_provider: Optional[str],
    requested_model: Optional[str],
    force_fallback: bool,
    bypass_cache: bool,
    fallback_generator: Any,
    max_retries: int = 2,
) -> AIExplanationResponse:
    """Unified, bounded pipeline shared across Prediction and Forecasting modules."""
    # 1. Compute deterministic fingerprint
    fingerprint = generate_evidence_fingerprint(compact_evidence)

    # 2. Check cache
    provider_name = (
        "deterministic_fallback"
        if (force_fallback or requested_provider == "deterministic_fallback")
        else (requested_provider or "default")
    )
    model_name = (
        "rules_engine_v1"
        if (force_fallback or requested_provider == "deterministic_fallback")
        else (requested_model or "default")
    )
    prefix = "pred" if explanation_type == "prediction" else "fc"
    cache_key = f"{prefix}:{fingerprint}:{provider_name}:{model_name}:{PROMPT_VERSION}"

    if not bypass_cache:
        cached = _cache.get(cache_key)
        if cached:
            return cached

    # 3. Handle explicit fallback requested
    if force_fallback or requested_provider == "deterministic_fallback":
        resp = fallback_generator(compact_evidence, fingerprint)
        _cache.set(cache_key, resp)
        return resp

    # 4. Resolve provider
    try:
        provider: BaseLLMProvider = get_llm_provider(
            provider_name=requested_provider,
            model=requested_model,
        )
    except Exception as e:
        logger.info(
            "Provider '%s' unavailable (%s). Using deterministic rules fallback for %s.",
            requested_provider,
            e,
            explanation_type,
        )
        return fallback_generator(compact_evidence, fingerprint)

    # 5. Execute bounded corrective retry loop (up to max_retries retries after initial attempt)
    total_attempts = 1 + max(0, min(max_retries, 3))
    raw_result: Optional[dict[str, Any]] = None
    last_error: Optional[str] = None
    corrective_feedback: Optional[str] = None

    for attempt in range(1, total_attempts + 1):
        try:
            raw_result = provider.generate_business_explanation(
                explanation_type=explanation_type,
                evidence=compact_evidence,
                max_tokens=650,
                corrective_feedback=corrective_feedback,
            )
            is_valid, reason = validate_explanation_integrity(raw_result, compact_evidence, explanation_type)
            if is_valid:
                break
            else:
                logger.info(
                    "Explanation validation issue on %s (attempt %d/%d): %s",
                    explanation_type,
                    attempt,
                    total_attempts,
                    reason,
                )
                last_error = reason
                corrective_feedback = reason
                raw_result = None
        except (LLMConfigError, LLMServiceError) as e:
            logger.info(
                "LLM provider '%s' unreachable/error on %s (attempt %d/%d): %s",
                provider.display_name,
                explanation_type,
                attempt,
                total_attempts,
                e,
            )
            last_error = str(e)
            break
        except Exception as e:
            logger.info(
                "Unexpected provider error during %s generation (attempt %d/%d): %s",
                explanation_type,
                attempt,
                total_attempts,
                e,
            )
            last_error = str(e)
            break

    # 6. Fallback if validation failed or provider error
    if not raw_result:
        logger.info(
            "Returning verified deterministic fallback explanation for %s (reason: %s)",
            explanation_type,
            last_error,
        )
        fallback = fallback_generator(compact_evidence, fingerprint)
        return fallback

    # 7. Assemble validated response
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    active_model = getattr(provider, "model", None)
    if not isinstance(active_model, str) or not active_model.strip():
        active_model = getattr(provider, "default_model", "default")
    if not isinstance(active_model, str):
        active_model = str(active_model)

    response = AIExplanationResponse(
        summary=str(raw_result.get("summary", "")).strip(),
        what_the_result_means=str(raw_result.get("what_the_result_means", "")).strip(),
        supporting_evidence=[str(x).strip() for x in raw_result.get("supporting_evidence", []) if str(x).strip()],
        evaluation_quality=str(raw_result.get("evaluation_quality", "")).strip(),
        uncertainty_and_limitations=[str(x).strip() for x in raw_result.get("uncertainty_and_limitations", []) if str(x).strip()],
        suggested_verifications=[str(x).strip() for x in raw_result.get("suggested_verifications", []) if str(x).strip()],
        provider=str(getattr(provider, "provider_id", "default")),
        model=active_model,
        generated_at=now_iso,
        is_fallback=False,
        cache_hit=False,
        evidence_fingerprint=fingerprint,
        raw_evidence=compact_evidence,
    )


    # Save to cache
    _cache.set(cache_key, response)
    return response


class ExplanationService:
    """Enterprise coordinator for AI business explanations with multi-LLM, Ollama, and fallback support."""

    @classmethod
    def get_status(cls) -> dict[str, Any]:
        """Returns provider availability and cache statistics."""
        raw_providers = list_available_providers()
        enriched = []
        for p in raw_providers:
            enriched.append({
                **p,
                "provider_id": p.get("id"),
                "display_name": p.get("name"),
            })
        return {
            "cached_explanations_count": _cache.size(),
            "providers": enriched,
            "prompt_version": PROMPT_VERSION,
        }

    @classmethod
    def explain_prediction(
        cls,
        req: PredictionExplanationRequest,
    ) -> AIExplanationResponse:
        """Generates an AI-powered business explanation for a single prediction."""
        compact_evidence: dict[str, Any] = {
            "target_name": req.target_name,
            "problem_type": req.problem_type,
            "unit": req.unit,
            "prediction": req.prediction,
            "probabilities": req.probabilities,
            "baseline_reference_value": req.baseline_reference_value,
            "decomposition_space": req.decomposition_space or "ORIGINAL_TARGET_SPACE",
            "contributions": req.contributions[:10] if req.contributions else [],
            "metrics": req.metrics,
            "model_metadata": req.model_metadata,
            "data_quality": req.data_quality,
        }
        return run_shared_explanation_pipeline(
            explanation_type="prediction",
            compact_evidence=compact_evidence,
            requested_provider=req.provider,
            requested_model=req.model,
            force_fallback=req.force_fallback,
            bypass_cache=req.bypass_cache,
            fallback_generator=generate_deterministic_prediction_explanation,
        )

    @classmethod
    def explain_forecast(
        cls,
        req: ForecastExplanationRequest,
    ) -> AIExplanationResponse:
        """Generates an AI-powered business explanation for a time-series forecast."""
        compact_evidence: dict[str, Any] = {
            "metric_column": req.metric_column,
            "date_column": req.date_column,
            "frequency": req.frequency,
            "horizon": req.horizon,
            "aggregation": req.aggregation,
            "unit": req.unit,
            "historical_summary": req.historical_summary,
            "forecast_summary": req.forecast_summary,
            "backtest_metrics": req.backtest_metrics,
            "intervals": req.intervals,
            "limitations": req.limitations,
        }
        return run_shared_explanation_pipeline(
            explanation_type="forecast",
            compact_evidence=compact_evidence,
            requested_provider=req.provider,
            requested_model=req.model,
            force_fallback=req.force_fallback,
            bypass_cache=req.bypass_cache,
            fallback_generator=generate_deterministic_forecast_explanation,
        )

