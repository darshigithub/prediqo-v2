"""Chart recommendation: result shape + semantic types -> chart type."""
from typing import Optional


def recommend_chart(result: dict, columns: Optional[list[dict]] = None) -> dict:
    """Recommend a chart for a query result.

    Rules (per spec):
      Date + metric            -> line
      Category + metric        -> bar (pie when few categories)
      No dimension (single)    -> KPI
      Two numeric fields       -> scatter
      Fallback                 -> table
    """
    data = result.get("data") or []
    dimension = result.get("dimension")
    metric = result.get("metric") or "metric"

    semantic = {(c.get("name")): c.get("semantic_type") for c in (columns or [])}
    dim_semantic = semantic.get(dimension)

    if not data:
        return {"chart_type": "table", "reason": "No data to visualize"}

    # Single KPI value
    if dimension is None or (len(data) == 1 and len(data[0]) == 1):
        return {"chart_type": "kpi", "reason": "Single metric value"}

    if dimension and dimension in data[0]:
        sample = data[0][dimension]
        if isinstance(sample, str) and (
            dim_semantic == "DATE"
            or any(k in dimension.lower() for k in ("date", "month", "year", "week", "day", "quarter"))
        ):
            return {"chart_type": "line", "reason": "Time dimension -> trend line"}

        uniq = len({str(r.get(dimension)) for r in data})
        if uniq == 2 and all(isinstance(r.get(dimension), (int, float)) for r in data):
            return {"chart_type": "scatter", "reason": "Two numeric fields"}
        # Category + metric defaults to bar (pie/area remain available in the
        # Chart Builder for users who prefer them).
        return {"chart_type": "bar", "reason": f"Category + metric -> bar chart ({uniq} categories)"}

    # Multiple numeric columns, no clear dimension
    if data and len(data[0]) >= 2 and all(
        isinstance(v, (int, float)) for v in list(data[0].values())[:2]
    ):
        return {"chart_type": "scatter", "reason": "Two numeric fields"}

    return {"chart_type": "table", "reason": "Tabular result"}
