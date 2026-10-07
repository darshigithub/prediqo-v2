"""Insights: derived strictly from the actual query result rows with semantic metric labels."""
from typing import Any


def _format_metric_label(metric: str) -> str:
    m = (metric or "value").lower().strip()
    if m in ("total_amount", "revenue", "sales", "sum_total_amount", "total_revenue"):
        return "Revenue"
    if m in ("count", "total_orders", "order_count", "orders", "count_order_id", "order_identifier"):
        return "Order count"
    if m in ("delivery_days", "delivery_time", "avg_delivery_time"):
        return "Delivery time"
    if m in ("customer_rating", "rating", "avg_customer_rating", "avg_rating"):
        return "Customer rating"
    return metric.replace("_", " ").title()


def generate_insight(result: dict) -> str:
    data: list[dict[str, Any]] = result.get("data", [])
    raw_metric = result.get("metric") or "value"
    metric_label = _format_metric_label(raw_metric)
    dimension = result.get("dimension")

    if not data:
        return "The query returned no rows."

    # Single value (KPI)
    if dimension is None or len(data[0]) == 1:
        value = data[0].get(raw_metric, data[0].get("metric"))
        if value is None and data and len(data[0]) > 0:
            value = list(data[0].values())[0]

        if isinstance(value, (int, float)):
            # If counting orders or integer items, show whole number
            if isinstance(value, int) or "count" in raw_metric.lower():
                return f"The {metric_label.lower()} is {int(value):,}."
            return f"The {metric_label.lower()} is {value:,.2f}."
        return f"The {metric_label.lower()} is {value}."

    def _num(row: dict) -> float:
        v = row.get(raw_metric)
        if v is None and len(row) > 1:
            # Fallback to second column value if metric key differs
            v = list(row.values())[1]
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    total = sum(_num(r) for r in data)
    top = max(data, key=_num)
    bottom = min(data, key=_num)
    top_label = str(top.get(dimension, "?"))
    top_val = _num(top)

    parts: list[str] = []
    if len(data) == 1:
        parts.append(f"{top_label} is the top {dimension.replace('_', ' ')} by "
                     f"{metric_label.lower()} ({top_val:,.2f}).")
    elif total:
        share = top_val / total * 100
        parts.append(
            f"{top_label} generated the highest {metric_label.lower()} ({top_val:,.2f}, "
            f"{share:.1f}% of total)."
        )
    else:
        parts.append(f"{top_label} has the highest {metric_label.lower()} ({top_val:,.2f}).")

    if len(data) > 1 and top_label != str(bottom.get(dimension, "?")):
        parts.append(f"{str(bottom.get(dimension, '?'))} has the lowest ({_num(bottom):,.2f}).")

    if len(data) > 2 and total:
        avg = total / len(data)
        above = sum(1 for r in data if _num(r) > avg)
        parts.append(f"{above} of {len(data)} groups are above the average ({avg:,.2f}).")

    return " ".join(parts)
