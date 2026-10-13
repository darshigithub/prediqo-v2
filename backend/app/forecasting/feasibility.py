"""Forecasting feasibility analysis and eligibility checks."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional
import pandas as pd

from ..prediction.target_detector import is_identifier_column
from ..prediction.predictor import infer_unit_from_target
from ..prediction.models import ColumnInfoItem, DataQualitySummary
from .models import (
    ForecastCandidateDate,
    ForecastCandidateMetric,
    ForecastFeasibilityResponse,
)

_DATE_PATTERNS = re.compile(
    r"\b(date|time|timestamp|created_at|order_date|transaction_date|purchased_on|"
    r"sale_date|invoice_date|booking_date|event_time|datetime|day|month|year)\b",
    re.IGNORECASE,
)


def detect_forecasting_dates(columns: list[dict]) -> list[ForecastCandidateDate]:
    """Detects candidate date/time columns for forecasting."""
    dates: list[ForecastCandidateDate] = []

    for c in columns:
        name = c.get("name", "")
        dtype = str(c.get("dtype", "")).lower()
        sem_type = str(c.get("semantic_type", "")).upper()
        disp_name = c.get("display_name") or name
        unique_cnt = int(c.get("unique_count") or 0)
        min_val = c.get("min")
        max_val = c.get("max")

        is_date = (
            sem_type == "DATE"
            or "date" in dtype
            or "time" in dtype
            or bool(_DATE_PATTERNS.search(name))
        )

        if is_date and unique_cnt >= 2:
            dates.append(
                ForecastCandidateDate(
                    name=name,
                    display_name=disp_name,
                    dtype=dtype,
                    min_date=str(min_val) if min_val is not None else None,
                    max_date=str(max_val) if max_val is not None else None,
                    distinct_dates=unique_cnt,
                )
            )

    # Prioritize transaction_date / order_date / date
    def _date_prio(d: ForecastCandidateDate) -> int:
        n = d.name.lower()
        if "order_date" in n or "transaction_date" in n or "purchased_on" in n:
            return 3
        if "date" in n or "created_at" in n:
            return 2
        return 1

    dates.sort(key=_date_prio, reverse=True)
    return dates


def detect_forecasting_metrics(columns: list[dict], row_count: int = 0) -> list[ForecastCandidateMetric]:
    """Detects suitable numeric metrics for time-series forecasting."""
    metrics: list[ForecastCandidateMetric] = []

    for c in columns:
        name = c.get("name", "")
        dtype = str(c.get("dtype", "")).lower()
        sem_type = str(c.get("semantic_type", "")).upper()
        role = str(c.get("business_role", "unknown")).lower()
        disp_name = c.get("display_name") or name
        null_cnt = int(c.get("null_count") or 0)
        null_pct = round((null_cnt / max(1, row_count)) * 100.0, 1)

        if is_identifier_column(name, sem_type, role):
            continue
        if sem_type == "DATE" or "date" in dtype or "time" in dtype:
            continue

        is_numeric = any(k in dtype for k in ("int", "float", "double", "decimal", "numeric"))
        if is_numeric and sem_type in ("MEASURE", "DIMENSION", "UNKNOWN"):
            # Determine recommended aggregation
            if role in ("revenue", "sales", "cost", "profit", "monetary_amount", "quantity"):
                rec_agg = "SUM"
                allowed = ["SUM", "AVG", "MIN", "MAX", "COUNT", "DISTINCT_COUNT"]
            elif role in ("rating", "score", "duration", "rate"):
                rec_agg = "AVG"
                allowed = ["AVG", "MIN", "MAX", "COUNT", "DISTINCT_COUNT"]
            else:
                rec_agg = "SUM"
                allowed = ["SUM", "AVG", "MIN", "MAX", "COUNT"]

            metrics.append(
                ForecastCandidateMetric(
                    name=name,
                    display_name=disp_name,
                    dtype=dtype,
                    business_role=role,
                    recommended_aggregation=rec_agg,
                    allowed_aggregations=allowed,
                    unit=infer_unit_from_target(name, "regression"),
                    null_count=null_cnt,
                    null_percentage=null_pct,
                )
            )

    # Prioritize revenue, sales, quantity
    def _metric_prio(m: ForecastCandidateMetric) -> int:
        r = m.business_role.lower()
        if r in ("revenue", "sales", "quantity", "profit"):
            return 3
        if "amount" in m.name.lower() or "sales" in m.name.lower() or "qty" in m.name.lower():
            return 2
        return 1

    metrics.sort(key=_metric_prio, reverse=True)
    return metrics


def check_forecast_feasibility(meta: dict, dataset_id: str) -> ForecastFeasibilityResponse:
    """Evaluates whether time-series forecasting is eligible and meaningful for a dataset."""
    status = meta.get("status", "READY")
    version = int(meta.get("version", 1))
    profile = meta.get("profile", {})
    row_count = int(profile.get("rows", 0))
    columns = meta.get("columns", [])

    warnings: list[str] = []
    missing_reqs: list[str] = []

    # Calculate Data Quality & Column Details
    columns_info: list[ColumnInfoItem] = []
    cols_with_nulls = 0
    total_null_cells = 0
    total_cells = max(1, row_count * max(1, len(columns)))

    for c in columns:
        c_name = c.get("name", "")
        null_cnt = int(c.get("null_count") or 0)
        if null_cnt > 0:
            cols_with_nulls += 1
            total_null_cells += null_cnt
        null_pct = round((null_cnt / max(1, row_count)) * 100.0, 1)

        sample_vals = None
        if c.get("top_values"):
            sample_vals = [tv.get("value") for tv in c["top_values"][:3] if isinstance(tv, dict)]
        elif c.get("min") is not None and c.get("max") is not None:
            sample_vals = [c.get("min"), c.get("avg"), c.get("max")]

        columns_info.append(
            ColumnInfoItem(
                name=c_name,
                display_name=c.get("display_name") or c_name,
                dtype=str(c.get("dtype", "")).lower(),
                semantic_type=str(c.get("semantic_type", "")).upper() or "DIMENSION",
                business_role=str(c.get("business_role", "")).lower() or "attribute",
                unique_count=int(c.get("unique_count") or 0),
                null_count=null_cnt,
                null_percentage=null_pct,
                sample_values=sample_vals,
                unit=infer_unit_from_target(c_name, ""),
            )
        )

    completeness_pct = round(max(0.0, min(100.0, ((total_cells - total_null_cells) / total_cells) * 100.0)), 1)
    quality_notes: list[str] = [
        f"Dataset contains {row_count:,} observations across {len(columns)} tracked features.",
    ]
    if cols_with_nulls == 0:
        quality_grade = "Excellent" if row_count >= 50 else "Good"
        quality_notes.append("100% complete data cells with zero missing values.")
    elif completeness_pct >= 95.0:
        quality_grade = "Good"
        quality_notes.append(f"{cols_with_nulls} column(s) contain missing values (overall {completeness_pct}% cell completeness).")
    elif completeness_pct >= 80.0:
        quality_grade = "Needs Attention"
        quality_notes.append(f"Noticeable missing data: {cols_with_nulls} column(s) have empty cells ({completeness_pct}% cell completeness).")
    else:
        quality_grade = "Insufficient"
        quality_notes.append(f"High missingness: only {completeness_pct}% of cells are populated.")

    if row_count < 30:
        quality_notes.append(f"Small sample size ({row_count} rows); time-series backtesting will have limited windows.")

    data_quality = DataQualitySummary(
        total_rows=row_count,
        total_columns=len(columns),
        complete_rows_pct=completeness_pct,
        columns_with_nulls=cols_with_nulls,
        quality_grade=quality_grade,
        quality_notes=quality_notes,
    )

    if status != "READY":
        return ForecastFeasibilityResponse(
            dataset_id=dataset_id,
            dataset_version=version,
            row_count=row_count,
            forecasting_possible=False,
            data_quality=data_quality,
            columns_info=columns_info,
            missing_requirements=[f"Dataset status is '{status}'. Forecasting requires status 'READY'."],
            warnings=[f"Dataset status is '{status}'."],
        )

    if row_count < 10:
        return ForecastFeasibilityResponse(
            dataset_id=dataset_id,
            dataset_version=version,
            row_count=row_count,
            forecasting_possible=False,
            data_quality=data_quality,
            columns_info=columns_info,
            missing_requirements=[f"Dataset has only {row_count} rows. At least 10 observations are required."],
            warnings=[f"Insufficient rows ({row_count}) for time-series forecasting."],
        )

    dates = detect_forecasting_dates(columns)
    metrics = detect_forecasting_metrics(columns, row_count=row_count)

    if not dates:
        missing_reqs.append("No valid date or timestamp column detected in dataset.")
    if not metrics:
        missing_reqs.append("No valid numeric measure column detected for aggregation.")

    distinct_periods = dates[0].distinct_dates if dates else 0
    if dates and distinct_periods < 10:
        warnings.append(
            f"Primary date column '{dates[0].name}' contains only {distinct_periods} distinct time periods. "
            "At least 10 distinct periods are recommended for reliable backtesting and forecasting."
        )

    # Check data freshness and staleness
    is_stale = False
    stale_warning = None
    data_start = dates[0].min_date if dates else None
    data_end = dates[0].max_date if dates else None

    if (not data_end or not data_start) and dates:
        from ..storage.dataset_store import get_parquet_path
        import duckdb

        parquet_path = get_parquet_path(dataset_id)
        if parquet_path and parquet_path.exists():
            try:
                p_str = str(parquet_path).replace("\\", "/")
                d_name = '"' + dates[0].name.replace('"', '""') + '"'
                con = duckdb.connect()
                row = con.execute(
                    f"SELECT MIN({d_name})::VARCHAR, MAX({d_name})::VARCHAR FROM read_parquet('{p_str}') WHERE {d_name} IS NOT NULL"
                ).fetchone()
                con.close()
                if row and row[0] is not None and row[1] is not None:
                    data_start = str(row[0])[:10]
                    data_end = str(row[1])[:10]
                    dates[0].min_date = data_start
                    dates[0].max_date = data_end
            except Exception:
                pass


    if data_end:
        try:
            # Parse max date if possible
            end_dt = pd.to_datetime(data_end, errors="coerce")
            if pd.notna(end_dt):
                now_dt = pd.Timestamp.now(tz=end_dt.tz if end_dt.tz is not None else None)
                days_diff = (now_dt - end_dt).days
                if days_diff > 60:
                    is_stale = True
                    stale_warning = (
                        f"Dataset historical observations end on {data_end} ({days_diff} days ago). "
                        "Generated forecasts will project forward from this historical cutoff and reflect a historical projection."
                    )
                    warnings.append(stale_warning)
        except Exception:
            pass

    forecasting_possible = len(dates) > 0 and len(metrics) > 0 and len(missing_reqs) == 0

    return ForecastFeasibilityResponse(
        dataset_id=dataset_id,
        dataset_version=version,
        row_count=row_count,
        forecasting_possible=forecasting_possible,
        recommended_date_columns=dates,
        recommended_metrics=metrics,
        available_frequencies=["daily", "weekly", "monthly"],
        data_start_date=data_start,
        data_end_date=data_end,
        distinct_periods_estimate=distinct_periods,
        is_stale=is_stale,
        stale_warning=stale_warning,
        data_quality=data_quality,
        columns_info=columns_info,
        missing_requirements=missing_reqs,
        warnings=warnings,
    )
