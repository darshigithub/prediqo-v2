"""AI Analyst service: end-to-end question answering pipeline.

Deterministic parser by default. If OPENAI_API_KEY is set, an optional AI
provider is used to parse the question into the same structured query
contract; execution and charting are unchanged.
"""
import os
from typing import Any

from ..models.schemas import AggregationQuery, ChartSpec
from ..charts.recommender import recommend_chart
from ..query_engine.executor import execute_query
from ..query_engine.insights import generate_insight
from ..query_engine.parser import parse_question
from ..storage.dataset_store import get_dataset


def _schema_for_parser(ds) -> list[dict]:
    return [
        {"name": c.name, "semantic_type": c.semantic_type, "dtype": c.dtype}
        for c in ds.columns
    ]


def _ai_parse(question: str, schema: list[dict]) -> dict | None:
    """Optional AI provider (OpenAI-compatible). Returns None when unavailable."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # optional dependency

        client = OpenAI(api_key=api_key)
        sys_prompt = (
            "You convert analytics questions into JSON with keys: "
            '{"group_by": [str], "metric": str, "aggregation": "sum|avg|count|min|max", '
            '"filters": [{"column","op","value"}], "sort_order": "asc|desc", "top_n": int|null, '
            '"time_grain": "day|month|year"|null}. '
            "Use __count__ as metric for counting rows. Column list: "
            + ", ".join(f"{c['name']}({c['semantic_type']})" for c in schema)
        )
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,
        )
        import json
        parsed = json.loads(resp.choices[0].message.content)
        return parsed
    except Exception:
        return None


def answer_question(dataset_id: str, question: str) -> dict[str, Any]:
    ds = get_dataset(dataset_id)
    if ds is None:
        raise KeyError(f"Dataset not found: {dataset_id}")

    schema = _schema_for_parser(ds)
    parsed = _ai_parse(question, schema)
    parser_used = "deterministic"

    if parsed:
        parser_used = "ai"
        query = AggregationQuery(
            dataset_id=dataset_id,
            group_by=parsed.get("group_by") or [],
            metric=parsed.get("metric") or "__count__",
            aggregation=parsed.get("aggregation") or "sum",
            filters=parsed.get("filters") or [],
            sort_order=parsed.get("sort_order") or "desc",
            top_n=parsed.get("top_n"),
        )
    else:
        result = parse_question(question, schema)
        query = AggregationQuery(**result["query"])
        query.dataset_id = dataset_id

    # Execute
    query_dict = query.model_dump()
    query_dict["time_grain"] = _detect_time_grain(question)
    from ..storage.dataset_store import get_parquet_path
    p_path = get_parquet_path(dataset_id)
    source = p_path if (p_path and p_path.exists()) else ds.dataframe
    exec_result = execute_query(source, AggregationQuery(**query_dict))

    rec = recommend_chart(exec_result, schema)
    insight = generate_insight(exec_result)

    return {
        "question": question,
        "query": query_dict,
        "result": exec_result,
        "chart_type": rec["chart_type"],
        "chart_reason": rec["reason"],
        "insight": insight,
        "parser_used": parser_used,
    }


def _detect_time_grain(question: str) -> str | None:
    q = (question or "").lower()
    if "month" in q:
        return "month"
    if "year" in q:
        return "year"
    if "day" in q or "daily" in q:
        return "day"
    return None


def execute_chart_spec(dataset_id: str, spec: ChartSpec) -> dict[str, Any]:
    """Execute a manual chart spec (Chart Builder)."""
    ds = get_dataset(dataset_id)
    if ds is None:
        raise KeyError(f"Dataset not found: {dataset_id}")

    metric = spec.metric or "__count__"
    aggregation = spec.aggregation or "sum"
    if spec.type == "kpi" and not spec.dimension:
        group_by: list[str] = []
    else:
        group_by = [spec.dimension] if spec.dimension else []

    query = AggregationQuery(
        dataset_id=dataset_id,
        group_by=group_by,
        metric=metric,
        aggregation=aggregation,
        filters=spec.filters or [],
        sort_by=None,
        sort_order=spec.sort or "desc",
        top_n=spec.top_n,
    )
    from ..storage.dataset_store import get_parquet_path
    p_path = get_parquet_path(dataset_id)
    source = p_path if (p_path and p_path.exists()) else ds.dataframe
    exec_result = execute_query(source, query)

    schema = _schema_for_parser(ds)
    rec = recommend_chart(exec_result, schema)
    insight = generate_insight(exec_result)

    return {
        "spec": spec.model_dump(),
        "result": exec_result,
        "chart_type": spec.type if spec.type != "auto" else rec["chart_type"],
        "recommended_type": rec["chart_type"],
        "insight": insight,
    }
