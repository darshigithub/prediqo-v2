"""Evidence collector for the Decision Layer.
Aggregates facts from prediction models, forecasts, data quality, and user operational inputs
WITHOUT retraining models or running redundant ML training.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from .models import (
    EvidenceItem,
    EvidenceSourceType,
    EvaluationRequest,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_evidence(
    req: EvaluationRequest,
) -> Tuple[Dict[str, Any], Dict[str, EvidenceItem], List[str]]:
    """Aggregates all relevant facts into a unified lookup dictionary and typed evidence items.

    Returns:
        (facts_dict, metadata_dict, missing_evidence_notes)
    """
    facts: Dict[str, Any] = {}
    metadata: Dict[str, EvidenceItem] = {}
    missing_notes: List[str] = []
    ts = _now()

    # 1. Ingest User Operational Facts
    if req.operational_facts:
        for k, v in req.operational_facts.items():
            if v is not None:
                facts[k] = v
                # Check if user provided unit metadata (e.g., facts with '_unit' suffix)
                unit_val = req.operational_facts.get(f"{k}_unit")
                item = EvidenceItem(
                    field_name=k,
                    source_type=EvidenceSourceType.OPERATIONAL_FACT,
                    value=v,
                    unit=str(unit_val) if unit_val else None,
                    source_id="user_input",
                    source_label="User Provided Operational Fact",
                    timestamp=ts,
                )
                metadata[k] = item

    # 2. Ingest Dataset Quality Evidence
    if req.dataset_id:
        try:
            from ..storage.dataset_store import get_metadata
            meta = get_metadata(req.dataset_id)
            if meta:
                dq = meta.get("data_quality", {})
                comp_pct = dq.get("complete_rows_pct", 100.0)
                facts["data_completeness_pct"] = float(comp_pct)
                metadata["data_completeness_pct"] = EvidenceItem(
                    field_name="data_completeness_pct",
                    source_type=EvidenceSourceType.DATA_QUALITY,
                    value=float(comp_pct),
                    unit="%",
                    source_id=req.dataset_id,
                    source_label=f"Dataset {req.dataset_id} Quality",
                    timestamp=ts,
                )

                tot_rows = meta.get("row_count", 0)
                facts["dataset_total_rows"] = tot_rows
                metadata["dataset_total_rows"] = EvidenceItem(
                    field_name="dataset_total_rows",
                    source_type=EvidenceSourceType.DATA_QUALITY,
                    value=tot_rows,
                    unit="rows",
                    source_id=req.dataset_id,
                    source_label="Dataset Row Count",
                    timestamp=ts,
                )

                null_cols = dq.get("columns_with_nulls", 0)
                facts["columns_with_nulls"] = null_cols
                metadata["columns_with_nulls"] = EvidenceItem(
                    field_name="columns_with_nulls",
                    source_type=EvidenceSourceType.DATA_QUALITY,
                    value=null_cols,
                    unit="columns",
                    source_id=req.dataset_id,
                    source_label="Columns with Nulls",
                    timestamp=ts,
                )
            else:
                missing_notes.append(f"Dataset '{req.dataset_id}' metadata could not be loaded.")
        except Exception as e:
            logger.warning("Error collecting dataset evidence: %s", e)
            missing_notes.append(f"Failed to load dataset '{req.dataset_id}' quality info: {e}")

    # 3. Ingest Prediction Model Evidence & Live Prediction
    if req.prediction_model_id:
        try:
            from ..prediction.service import PredictionService
            from ..prediction.models import PredictRequest

            model_data = PredictionService.get_model(req.prediction_model_id)
            if model_data:
                target_col = model_data.get("target_column")
                unit_val = model_data.get("unit")
                metrics = model_data.get("metrics", {})

                # Extract model metrics
                for m_key, m_val in metrics.items():
                    if m_val is not None:
                        field_k = f"model_{m_key}"
                        try:
                            facts[field_k] = float(m_val)
                        except (ValueError, TypeError):
                            facts[field_k] = m_val

                        metadata[field_k] = EvidenceItem(
                            field_name=field_k,
                            source_type=EvidenceSourceType.MODEL_METRIC,
                            value=m_val,
                            unit=unit_val if m_key in ("mae", "rmse") else None,
                            source_id=req.prediction_model_id,
                            source_label=f"Trained Model {model_data.get('algorithm', '')} Metric",
                            timestamp=ts,
                        )

                # If prediction inputs are supplied, run single prediction using saved model
                if req.prediction_inputs:
                    pred_res = PredictionService.predict(
                        PredictRequest(
                            model_id=req.prediction_model_id,
                            features=req.prediction_inputs,
                        )
                    )
                    pred_val = pred_res.prediction
                    facts["predicted_value"] = pred_val
                    facts["prediction"] = pred_val
                    metadata["predicted_value"] = EvidenceItem(
                        field_name="predicted_value",
                        source_type=EvidenceSourceType.PREDICTION,
                        value=pred_val,
                        unit=pred_res.unit or unit_val,
                        source_id=req.prediction_model_id,
                        source_label=f"Predicted {target_col}",
                        timestamp=ts,
                    )
                    metadata["prediction"] = metadata["predicted_value"]

                    # If classification probabilities exist
                    if pred_res.probabilities:
                        for cls_name, prob_val in pred_res.probabilities.items():
                            cls_key = f"prob_{cls_name.lower().replace(' ', '_')}"
                            facts[cls_key] = prob_val
                            metadata[cls_key] = EvidenceItem(
                                field_name=cls_key,
                                source_type=EvidenceSourceType.PREDICTION,
                                value=prob_val,
                                unit="%",
                                source_id=req.prediction_model_id,
                                source_label=f"Probability for class {cls_name}",
                                timestamp=ts,
                            )
                        # Top class probability
                        max_prob = max(pred_res.probabilities.values())
                        facts["top_class_probability"] = max_prob
                        metadata["top_class_probability"] = EvidenceItem(
                            field_name="top_class_probability",
                            source_type=EvidenceSourceType.PREDICTION,
                            value=max_prob,
                            unit="%",
                            source_id=req.prediction_model_id,
                            source_label="Winning Class Probability",
                            timestamp=ts,
                        )
            else:
                missing_notes.append(f"Model '{req.prediction_model_id}' details not found on disk.")
        except Exception as e:
            logger.warning("Error collecting prediction model evidence: %s", e)
            missing_notes.append(f"Failed to load prediction model '{req.prediction_model_id}': {e}")

    # 4. Ingest Forecast Evidence
    if req.forecast_model_id:
        try:
            from ..forecasting.service import ForecastingService
            fc_data = ForecastingService.get_model(req.forecast_model_id)
            if fc_data:
                pts = fc_data.get("points", [])
                metrics = fc_data.get("metrics", {})
                unit_val = fc_data.get("unit")
                metric_name = fc_data.get("metric_column", "forecast")

                # Extract forecast metrics
                for m_key, m_val in metrics.items():
                    if m_val is not None:
                        field_k = f"forecast_{m_key}"
                        try:
                            facts[field_k] = float(m_val)
                        except (ValueError, TypeError):
                            facts[field_k] = m_val

                        metadata[field_k] = EvidenceItem(
                            field_name=field_k,
                            source_type=EvidenceSourceType.MODEL_METRIC,
                            value=m_val,
                            unit=unit_val if m_key in ("mae", "rmse") else ("%" if m_key in ("wape", "mape") else None),
                            source_id=req.forecast_model_id,
                            source_label=f"Forecast Backtest Metric ({m_key.upper()})",
                            timestamp=ts,
                        )

                # Extract horizon aggregate projections
                if pts:
                    values = [float(p.get("forecast", 0)) for p in pts if p.get("forecast") is not None]
                    if values:
                        fc_total = sum(values)
                        fc_avg = fc_total / len(values)
                        fc_max = max(values)
                        fc_min = min(values)

                        facts["forecast_total"] = fc_total
                        metadata["forecast_total"] = EvidenceItem(
                            field_name="forecast_total",
                            source_type=EvidenceSourceType.FORECAST,
                            value=fc_total,
                            unit=unit_val,
                            source_id=req.forecast_model_id,
                            source_label=f"Projected Total {metric_name} ({len(values)} periods)",
                            timestamp=ts,
                        )

                        facts["forecast_average"] = fc_avg
                        metadata["forecast_average"] = EvidenceItem(
                            field_name="forecast_average",
                            source_type=EvidenceSourceType.FORECAST,
                            value=fc_avg,
                            unit=unit_val,
                            source_id=req.forecast_model_id,
                            source_label=f"Projected Average {metric_name} per period",
                            timestamp=ts,
                        )

                        facts["forecast_peak"] = fc_max
                        metadata["forecast_peak"] = EvidenceItem(
                            field_name="forecast_peak",
                            source_type=EvidenceSourceType.FORECAST,
                            value=fc_max,
                            unit=unit_val,
                            source_id=req.forecast_model_id,
                            source_label=f"Projected Peak {metric_name}",
                            timestamp=ts,
                        )

                        # Also populate standard alias "predicted_demand" if not already set
                        if "predicted_demand" not in facts:
                            facts["predicted_demand"] = fc_total
                            metadata["predicted_demand"] = EvidenceItem(
                                field_name="predicted_demand",
                                source_type=EvidenceSourceType.FORECAST,
                                value=fc_total,
                                unit=unit_val,
                                source_id=req.forecast_model_id,
                                source_label=f"Predicted Demand from Forecast Horizon Total",
                                timestamp=ts,
                            )
            else:
                missing_notes.append(f"Forecast model '{req.forecast_model_id}' could not be loaded.")
        except Exception as e:
            logger.warning("Error collecting forecast evidence: %s", e)
            missing_notes.append(f"Failed to load forecast model '{req.forecast_model_id}': {e}")

    return facts, metadata, missing_notes
