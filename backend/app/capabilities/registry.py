"""Centralized Capability Assessment Registry for Prediction and Forecasting."""
from __future__ import annotations

import logging
from typing import Any, Optional
import duckdb
import pandas as pd

from ..forecasting.service import ForecastingService
from ..prediction.service import PredictionService
from ..storage.dataset_store import get_metadata, get_parquet_path
from .models import (
    CapabilityAssessmentResponse,
    CapabilityForecastingSummary,
    CapabilityPredictionSummary,
    GranularityReport,
)

logger = logging.getLogger(__name__)


def detect_schema_mappings(columns: list[dict]) -> tuple[dict[str, str], dict[str, float]]:
    """Detects canonical concept mappings and confidence scores from column metadata."""
    mappings: dict[str, str] = {}
    confidences: dict[str, float] = {}

    for c in columns:
        name = c.get("name", "")
        n_low = name.lower()
        role = str(c.get("business_role", "")).lower()
        sem = str(c.get("semantic_type", "")).upper()

        # Date mapping
        if "date" not in mappings:
            if role == "transaction_date":
                mappings["date"] = name
                confidences["date"] = 0.95
            elif sem == "DATE" or "date" in n_low or "time" in n_low or n_low in ("purchased_on", "created_at"):
                mappings["date"] = name
                confidences["date"] = 0.85

        # Revenue / monetary mapping
        if "revenue" not in mappings:
            if role == "revenue":
                mappings["revenue"] = name
                confidences["revenue"] = 0.95
            elif n_low in ("sales", "sales_amount", "net_sales", "total_amount", "daily_revenue", "turnover"):
                mappings["revenue"] = name
                confidences["revenue"] = 0.90
            elif role == "monetary_amount":
                mappings["revenue"] = name
                confidences["revenue"] = 0.75

        # Quantity mapping
        if "quantity" not in mappings:
            if role == "quantity" or n_low in ("quantity", "qty", "units", "units_sold"):
                mappings["quantity"] = name
                confidences["quantity"] = 0.90

        # Customer mapping
        if "customer" not in mappings:
            if role == "customer_identifier" or n_low in ("customer_id", "buyer_id", "client_id", "user_id"):
                mappings["customer"] = name
                confidences["customer"] = 0.90

        # Order mapping
        if "order" not in mappings:
            if role == "order_identifier" or n_low in ("order_id", "invoice_number", "order_no", "invoice_id"):
                mappings["order"] = name
                confidences["order"] = 0.90

    return mappings, confidences


def assess_dataset_granularity(
    parquet_path: Optional[Any], columns: list[dict], row_count: int
) -> GranularityReport:
    """Inspects dataset structure to identify whether it is transaction, order-item, or aggregated."""
    if not parquet_path or not parquet_path.exists() or row_count == 0:
        return GranularityReport(
            likely_granularity="generic_tabular",
            distinct_id_ratio=None,
            has_repeated_orders=False,
            aggregation_policy_note="Standard tabular records. Observations treated as independent.",
        )

    # Find potential order or transaction identifier
    id_col = next(
        (c.get("name") for c in columns if "order" in str(c.get("business_role", "")).lower() or "order" in c.get("name", "").lower() or "invoice" in c.get("name", "").lower()),
        None,
    )

    if not id_col:
        # Check if single date column with unique count == row count
        date_col = next(
            (c for c in columns if c.get("semantic_type") == "DATE" or "date" in c.get("name", "").lower()),
            None,
        )
        if date_col and int(date_col.get("unique_count") or 0) >= row_count * 0.9:
            return GranularityReport(
                likely_granularity="daily_aggregated",
                distinct_id_ratio=1.0,
                has_repeated_orders=False,
                aggregation_policy_note="Already aggregated time-series data. Further summation may not be required.",
            )

        return GranularityReport(
            likely_granularity="generic_tabular",
            distinct_id_ratio=None,
            has_repeated_orders=False,
            aggregation_policy_note="Generic tabular structure. No order identifier detected.",
        )

    # Query distinct counts in Parquet via DuckDB
    escaped = '"' + id_col.replace('"', '""') + '"'
    p_str = str(parquet_path).replace("\\", "/")

    try:
        con = duckdb.connect()
        res = con.execute(f"SELECT COUNT(DISTINCT {escaped}) AS distinct_cnt, COUNT(*) AS total_cnt FROM read_parquet('{p_str}')").fetchone()
        con.close()

        if res and res[1] > 0:
            distinct_cnt, total_cnt = res
            ratio = round(distinct_cnt / total_cnt, 3)

            if ratio < 0.90:
                return GranularityReport(
                    likely_granularity="order_item",
                    distinct_id_ratio=ratio,
                    has_repeated_orders=True,
                    aggregation_policy_note=(
                        f"Order-item level granularity detected ({distinct_cnt} unique orders across {total_cnt} rows). "
                        "Do not sum repeated order totals directly without grouping; order volume must use DISTINCT_COUNT."
                    ),
                )
            else:
                return GranularityReport(
                    likely_granularity="transaction",
                    distinct_id_ratio=ratio,
                    has_repeated_orders=False,
                    aggregation_policy_note="One row per transaction. Direct summation of metrics is safe.",
                )
    except Exception as e:
        logger.debug("Failed granularity check: %s", e)

    return GranularityReport(
        likely_granularity="transaction",
        distinct_id_ratio=1.0,
        has_repeated_orders=False,
        aggregation_policy_note="Observations treated as discrete transactional records.",
    )


def assess_capabilities(
    dataset_id: str, manual_overrides: Optional[dict[str, str]] = None
) -> CapabilityAssessmentResponse:
    """Central assessment of prediction and forecasting capabilities for a dataset."""
    meta = get_metadata(dataset_id)
    if not meta:
        raise KeyError(f"Dataset '{dataset_id}' not found.")

    version = int(meta.get("version", 1))
    profile = meta.get("profile", {})
    row_count = int(profile.get("rows", 0))
    columns = meta.get("columns", [])
    all_col_names = [c.get("name") for c in columns]

    # Validate manual overrides if supplied
    all_warnings: list[str] = []
    detected_mappings, confidences = detect_schema_mappings(columns)

    if manual_overrides:
        for concept, col_name in manual_overrides.items():
            if col_name not in all_col_names:
                raise ValueError(
                    f"Configured column '{col_name}' for concept '{concept}' does not exist in dataset."
                )
            detected_mappings[concept] = col_name
            confidences[concept] = 1.0  # manual override is 100% confident

    # Granularity assessment
    parquet_path = get_parquet_path(dataset_id)
    granularity = assess_dataset_granularity(parquet_path, columns, row_count)
    if granularity.has_repeated_orders:
        all_warnings.append(granularity.aggregation_policy_note)

    # 1. Prediction Capability Assessment
    pred_feas = PredictionService.get_feasibility(dataset_id)
    pred_summary = CapabilityPredictionSummary(
        available=pred_feas.prediction_possible,
        recommended_targets=pred_feas.recommended_targets,
        regression_target_count=len(pred_feas.regression_targets),
        classification_target_count=len(pred_feas.classification_targets),
        warnings=pred_feas.warnings,
    )

    # 2. Forecasting Capability Assessment
    fc_feas = ForecastingService.get_feasibility(dataset_id)
    fc_summary = CapabilityForecastingSummary(
        available=fc_feas.forecasting_possible,
        recommended_date_columns=[d.name for d in fc_feas.recommended_date_columns],
        recommended_metrics=[m.name for m in fc_feas.recommended_metrics],
        available_frequencies=fc_feas.available_frequencies,
        is_stale=fc_feas.is_stale,
        missing_requirements=fc_feas.missing_requirements,
        warnings=fc_feas.warnings,
    )

    return CapabilityAssessmentResponse(
        dataset_id=dataset_id,
        dataset_version=version,
        row_count=row_count,
        granularity=granularity,
        capabilities={
            "prediction": pred_summary.model_dump(),
            "forecasting": fc_summary.model_dump(),
        },
        detected_mappings=detected_mappings,
        mapping_confidences=confidences,
        warnings=all_warnings,
    )
