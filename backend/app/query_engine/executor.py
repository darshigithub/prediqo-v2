"""Query executor: runs structured queries via DuckDB SQL directly over Parquet or in-memory DataFrame."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Union

import duckdb
import pandas as pd

from ..models.schemas import AggregationQuery

logger = logging.getLogger(__name__)

ALLOWED_AGGS = {"sum", "avg", "count", "min", "max", "count_distinct"}


def _quote_ident(name: str) -> str:
    safe = name.replace('"', '""')
    return f'"{safe}"'


def _quote_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _build_filter_sql(filters: list[dict]) -> str:
    clauses: list[str] = []
    for f in filters or []:
        op = str(f.get("op", "=")).lower()
        col = str(f.get("column", ""))
        val = f.get("value")
        ops = {
            "eq": "=", "=": "=", "ne": "!=", "!=": "!=", "gt": ">", ">": ">",
            "lt": "<", "<": "<", "gte": ">=", "lte": "<=",
            "contains": "contains", "in": "in",
        }
        if op not in ops or not col:
            continue
        if op == "contains":
            clauses.append(f"contains(lower(CAST({_quote_ident(col)} AS VARCHAR)), lower({_quote_literal(val)}))")
        elif op == "in":
            vals = ", ".join(_quote_literal(v) for v in (val or []))
            clauses.append(f"{_quote_ident(col)} IN ({vals})")
        else:
            clauses.append(f"{_quote_ident(col)} {ops[op]} {_quote_literal(val)}")
    return (" WHERE " + " AND ".join(clauses)) if clauses else ""


def _prepare_duckdb_source(source: Union[str, Path, pd.DataFrame]) -> tuple[duckdb.DuckDBPyConnection, list[str], dict[str, str]]:
    """Initializes DuckDB connection and exposes 't' directly from Parquet or DataFrame."""
    con = duckdb.connect()
    if isinstance(source, (str, Path)):
        p_str = str(source).replace("\\", "/")
        con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{p_str}')")
    elif isinstance(source, pd.DataFrame):
        if source.empty:
            con.close()
            raise ValueError("Dataset is empty")
        con.register("t", source)
    else:
        con.close()
        raise ValueError(f"Unsupported source type: {type(source)}")

    desc = con.query("DESCRIBE t").fetchall()
    col_names = [row[0] for row in desc]
    col_types = {row[0]: str(row[1]).lower() for row in desc}
    return con, col_names, col_types


def execute_query(source: Union[str, Path, pd.DataFrame], query: AggregationQuery) -> dict:
    """Execute the structured query via DuckDB SQL over Parquet or DataFrame.
    Returns {data, sql, row_count, timing}.
    """
    t0 = time.perf_counter()
    con, col_names, col_types = _prepare_duckdb_source(source)

    try:
        metric = query.metric
        aggregation = (query.aggregation or "sum").lower()
        if aggregation not in ALLOWED_AGGS:
            aggregation = "sum"
        is_count = metric in ("__count__", "*", "1") or aggregation == "count"

        agg_expr = "COUNT(*)" if is_count else f"{aggregation.upper()}({_quote_ident(metric)})"

        group_cols = [c for c in (query.group_by or []) if c in col_names]
        date_grain = None
        if group_cols and any(d_type in col_types.get(group_cols[0], "") for d_type in ("date", "time", "timestamp")):
            date_grain = getattr(query, "time_grain", None) or "month"
            g0 = _quote_ident(group_cols[0])
            if date_grain == "month":
                time_expr = f"date_trunc('month', {g0})"
            elif date_grain == "year":
                time_expr = f"date_trunc('year', {g0})"
            else:
                time_expr = f"date_trunc('day', {g0})"
            select_dim = f"{time_expr} AS {_quote_ident(group_cols[0])}"
        elif group_cols:
            select_dim = ", ".join(_quote_ident(c) for c in group_cols)
        else:
            select_dim = None

        where_sql = _build_filter_sql(query.filters)

        # Prune columns: only requested dimension and aggregated metric are fetched
        if select_dim:
            sql = f"SELECT {select_dim}, {agg_expr} AS metric FROM t{where_sql} GROUP BY 1"
        else:
            sql = f"SELECT {agg_expr} AS metric FROM t{where_sql}"

        out_metric_name = "count" if is_count else metric

        sort_col = query.sort_by if (query.sort_by and query.sort_by in col_names) else None
        if select_dim:
            if sort_col == group_cols[0]:
                sql += f" ORDER BY 1 {query.sort_order.upper()}"
            else:
                sql += f" ORDER BY 2 {query.sort_order.upper()}"

        # Result size control
        if query.top_n:
            sql += f" LIMIT {int(query.top_n)}"
        elif select_dim:
            sql += " LIMIT 500"

        logger.info("DUCKDB_EXECUTION: %s", sql)
        t_duckdb_start = time.perf_counter()
        rel = con.query(sql)
        out_df = rel.df()
        duckdb_ms = int((time.perf_counter() - t_duckdb_start) * 1000)

        # Normalize output
        t_ser_start = time.perf_counter()
        if select_dim:
            dim_name = group_cols[0]
            cols = list(out_df.columns)
            if len(cols) >= 2:
                out_df = out_df.rename(columns={cols[0]: dim_name, cols[-1]: out_metric_name})
            if date_grain:
                fmt = {"month": "%b %Y", "year": "%Y", "day": "%Y-%m-%d"}[date_grain]
                out_df[dim_name] = pd.to_datetime(out_df[dim_name]).dt.strftime(fmt)
        else:
            out_df = out_df.rename(columns={"metric": out_metric_name})

        records = out_df.to_dict(orient="records")
        for r in records:
            for k, v in r.items():
                if pd.isna(v):
                    r[k] = None
                elif isinstance(v, float):
                    r[k] = round(v, 2)

        serialization_ms = int((time.perf_counter() - t_ser_start) * 1000)
        total_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "data": records,
            "sql": sql,
            "row_count": len(records),
            "metric": out_metric_name,
            "dimension": group_cols[0] if group_cols else None,
            "timing": {
                "duckdb_ms": duckdb_ms,
                "serialization_ms": serialization_ms,
                "total_ms": total_ms,
            },
        }
    finally:
        con.close()


def execute_query_plan(source: Union[str, Path, pd.DataFrame], plan: Any) -> dict:
    """Execute a validated QueryPlan using DuckDB SQL directly over Parquet or DataFrame."""
    t0 = time.perf_counter()
    con, col_names, col_types = _prepare_duckdb_source(source)

    try:
        # Build filter SQL with push-down
        filter_dicts = [
            {"column": f.column, "op": f.operator, "value": f.value}
            for f in (getattr(plan, "filters", []) or [])
        ]
        where_sql = _build_filter_sql(filter_dicts)

        intent = str(getattr(plan, "intent", "aggregation")).lower()
        dimensions = getattr(plan, "dimensions", []) or []
        metrics = getattr(plan, "metrics", []) or []
        sort_specs = getattr(plan, "sort", []) or []
        limit_val = getattr(plan, "limit", 20)

        # 1. Filter / Raw rows mode
        if intent == "filter" or (not metrics and dimensions):
            cols = [c for c in dimensions if c in col_names]
            select_cols = ", ".join(_quote_ident(c) for c in cols) if cols else "*"


            order_clauses = []
            for s in sort_specs:
                if s.column in col_names:
                    order_clauses.append(f"{_quote_ident(s.column)} {s.direction.upper()}")
            order_sql = (" ORDER BY " + ", ".join(order_clauses)) if order_clauses else ""
            limit_clause = f" LIMIT {int(limit_val)}" if limit_val else " LIMIT 50"
            sql = f"SELECT {select_cols} FROM t{where_sql}{order_sql}{limit_clause}"

            logger.info("DUCKDB_EXECUTION (filter): %s", sql)
            t_duckdb_start = time.perf_counter()
            rel = con.query(sql)
            out_df = rel.df()
            duckdb_ms = int((time.perf_counter() - t_duckdb_start) * 1000)

            t_ser_start = time.perf_counter()
            for col in out_df.columns:
                if any(d_type in col_types.get(col, "") for d_type in ("date", "time", "timestamp")):
                    out_df[col] = pd.to_datetime(out_df[col]).dt.strftime("%Y-%m-%d")

            records = out_df.to_dict(orient="records")
            for r in records:
                for k, v in r.items():
                    if pd.isna(v):
                        r[k] = None
                    elif isinstance(v, float):
                        r[k] = round(v, 2)

            serialization_ms = int((time.perf_counter() - t_ser_start) * 1000)
            total_ms = int((time.perf_counter() - t0) * 1000)

            return {
                "data": records,
                "columns": list(out_df.columns),
                "sql": sql,
                "row_count": len(records),
                "metric": None,
                "dimension": cols[0] if cols else (col_names[0] if col_names else None),
                "timing": {
                    "duckdb_ms": duckdb_ms,
                    "serialization_ms": serialization_ms,
                    "total_ms": total_ms,
                },
            }

        # 2. Aggregation / Summary mode with Column Pruning
        group_cols = [c for c in dimensions if c in col_names]
        date_grain = getattr(plan, "time_grain", None)
        is_date_group = False
        select_dim_parts: list[str] = []
        dim_display_name = None

        if group_cols:
            dim_display_name = group_cols[0]
            if any(d_type in col_types.get(group_cols[0], "") for d_type in ("date", "time", "timestamp")) or date_grain:
                is_date_group = True
                grain = (date_grain or "month").lower()
                g0 = _quote_ident(group_cols[0])
                if grain == "year":
                    time_expr = f"date_trunc('year', {g0})"
                elif grain == "day":
                    time_expr = f"date_trunc('day', {g0})"
                else:
                    grain = "month"
                    time_expr = f"date_trunc('month', {g0})"
                select_dim_parts.append(f"{time_expr} AS {_quote_ident(group_cols[0])}")
                for gc in group_cols[1:]:
                    select_dim_parts.append(_quote_ident(gc))
            else:
                for gc in group_cols:
                    select_dim_parts.append(_quote_ident(gc))

        metric_expr_parts: list[str] = []
        out_metric_names: list[str] = []
        for m in metrics:
            agg = m.aggregation.upper()
            col = m.column
            alias = m.alias or (f"{agg.lower()}_{col.lower()}" if col not in ("*", "__count__", "1") else "count")
            out_metric_names.append(alias)

            if col in ("*", "__count__", "1") or agg == "COUNT":
                if agg == "COUNT_DISTINCT" and col not in ("*", "__count__", "1"):
                    metric_expr_parts.append(f"COUNT(DISTINCT {_quote_ident(col)}) AS {_quote_ident(alias)}")
                elif agg == "COUNT" and col not in ("*", "__count__", "1"):
                    metric_expr_parts.append(f"COUNT({_quote_ident(col)}) AS {_quote_ident(alias)}")
                else:
                    metric_expr_parts.append(f"COUNT(*) AS {_quote_ident(alias)}")
            elif agg == "COUNT_DISTINCT":
                metric_expr_parts.append(f"COUNT(DISTINCT {_quote_ident(col)}) AS {_quote_ident(alias)}")
            else:
                metric_expr_parts.append(f"{agg}({_quote_ident(col)}) AS {_quote_ident(alias)}")

        if not metric_expr_parts:
            metric_expr_parts.append("COUNT(*) AS count")
            out_metric_names.append("count")

        select_parts = list(select_dim_parts) + metric_expr_parts

        # DuckDB Query with Column Pruning
        if group_cols:
            group_by_nums = ", ".join(str(i + 1) for i in range(len(select_dim_parts)))
            sql = f"SELECT {', '.join(select_parts)} FROM t{where_sql} GROUP BY {group_by_nums}"
        else:
            sql = f"SELECT {', '.join(select_parts)} FROM t{where_sql}"

        order_clauses = []
        for s in sort_specs:
            direction = s.direction.upper()
            if s.column in out_metric_names:
                order_clauses.append(f"{_quote_ident(s.column)} {direction}")
            elif s.column in group_cols:
                order_clauses.append(f"{_quote_ident(s.column)} {direction}")
            elif s.column in col_names:
                order_clauses.append(f"{_quote_ident(s.column)} {direction}")

        if order_clauses:
            sql += f" ORDER BY {', '.join(order_clauses)}"
        elif group_cols:
            if is_date_group:
                sql += f" ORDER BY 1 ASC"
            else:
                sql += f" ORDER BY {len(select_dim_parts) + 1} DESC"

        # Result size limit
        if limit_val:
            sql += f" LIMIT {int(limit_val)}"
        elif group_cols:
            sql += " LIMIT 500"

        logger.info("DUCKDB_EXECUTION (agg): %s", sql)
        t_duckdb_start = time.perf_counter()
        rel = con.query(sql)
        out_df = rel.df()
        duckdb_ms = int((time.perf_counter() - t_duckdb_start) * 1000)

        t_ser_start = time.perf_counter()
        if is_date_group and dim_display_name and dim_display_name in out_df.columns:
            fmt = {"month": "%b %Y", "year": "%Y", "day": "%Y-%m-%d"}.get(date_grain or "month", "%b %Y")
            out_df[dim_display_name] = pd.to_datetime(out_df[dim_display_name]).dt.strftime(fmt)

        records = out_df.to_dict(orient="records")
        for r in records:
            for k, v in r.items():
                if pd.isna(v):
                    r[k] = None
                elif isinstance(v, float):
                    r[k] = round(v, 2)

        serialization_ms = int((time.perf_counter() - t_ser_start) * 1000)
        total_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "data": records,
            "columns": list(out_df.columns),
            "sql": sql,
            "row_count": len(records),
            "metric": out_metric_names[0] if out_metric_names else None,
            "dimension": dim_display_name,
            "timing": {
                "duckdb_ms": duckdb_ms,
                "serialization_ms": serialization_ms,
                "total_ms": total_ms,
            },
        }
    finally:
        con.close()
