"""Deterministic natural-language question parser.

User Question -> Intent Detection -> Structured Query
No external AI API required. An optional AI provider can sit in front of
this later without changing the structured-query contract.
"""
import re
from typing import Optional

from ..models.schemas import AggregationQuery

AGG_KEYWORDS = {
    "sum": ["sum", "total"],
    "avg": ["avg", "average", "mean"],
    "count": ["count", "how many", "number of"],
    "min": ["min", "minimum", "lowest"],
    "max": ["max", "maximum", "highest"],
}

STOPWORDS = {
    "what", "which", "who", "are", "is", "the", "a", "an", "of", "in", "for",
    "by", "and", "or", "to", "show", "me", "list", "give", "tell", "get",
    "top", "bottom", "best", "worst", "per", "each", "all", "from", "with",
    "has", "have", "had", "how", "many", "much", "most", "least", "highest",
    "lowest", "average", "avg", "total", "sum", "count", "maximum", "minimum",
    "value", "values", "revenue", "sales", "amount", "order", "orders",
    "please", "analytics", "data", "there", "were", "was",
}

METRIC_KEYWORDS = {
    r"\b(revenue|sales|amount|value|spent|spend)\b":
        ("revenue", "amount", "total", "sales", "value"),
    r"\b(quantity|units|qty)\b": ("quantity", "qty", "unit"),
    r"\b(rating)\b": ("rating",),
    r"\bage\b": ("age",),
    r"\b(price)\b": ("price",),
    r"\b(discount)\b": ("discount",),
}
COUNT_TRIGGER = r"\b(orders?|transactions?|records?|rows?|entries)\b"


def _detect_aggregation(q: str, metric: str) -> str:
    if metric == "__count__":
        return "count"
    for agg, words in AGG_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(w)}\b", q) for w in words):
            return agg
    return "sum"


def _detect_top_n(q: str) -> Optional[int]:
    m = re.search(r"\btop\s+(\d+)\b", q)
    if m:
        return int(m.group(1))
    if re.search(r"\btop\b", q):
        return 10  # bare "top products" defaults to 10
    return None


def _detect_sort_order(q: str) -> str:
    if re.search(r"\b(lowest|bottom|least|smallest)\b", q):
        return "asc"
    return "desc"


def _detect_time_grouping(q: str) -> Optional[str]:
    if re.search(r"\b(monthly|by month|per month)\b", q):
        return "month"
    if re.search(r"\b(yearly|by year|per year)\b", q):
        return "year"
    if re.search(r"\b(daily|by day|per day)\b", q):
        return "day"
    return None


def parse_question(question: str, columns: list[dict]) -> dict:
    """Parse a question into a structured query using dataset column metadata.

    columns: [{name, semantic_type, dtype}, ...] from the StandardDataset.
    Returns {query: dict, notes: [...]}.
    """
    q = (question or "").lower().strip()
    notes: list[str] = []

    def _norm(name: str) -> str:
        return name.lower().replace("_", " ").strip()

    measures = [c for c in columns if c.get("semantic_type") == "MEASURE"]
    dimensions = [c for c in columns
                  if c.get("semantic_type") in ("CATEGORY", "DIMENSION", "TEXT")]
    date_cols = [c for c in columns if c.get("semantic_type") == "DATE"]

    # ---------------- Metric detection ----------------
    metric: Optional[str] = None
    if re.search(r"\b(order_id|order id)\b", q) and ("total" in q or "count" in q or "how many" in q):
        metric = "__count__"
    else:
        for pattern, keywords in METRIC_KEYWORDS.items():
            if re.search(pattern, q):
                for kw in keywords:
                    for col in measures:
                        if kw in _norm(col["name"]):
                            metric = col["name"]
                            break
                    if metric:
                        break
                break
    if metric is None and re.search(COUNT_TRIGGER, q):
        metric = "__count__"
    if metric is None:
        # Generic fallback: main total/amount measure, else count rows
        for kw in ("total", "amount"):
            for col in measures:
                if kw in _norm(col["name"]):
                    metric = col["name"]
                    break
            if metric:
                break
        if metric is None and measures:
            metric = measures[-1]["name"]
            notes.append(f"No explicit metric found; using '{metric}'.")
        if metric is None:
            metric = "__count__"
            notes.append("No numeric metric found; falling back to COUNT of rows.")

    aggregation = _detect_aggregation(q, metric)

    # ---------------- Dimension / group-by detection ----------------
    group_by: list[str] = []
    time_grain = _detect_time_grouping(q)

    if time_grain:
        if date_cols:
            group_by = [date_cols[0]["name"]]
        else:
            notes.append("Time grouping requested but no DATE column found.")
    else:
        dim = None
        q_clean = re.sub(r"[?.!;,]+\s*$", "", q).strip()
        m = re.search(r"\bby\s+([a-z0-9_ ]+)$", q_clean)
        by_phrase = m.group(1).strip() if m else None

        # 1) "by X" phrase -> whole-phrase match, then word-level containment
        if by_phrase:
            for col in dimensions:
                if _norm(col["name"]) == by_phrase:
                    dim = col["name"]
                    break
            if dim is None:
                words = sorted(
                    [w for w in re.split(r"\s+", by_phrase)
                     if w and w not in ("the", "a", "an", "each")],
                    key=len, reverse=True,
                )
                for w in words:
                    if len(w) < 4:
                        continue
                    for col in dimensions:
                        n = _norm(col["name"])
                        if w in n or n in w:
                            dim = col["name"]
                            break
                    if dim:
                        break
            # explicit "by X" that we could not match: fall back to first category
            if dim is None:
                cats = [c for c in columns if c.get("semantic_type") == "CATEGORY"]
                if cats:
                    dim = cats[0]["name"]
                    notes.append(f"Could not match '{by_phrase}'; using '{dim}'.")

        # 2) "which X has ..." pattern
        if dim is None:
            m2 = re.search(r"\bwhich\s+([a-z0-9_ ]+?)\s+(?:has|have)\b", q)
            if m2:
                words = sorted([w for w in re.split(r"\s+", m2.group(1).strip()) if w],
                               key=len, reverse=True)
                for w in words:
                    if len(w) < 4:
                        continue
                    for col in dimensions:
                        n = _norm(col["name"])
                        if w in n or n in w:
                            dim = col["name"]
                            break
                    if dim:
                        break

        # 3) remaining nouns in the question (e.g. "top 10 products")
        if dim is None:
            cleaned = re.sub(r"[^a-z0-9_ ]", " ", q)
            words = [w for w in re.split(r"\s+", cleaned)
                     if w and len(w) >= 4 and w not in STOPWORDS]
            for w in words:
                for col in dimensions:
                    n = _norm(col["name"])
                    if w in n or n in w:
                        dim = col["name"]
                        break
                if dim:
                    break

        # No "by", no "which", no matching noun -> no grouping (KPI result)
        if dim:
            group_by = [dim]

    top_n = _detect_top_n(q)
    if top_n is None and re.search(r"\bwhich\b", q):
        top_n = 1  # "which city has the highest revenue" -> single answer

    query = AggregationQuery(
        dataset_id="",  # filled by caller
        operation="aggregate",
        group_by=group_by,
        metric=metric,
        aggregation=aggregation,
        filters=[],
        sort_by=group_by[0] if (time_grain and group_by) else None,
        sort_order="asc" if time_grain else _detect_sort_order(q),
        top_n=top_n,
    ).model_dump()
    return {"query": query, "notes": notes}
