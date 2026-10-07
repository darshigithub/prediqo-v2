"""Query validator: validates QueryPlan against dataset schema and semantic rules before execution."""
from __future__ import annotations

from typing import Any, Iterable, Optional

from .query_planner import QueryPlan

ALLOWED_AGGREGATIONS = {"SUM", "AVG", "COUNT", "COUNT_DISTINCT", "MIN", "MAX"}
ALLOWED_OPERATORS = {
    "=", "==", "!=", "<>", ">", "<", ">=", "<=", "contains", "in", "like", "ilike",
    "eq", "ne", "gt", "lt", "gte", "lte"
}
MAX_QUERY_ROWS = 10000


class QueryValidationError(ValueError):
    """Raised when an analytical query plan violates dataset schema or safety rules."""
    pass


def validate_query_plan(
    plan: QueryPlan,
    available_columns: Iterable[str],
    dataset_name: str = "dataset",
    columns_meta: Optional[dict[str, Any] | list[Any]] = None,
) -> QueryPlan:
    """Validates the QueryPlan against dataset columns, semantic types, and safety constraints.

    Returns the validated QueryPlan or raises QueryValidationError.
    """
    col_set = set(available_columns)
    col_set_lower = {c.lower(): c for c in col_set}

    meta_dict: dict[str, Any] = {}
    if columns_meta:
        if isinstance(columns_meta, list):
            meta_dict = {
                (c.get("name", "") if isinstance(c, dict) else getattr(c, "name", "")).lower(): c
                for c in columns_meta
            }
        elif isinstance(columns_meta, dict):
            meta_dict = {k.lower(): v for k, v in columns_meta.items()}

    # 1. Validate Table
    if not plan.table:
        plan.table = dataset_name

    # 2. Validate Dimensions
    validated_dimensions: list[str] = []
    for dim in plan.dimensions:
        if dim in col_set:
            validated_dimensions.append(dim)
        elif dim.lower() in col_set_lower:
            validated_dimensions.append(col_set_lower[dim.lower()])
        else:
            raise QueryValidationError(
                f"The dataset does not contain dimension column '{dim}'. Available columns: {sorted(col_set)}"
            )
    plan.dimensions = validated_dimensions

    # 3. Validate Metrics & Aggregations
    metric_aliases = set()
    validated_metrics = []
    for m in plan.metrics:
        agg = m.aggregation.upper()
        if agg not in ALLOWED_AGGREGATIONS:
            raise QueryValidationError(
                f"Unsupported aggregation '{m.aggregation}'. Supported aggregations: {sorted(ALLOWED_AGGREGATIONS)}"
            )
        m.aggregation = agg

        # Metric column check
        col = m.column
        if col in ("*", "__count__", "1"):
            validated_col = col
        elif col in col_set:
            validated_col = col
        elif col.lower() in col_set_lower:
            validated_col = col_set_lower[col.lower()]
        else:
            raise QueryValidationError(
                f"The dataset does not contain metric column '{col}'. Available columns: {sorted(col_set)}"
            )

        # Semantic aggregation compatibility check
        col_key = validated_col.lower()
        if col_key in meta_dict:
            cm = meta_dict[col_key]
            sem_type = cm.get("semantic_type", "") if isinstance(cm, dict) else getattr(cm, "semantic_type", "")
            b_role = cm.get("business_role", "") if isinstance(cm, dict) else getattr(cm, "business_role", "")

            # Rule: IDs must NEVER be summed or averaged
            if sem_type == "ID" or b_role.endswith("identifier"):
                if agg in ("SUM", "AVG", "MIN", "MAX"):
                    verb = "summed" if agg == "SUM" else f"{agg.lower()}ed"
                    raise QueryValidationError(f"'{validated_col}' is an identifier and cannot be {verb}.")

            # Rule: Categorical text fields must not be summed or averaged
            elif sem_type in ("CATEGORY", "DIMENSION", "TEXT"):
                if agg in ("SUM", "AVG"):
                    raise QueryValidationError(f"'{validated_col}' is a {sem_type.lower()} column and cannot be {agg.lower()}ed.")

            # Rule: Dates must not be summed or averaged
            elif sem_type == "DATE":
                if agg in ("SUM", "AVG"):
                    raise QueryValidationError(f"'{validated_col}' is a date column and cannot be {agg.lower()}ed.")

        m.column = validated_col
        if not m.alias:
            m.alias = f"{agg.lower()}_{validated_col.lower()}" if validated_col not in ("*", "__count__") else "count"
        metric_aliases.add(m.alias)
        metric_aliases.add(validated_col)
        validated_metrics.append(m)
    plan.metrics = validated_metrics

    # 4. Validate Filters
    for f in plan.filters:
        col = f.column
        if col in col_set:
            f.column = col
        elif col.lower() in col_set_lower:
            f.column = col_set_lower[col.lower()]
        else:
            raise QueryValidationError(
                f"Filter references unknown column '{col}'. Available columns: {sorted(col_set)}"
            )

        op = f.operator.lower()
        if op not in ALLOWED_OPERATORS:
            raise QueryValidationError(
                f"Filter on '{col}' uses unsupported operator '{f.operator}'."
            )

    # 5. Validate Sort
    valid_sort_targets = col_set.union(metric_aliases).union(set(plan.dimensions))
    valid_sort_targets_lower = {c.lower(): c for c in valid_sort_targets}
    for s in plan.sort:
        col = s.column
        if col in valid_sort_targets:
            s.column = col
        elif col.lower() in valid_sort_targets_lower:
            s.column = valid_sort_targets_lower[col.lower()]
        else:
            raise QueryValidationError(
                f"Sort references unknown field '{col}'. Must be a valid column, dimension, or metric."
            )

        direction = s.direction.upper()
        if direction not in ("ASC", "DESC"):
            s.direction = "DESC"

    # 6. Validate Limit
    if plan.limit is None:
        plan.limit = 100
    elif plan.limit > MAX_QUERY_ROWS:
        plan.limit = MAX_QUERY_ROWS
    elif plan.limit <= 0:
        plan.limit = 20

    # 7. Validate Chart Config
    if plan.chart:
        chart_type = plan.chart.type.lower()
        valid_chart_types = {"bar", "line", "pie", "area", "scatter", "kpi", "table"}
        if chart_type not in valid_chart_types:
            plan.chart.type = "bar"

    return plan


def correct_identifier_aggregation(
    plan: QueryPlan,
    columns_meta: dict[str, Any] | list[Any],
) -> tuple[QueryPlan, bool]:
    """Auto-corrects invalid identifier aggregations (e.g. SUM(order_id) -> COUNT(order_id))."""
    if isinstance(columns_meta, list):
        meta_dict = {
            (c.get("name", "") if isinstance(c, dict) else getattr(c, "name", "")).lower(): c
            for c in columns_meta
        }
    elif isinstance(columns_meta, dict):
        meta_dict = {k.lower(): v for k, v in columns_meta.items()}
    else:
        meta_dict = {}

    corrected = False
    for m in plan.metrics:
        col_lower = m.column.lower()
        if col_lower in meta_dict:
            cm = meta_dict[col_lower]
            sem_type = cm.get("semantic_type", "") if isinstance(cm, dict) else getattr(cm, "semantic_type", "")
            b_role = cm.get("business_role", "") if isinstance(cm, dict) else getattr(cm, "business_role", "")

            if (sem_type == "ID" or b_role.endswith("identifier")) and m.aggregation.upper() in ("SUM", "AVG"):
                prev_agg = m.aggregation.upper()
                verb = "summed" if prev_agg == "SUM" else f"{prev_agg.lower()}ed"
                m.aggregation = "COUNT"
                m.alias = f"count_{m.column.lower()}"
                plan.explanation = (
                    f"'{m.column}' is an identifier and cannot be {verb}, "
                    f"so it was interpreted as the total count of {m.column}."
                )
                corrected = True

    return plan, corrected
