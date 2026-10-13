"""Time-series data preparation and DuckDB aggregation over Parquet."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Tuple
import duckdb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def get_duckdb_date_trunc(frequency: str, date_col: str) -> str:
    """Returns DuckDB SQL expression to truncate a date/timestamp to regular frequency."""
    freq = frequency.lower()
    escaped_col = '"' + date_col.replace('"', '""') + '"'
    if freq == "weekly":
        return f"CAST(date_trunc('week', CAST({escaped_col} AS TIMESTAMP)) AS DATE)"
    elif freq == "monthly":
        return f"CAST(date_trunc('month', CAST({escaped_col} AS TIMESTAMP)) AS DATE)"
    else:  # daily
        return f"CAST(date_trunc('day', CAST({escaped_col} AS TIMESTAMP)) AS DATE)"


def get_duckdb_agg_expr(aggregation: str, metric_col: str) -> str:
    """Returns DuckDB SQL aggregation expression."""
    agg = aggregation.upper()
    escaped_col = '"' + metric_col.replace('"', '""') + '"'
    if agg == "AVG":
        return f"AVG(CAST({escaped_col} AS DOUBLE))"
    elif agg == "COUNT":
        return f"COUNT({escaped_col})"
    elif agg == "DISTINCT_COUNT":
        return f"COUNT(DISTINCT {escaped_col})"
    else:  # SUM
        return f"SUM(CAST({escaped_col} AS DOUBLE))"


def get_pandas_freq_alias(frequency: str) -> str:
    """Returns pandas offset alias for the requested frequency."""
    freq = frequency.lower()
    if freq == "weekly":
        return "W-MON"
    elif freq == "monthly":
        return "MS"
    else:
        return "D"


def aggregate_time_series_from_parquet(
    parquet_path: Path,
    date_col: str,
    metric_col: str,
    frequency: str = "daily",
    aggregation: str = "SUM",
    group_col: Optional[str] = None,
    imputation_method: Optional[str] = None,
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    """Aggregates parquet transactional records into a regular time series using DuckDB.

    Returns:
        df: DataFrame with columns ['ds', 'y'] sorted chronologically.
        stats: Dictionary containing summary of time series characteristics.
        warnings: List of data-quality warnings encountered.
    """
    warnings: list[str] = []
    p_str = str(parquet_path).replace("\\", "/")

    date_trunc_expr = get_duckdb_date_trunc(frequency, date_col)
    agg_expr = get_duckdb_agg_expr(aggregation, metric_col)

    escaped_date = '"' + date_col.replace('"', '""') + '"'
    escaped_metric = '"' + metric_col.replace('"', '""') + '"'

    con = duckdb.connect()
    try:
        sql = f"""
            SELECT
                {date_trunc_expr} AS ds,
                {agg_expr} AS y
            FROM read_parquet('{p_str}')
            WHERE {escaped_date} IS NOT NULL AND {escaped_metric} IS NOT NULL
            GROUP BY ds
            ORDER BY ds ASC
        """
        raw_df = con.execute(sql).df()
    finally:
        con.close()

    if raw_df.empty:
        raise ValueError(
            f"No valid non-null records found when aggregating '{metric_col}' by '{date_col}'."
        )

    # Convert ds to Timestamp
    raw_df["ds"] = pd.to_datetime(raw_df["ds"])
    raw_df["y"] = pd.to_numeric(raw_df["y"], errors="coerce")
    raw_df = raw_df.dropna(subset=["ds", "y"]).sort_values("ds").reset_index(drop=True)

    if len(raw_df) < 5:
        raise ValueError(
            f"Time series has only {len(raw_df)} distinct periods after aggregation. "
            "At least 5 periods are strictly required for forecasting."
        )

    # Build regular continuous frequency index
    min_date = raw_df["ds"].min()
    max_date = raw_df["ds"].max()
    freq_alias = get_pandas_freq_alias(frequency)

    full_date_range = pd.date_range(start=min_date, end=max_date, freq=freq_alias)
    reindexed_df = raw_df.set_index("ds").reindex(full_date_range)
    reindexed_df.index.name = "ds"

    missing_periods = int(reindexed_df["y"].isna().sum())
    total_periods = len(reindexed_df)

    if missing_periods > 0:
        pct_missing = round((missing_periods / total_periods) * 100, 1)
        strategy = (imputation_method or "").lower()
        if not strategy:
            strategy = "zero" if aggregation.upper() in ("SUM", "COUNT", "DISTINCT_COUNT") else "ffill"

        if strategy == "zero":
            reindexed_df["y"] = reindexed_df["y"].fillna(0.0)
            warnings.append(
                f"Time series had {missing_periods} missing periods ({pct_missing}%). "
                "These were imputed with 0.0 (zero activity)."
            )
        elif strategy == "interpolate":
            reindexed_df["y"] = reindexed_df["y"].interpolate(method="linear").bfill().ffill()
            warnings.append(
                f"Time series had {missing_periods} missing periods ({pct_missing}%). "
                "These were imputed using linear interpolation."
            )
        elif strategy == "bfill":
            reindexed_df["y"] = reindexed_df["y"].bfill().ffill()
            warnings.append(
                f"Time series had {missing_periods} missing periods ({pct_missing}%). "
                "These were imputed using backward-fill."
            )
        else:  # ffill
            reindexed_df["y"] = reindexed_df["y"].ffill().bfill()
            warnings.append(
                f"Time series had {missing_periods} missing periods ({pct_missing}%). "
                "These were imputed using forward-fill."
            )


    series_df = reindexed_df.reset_index()
    series_df["ds"] = pd.to_datetime(series_df["ds"])
    series_df["y"] = series_df["y"].astype(float)

    zero_count = int((series_df["y"] == 0.0).sum())
    stats = {
        "start_date": series_df["ds"].min().strftime("%Y-%m-%d"),
        "end_date": series_df["ds"].max().strftime("%Y-%m-%d"),
        "total_periods": total_periods,
        "missing_periods_imputed": missing_periods,
        "zero_count": zero_count,
        "frequency": frequency,
        "aggregation": aggregation,
        "mean_value": round(float(series_df["y"].mean()), 2),
        "std_value": round(float(series_df["y"].std()), 2) if len(series_df) > 1 else 0.0,
    }

    return series_df, stats, warnings
