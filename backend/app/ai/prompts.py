"""System prompts and context builders for OpenAI / multi-provider AI Analyst."""
from __future__ import annotations

import json
from typing import Any, Optional

from ..models.dataset import StandardDataset
from ..standardization.semantics import discover_derived_metrics

ANALYST_SYSTEM_PROMPT = """You are an expert AI Data Analyst.
Your role is to translate a user's natural language question into a precise, structured analytical query plan that will be executed by our backend query engine.

STRICT OPERATING RULES:
1. Only use columns that exist in the provided dataset schema.
2. Never invent columns or attributes.
3. Never invent metrics.
4. Never invent or assume data values.
5. Never fabricate query results.
6. Use only the supplied dataset schema and column metadata.
7. Prefer existing semantic measures and metrics.
8. Return ONLY valid JSON adhering to the specified schema.
9. Never return executable Python code.
10. Never return raw SQL as primary output.
11. Do not execute or suggest destructive database commands.
12. If the user question is ambiguous or vague, choose the most sensible analytical interpretation and explain it clearly in "explanation".
13. If the requested analysis cannot be performed with the available columns, explain why in "explanation" and leave "metrics" and "dimensions" empty.
14. Select the most appropriate visualization ("bar", "line", "pie", "area", "scatter", "kpi", "table").
    - Use "bar" for category comparisons and rankings.
    - Use "line" or "area" for trends over time/dates.
    - Use "pie" for part-to-whole distributions with few categories (<= 7).
    - Use "kpi" for single scalar summary numbers.
    - Use "table" for multi-column detail views or filters.
15. Keep the analytical query as simple and direct as possible.
16. SEMANTIC BUSINESS ROLES & IDENTIFIERS:
    - Never sum or average identifiers (semantic_type=ID or business_role ends with '_identifier').
    - For questions asking about order volume, transaction count, or customer numbers (e.g. "how many orders", "total orders", "orders by city", "order trends"), use COUNT(identifier_col) or COUNT(*).
    - If a user asks "total order id", interpret as COUNT(order_id) and explain that order_id is an identifier.
    - If a user asks to average an identifier, explain that identifiers cannot be averaged.
    - For measures with business_role=revenue or monetary_amount, use SUM by default for totals, or AVG for averages.
    - For ratings and duration, use AVG by default.

SUPPORTED INTENTS:
- aggregation (e.g. "Show revenue by city", "Orders per payment method")
- comparison (e.g. "Compare revenue between Bengaluru and Mumbai")
- ranking (e.g. "What are the top 10 products by revenue?")
- trend (e.g. "Show monthly revenue", "Order trends over time")
- distribution (e.g. "Show the distribution of customer ratings")
- filter (e.g. "Show completed orders from Bengaluru", "Electronics orders in Delhi")
- summary (e.g. "Give me a summary of this dataset", "What is total sales?")

OUTPUT JSON SCHEMA:
{
  "intent": "aggregation" | "comparison" | "ranking" | "trend" | "distribution" | "filter" | "summary",
  "table": "<table_name>",
  "dimensions": ["<column_name>"],
  "metrics": [
    {
      "column": "<column_name>",
      "aggregation": "SUM" | "AVG" | "COUNT" | "COUNT_DISTINCT" | "MIN" | "MAX",
      "alias": "<clean_snake_case_alias>"
    }
  ],
  "filters": [
    {
      "column": "<column_name>",
      "operator": "=" | "!=" | ">" | "<" | ">=" | "<=" | "contains" | "in",
      "value": "<value>"
    }
  ],
  "sort": [
    {
      "column": "<metric_alias_or_column>",
      "direction": "ASC" | "DESC"
    }
  ],
  "limit": <integer_or_null>,
  "time_grain": "day" | "month" | "year" | null,
  "chart": {
    "type": "bar" | "line" | "pie" | "area" | "scatter" | "kpi" | "table",
    "x": "<dimension_name_or_null>",
    "y": "<metric_alias_or_null>"
  },
  "explanation": "<Concise 1-2 sentence description of what this query computes>"
}

When the user asks for a filter query (e.g. "Show completed orders in Bengaluru"), set:
- intent: "filter"
- filters: appropriate filter conditions
- dimensions: key columns or leave empty for all columns
- metrics: []
- chart: {"type": "table"}

When the user asks for a time trend (e.g. "monthly revenue"):
- set time_grain: "month"
- dimension: the date column
- chart: {"type": "line"}
"""


def build_dataset_context(dataset: Any) -> dict[str, Any]:
    """Builds a compact, rich semantic metadata context for the AI without sending the entire dataset."""
    tables_columns = []
    available_metrics = []
    available_dimensions = []
    date_columns = []
    identifiers = []

    if isinstance(dataset, dict):
        dataset_name = dataset.get("dataset_name", "dataset")
        source_type = dataset.get("source_type", "DATASET")
        profile = dataset.get("profile", {})
        profile_stats = profile.get("column_stats", {})
        row_count = profile.get("rows", 0)
        column_count = profile.get("columns", len(dataset.get("columns", [])))

        # Convert dict columns to ColumnMeta-like objects for discover_derived_metrics
        cols_for_derived = [
            ColumnMeta(
                name=c["name"],
                dtype=c.get("dtype", "string"),
                semantic_type=c.get("semantic_type", "DIMENSION"),
                unique_count=c.get("unique_count", 0),
                null_count=c.get("null_count", 0),
                business_role=c.get("business_role", "unknown"),
                display_name=c.get("display_name", c["name"]),
                allowed_aggregations=c.get("allowed_aggregations", []),
            )
            for c in dataset.get("columns", [])
        ]

        for col in dataset.get("columns", []):
            c_name = col["name"]
            c_type = col.get("dtype", "string")
            c_semantic = col.get("semantic_type", "DIMENSION")
            stat = profile_stats.get(c_name, {})
            b_role = col.get("business_role") or stat.get("business_role", "unknown")
            d_name = col.get("display_name") or stat.get("display_name", c_name)
            allowed_aggs = col.get("allowed_aggregations") or stat.get("allowed_aggregations", [])

            col_info: dict[str, Any] = {
                "name": c_name,
                "type": c_type,
                "semantic_type": c_semantic,
                "business_role": b_role,
                "display_name": d_name,
                "allowed_aggregations": allowed_aggs,
                "unique_count": col.get("unique_count", 0),
                "null_count": col.get("null_count", 0),
            }

            if col.get("min") is not None:
                col_info["min"] = col["min"]
            if col.get("max") is not None:
                col_info["max"] = col["max"]
            if col.get("avg") is not None:
                col_info["avg"] = col["avg"]

            top_vals = col.get("top_values") or stat.get("top_values")
            if top_vals:
                col_info["sample_values"] = [v["value"] for v in top_vals[:5] if isinstance(v, dict) and v.get("value") is not None]

            tables_columns.append(col_info)

            if c_semantic == "ID" or b_role.endswith("identifier"):
                identifiers.append(f"{c_name} ({b_role})")
            elif c_semantic == "MEASURE":
                available_metrics.append(f"{c_name} (role: {b_role}, allowed: {', '.join(allowed_aggs)})")
            elif c_semantic in ("CATEGORY", "DIMENSION"):
                available_dimensions.append(f"{c_name} ({b_role})")

            if c_semantic == "DATE" or "datetime" in str(c_type).lower():
                date_columns.append(c_name)

        sem_model = dataset.get("semantic_model", {})
        derived_metrics = sem_model.get("derived_metrics") or discover_derived_metrics(cols_for_derived)

        return {
            "dataset_name": dataset_name,
            "source": source_type.upper(),
            "row_count": row_count,
            "column_count": column_count,
            "tables": [
                {
                    "name": dataset_name,
                    "columns": tables_columns,
                }
            ],
            "available_metrics": available_metrics,
            "available_dimensions": available_dimensions,
            "date_columns": date_columns,
            "identifiers": identifiers,
            "derived_metrics": [f"{m['name']} ({m.get('description', '')})" for m in derived_metrics],
        }

    # StandardDataset branch
    profile_stats = dataset.profile.column_stats if dataset.profile else {}

    for col in dataset.columns:
        stat = profile_stats.get(col.name, {})
        b_role = getattr(col, "business_role", stat.get("business_role", "unknown"))
        d_name = getattr(col, "display_name", stat.get("display_name", col.name))
        allowed_aggs = getattr(col, "allowed_aggregations", stat.get("allowed_aggregations", []))

        col_info: dict[str, Any] = {
            "name": col.name,
            "type": col.dtype,
            "semantic_type": col.semantic_type,
            "business_role": b_role,
            "display_name": d_name,
            "allowed_aggregations": allowed_aggs,
            "unique_count": col.unique_count,
            "null_count": col.null_count,
        }

        # Numeric statistics
        if col.min is not None:
            col_info["min"] = col.min
        if col.max is not None:
            col_info["max"] = col.max
        if col.avg is not None:
            col_info["avg"] = col.avg

        # Categorical sample values
        if col.top_values:
            col_info["sample_values"] = [v["value"] for v in col.top_values[:5] if v.get("value") is not None]
        elif stat.get("top_values"):
            col_info["sample_values"] = [v["value"] for v in stat["top_values"][:5] if v.get("value") is not None]

        tables_columns.append(col_info)

        # Categorize column into lists
        if col.semantic_type == "ID" or b_role.endswith("identifier"):
            identifiers.append(f"{col.name} ({b_role})")
        elif col.semantic_type == "MEASURE":
            available_metrics.append(f"{col.name} (role: {b_role}, allowed: {', '.join(allowed_aggs)})")
        elif col.semantic_type in ("CATEGORY", "DIMENSION"):
            available_dimensions.append(f"{col.name} ({b_role})")

        if col.semantic_type == "DATE" or "datetime" in str(col.dtype).lower():
            date_columns.append(col.name)

    derived_metrics = discover_derived_metrics(dataset.columns)

    return {
        "dataset_name": dataset.dataset_name,
        "source": dataset.source_type.upper(),
        "row_count": dataset.profile.rows if dataset.profile else len(dataset.dataframe),
        "column_count": dataset.profile.columns if dataset.profile else len(dataset.columns),
        "tables": [
            {
                "name": dataset.dataset_name,
                "columns": tables_columns,
            }
        ],
        "available_metrics": available_metrics,
        "available_dimensions": available_dimensions,
        "date_columns": date_columns,
        "identifiers": identifiers,
    }



def build_user_prompt(
    question: str,
    context: dict[str, Any],
    previous_plan: Optional[dict[str, Any]] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> str:
    """Builds the prompt for the AI to generate the structured query plan."""
    prompt_lines = [
        f"DATASET CONTEXT:",
        f"Dataset: {context.get('dataset_name')}",
        f"Source: {context.get('source')}",
        f"Total Rows: {context.get('row_count')}",
        f"Total Columns: {context.get('column_count')}",
        "",
        "AVAILABLE COLUMNS & SEMANTIC METADATA:",
    ]

    for table in context.get("tables", []):
        for col in table.get("columns", []):
            line = f"- {col['name']}: type={col.get('type')}, semantic_type={col.get('semantic_type')}, business_role={col.get('business_role')}"
            if col.get("allowed_aggregations"):
                line += f", allowed_aggs=[{', '.join(col.get('allowed_aggregations'))}]"
            if "sample_values" in col and col["sample_values"]:
                samples = ", ".join(f"'{s}'" for s in col["sample_values"][:5])
                line += f", samples=[{samples}]"
            if "min" in col and "max" in col:
                line += f", min={col['min']}, max={col['max']}"
            prompt_lines.append(line)

    prompt_lines.extend([
        "",
        f"Identifiers (Count only): {', '.join(context.get('identifiers', [])) or 'None'}",
        f"Available Measures: {', '.join(context.get('available_metrics', [])) or 'None'}",
        f"Available Dimensions: {', '.join(context.get('available_dimensions', [])) or 'None'}",
        f"Available Date Columns: {', '.join(context.get('date_columns', [])) or 'None'}",
    ])

    derived = context.get("derived_metrics", [])
    if derived:
        prompt_lines.extend([
            "",
            "RECOMMENDED DERIVED METRICS:",
        ])
        for dm in derived:
            prompt_lines.append(f"- {dm['display_name']}: {dm['aggregation']}({dm['column']}) -> {dm.get('description', '')}")

    if previous_plan:
        prompt_lines.extend([
            "",
            "PREVIOUS QUERY CONTEXT (active query the user may be modifying):",
            json.dumps(previous_plan, indent=2),
            "If the current question is a follow-up (e.g. 'only top 5', 'show as bar chart', 'only completed orders', 'filter by Delhi'), adjust the previous query plan accordingly!",
        ])

    if conversation_history:
        prompt_lines.extend([
            "",
            "RECENT CONVERSATION HISTORY:",
        ])
        for msg in conversation_history[-4:]:
            prompt_lines.append(f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}")

    prompt_lines.extend([
        "",
        f'USER QUESTION: "{question}"',
        "",
        "Generate the structured JSON query plan adhering to the strict schema. Return only valid JSON.",
    ])

    return "\n".join(prompt_lines)


def build_insight_prompt(
    question: str,
    query_plan: dict[str, Any],
    execution_result: dict[str, Any],
) -> str:
    """Builds the prompt to generate business analyst insight AFTER actual query execution."""
    data_sample = execution_result.get("data", [])[:15]
    row_count = execution_result.get("row_count", len(data_sample))

    return f"""You are an executive Data Analyst presenting findings to a business stakeholder.

QUESTION: "{question}"
QUERY INTENT: {query_plan.get('intent', 'aggregation')}
ROWS RETURNED: {row_count}

ACTUAL QUERY EXECUTION RESULT (Data retrieved from DuckDB engine):
{json.dumps(data_sample, indent=2, default=str)}

RULES FOR INSIGHT:
1. Base your insight ONLY on the actual execution result data shown above.
2. Cite the exact figures, names, and patterns directly from the result data.
3. NEVER fabricate or hallucinate any numbers not present in the result.
4. Use professional metric phrasing (e.g. "Revenue" rather than "total_amount", "Order volume" rather than "order_id count").
5. Keep the explanation professional, concise, and actionable (2 to 4 sentences).
6. Highlight the leader/outlier and the general trend or distribution.
"""
