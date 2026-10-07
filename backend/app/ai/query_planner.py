"""Query planner: transforms AI structured output into an internal QueryPlan."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class MetricSpec:
    column: str
    aggregation: str = "SUM"  # SUM, AVG, COUNT, COUNT_DISTINCT, MIN, MAX
    alias: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = {"column": self.column, "aggregation": self.aggregation.upper()}
        if self.alias:
            d["alias"] = self.alias
        return d


@dataclass
class FilterSpec:
    column: str
    operator: str = "="  # =, !=, >, <, >=, <=, contains, in
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "operator": self.operator,
            "value": self.value,
        }


@dataclass
class SortSpec:
    column: str
    direction: str = "DESC"  # ASC, DESC

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "direction": self.direction.upper(),
        }


@dataclass
class ChartConfig:
    type: str = "bar"  # bar, line, pie, area, scatter, kpi, table
    x: Optional[str] = None
    y: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.lower(),
            "x": self.x,
            "y": self.y,
        }


@dataclass
class QueryPlan:
    table: str
    intent: str = "aggregation"  # aggregation, comparison, ranking, trend, distribution, filter, summary
    dimensions: list[str] = field(default_factory=list)
    metrics: list[MetricSpec] = field(default_factory=list)
    filters: list[FilterSpec] = field(default_factory=list)
    sort: list[SortSpec] = field(default_factory=list)
    limit: Optional[int] = 20
    chart: Optional[ChartConfig] = None
    explanation: Optional[str] = None
    time_grain: Optional[str] = None  # day, month, year

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "intent": self.intent,
            "table": self.table,
            "dimensions": list(self.dimensions),
            "metrics": [m.to_dict() for m in self.metrics],
            "filters": [f.to_dict() for f in self.filters],
            "sort": [s.to_dict() for s in self.sort],
            "limit": self.limit,
            "chart": self.chart.to_dict() if self.chart else None,
            "explanation": self.explanation,
        }
        if self.time_grain:
            res["time_grain"] = self.time_grain
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_table: str = "dataset") -> QueryPlan:
        intent = str(data.get("intent") or "aggregation").lower()
        table = str(data.get("table") or default_table)
        dimensions = [str(d) for d in data.get("dimensions") or [] if d]

        metrics: list[MetricSpec] = []
        for m in data.get("metrics") or []:
            if isinstance(m, dict):
                col = str(m.get("column", "")).strip()
                agg = str(m.get("aggregation", "SUM")).strip().upper()
                alias = m.get("alias")
                if col:
                    metrics.append(MetricSpec(column=col, aggregation=agg, alias=alias))
            elif isinstance(m, str) and m.strip():
                metrics.append(MetricSpec(column=m.strip(), aggregation="SUM"))

        filters: list[FilterSpec] = []
        for f in data.get("filters") or []:
            if isinstance(f, dict):
                col = str(f.get("column", "")).strip()
                op = str(f.get("operator") or f.get("op") or "=").strip()
                val = f.get("value")
                if col:
                    filters.append(FilterSpec(column=col, operator=op, value=val))

        sorts: list[SortSpec] = []
        for s in data.get("sort") or []:
            if isinstance(s, dict):
                col = str(s.get("column", "")).strip()
                direction = str(s.get("direction", "DESC")).strip().upper()
                if col:
                    sorts.append(SortSpec(column=col, direction=direction))

        limit_raw = data.get("limit")
        limit = int(limit_raw) if limit_raw is not None and str(limit_raw).isdigit() else 20
        if limit is not None and limit <= 0:
            limit = None

        chart_raw = data.get("chart")
        chart = None
        if isinstance(chart_raw, dict):
            chart = ChartConfig(
                type=str(chart_raw.get("type", "bar")).lower(),
                x=chart_raw.get("x"),
                y=chart_raw.get("y"),
            )

        explanation = data.get("explanation")
        time_grain = data.get("time_grain")

        return cls(
            table=table,
            intent=intent,
            dimensions=dimensions,
            metrics=metrics,
            filters=filters,
            sort=sorts,
            limit=limit,
            chart=chart,
            explanation=explanation,
            time_grain=time_grain,
        )


def build_query_plan(
    raw_ai_output: dict[str, Any],
    default_table: str = "dataset",
    previous_plan: Optional[QueryPlan] = None,
    user_question: Optional[str] = None,
) -> QueryPlan:
    """Builds and optionally merges QueryPlan with conversation context."""
    plan = QueryPlan.from_dict(raw_ai_output, default_table=default_table)

    # Check for follow-up modifications if previous_plan exists
    if previous_plan is not None and user_question:
        q_lower = user_question.strip().lower()

        # Follow-up: Only top N / limit change
        top_match = re.search(r'\b(?:only\s+)?top\s+(\d+)\b', q_lower)
        if top_match and not plan.dimensions and not plan.metrics:
            n = int(top_match.group(1))
            return QueryPlan(
                table=previous_plan.table,
                intent="ranking",
                dimensions=list(previous_plan.dimensions),
                metrics=list(previous_plan.metrics),
                filters=list(previous_plan.filters),
                sort=list(previous_plan.sort) or ([SortSpec(column=previous_plan.metrics[0].alias or previous_plan.metrics[0].column, direction="DESC")] if previous_plan.metrics else []),
                limit=n,
                chart=previous_plan.chart,
                explanation=f"Updated to show top {n} records from previous analysis.",
                time_grain=previous_plan.time_grain,
            )

        # Follow-up: Chart type switch (e.g. "Now show it as a bar chart" / "as a line chart")
        chart_match = re.search(r'\b(?:show\s+(?:it\s+)?as\s+(?:a\s+)?|make\s+it\s+(?:a\s+)?)(bar|line|pie|area|scatter|table|kpi)\b', q_lower)
        if chart_match and (not plan.dimensions or plan.dimensions == previous_plan.dimensions):
            new_chart_type = chart_match.group(1)
            new_chart = ChartConfig(
                type=new_chart_type,
                x=previous_plan.chart.x if previous_plan.chart else (previous_plan.dimensions[0] if previous_plan.dimensions else None),
                y=previous_plan.chart.y if previous_plan.chart else (previous_plan.metrics[0].alias or previous_plan.metrics[0].column if previous_plan.metrics else None),
            )
            return QueryPlan(
                table=previous_plan.table,
                intent=previous_plan.intent,
                dimensions=list(previous_plan.dimensions),
                metrics=list(previous_plan.metrics),
                filters=list(previous_plan.filters),
                sort=list(previous_plan.sort),
                limit=previous_plan.limit,
                chart=new_chart,
                explanation=f"Switched visualization to {new_chart_type} chart.",
                time_grain=previous_plan.time_grain,
            )

    return plan
