"""Suggestion engine: generates dataset-specific analytical questions based on semantic intelligence."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from ..models.dataset import ColumnMeta, StandardDataset
from .openai_client import openai_service
from .prompts import build_dataset_context

logger = logging.getLogger(__name__)


def generate_deterministic_suggestions(dataset: Any) -> list[str]:
    """Generates 6-10 useful analytical questions based strictly on semantic metadata and business roles.

    Enforces that IDs are counted rather than summed or averaged, avoiding invalid questions like
    'total order id' or 'monthly order id'.
    """
    if isinstance(dataset, dict):
        raw_cols = dataset.get("columns", [])
        columns = [
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
            for c in raw_cols
        ]
    else:
        columns = dataset.columns


    def friendly_name(name: str) -> str:
        clean = re.sub(r"[_\-]+", " ", name).strip()
        return clean.title()

    # Partition columns semantically
    id_cols = [c for c in columns if c.semantic_type == "ID" or getattr(c, "business_role", "").endswith("identifier")]
    order_id_col = next((c for c in id_cols if getattr(c, "business_role", "") == "order_identifier" or "order" in c.name.lower()), None)
    customer_id_col = next((c for c in id_cols if getattr(c, "business_role", "") == "customer_identifier" or any(k in c.name.lower() for k in ("customer", "user"))), None)

    date_cols = [c for c in columns if c.semantic_type == "DATE" or "date" in c.name.lower()]

    # True measures (exclude IDs and non-additive metrics)
    id_names = {c.name.lower() for c in id_cols}
    measures = [
        c for c in columns
        if c.semantic_type == "MEASURE" and c.name.lower() not in id_names
    ]

    # Business role specific columns
    rev_col = next(
        (c for c in measures if getattr(c, "business_role", "") == "revenue" or any(k in c.name.lower() for k in ("revenue", "sales", "total_amount", "amount"))),
        None
    )
    if not rev_col and measures:
        # Fallback to first non-rating, non-duration measure
        rev_col = next(
            (c for c in measures if getattr(c, "business_role", "") not in ("rating", "duration", "score")),
            measures[0] if measures else None
        )

    rating_col = next(
        (c for c in columns if getattr(c, "business_role", "") == "rating" or any(k in c.name.lower() for k in ("rating", "score"))),
        None
    )
    delivery_col = next(
        (c for c in columns if getattr(c, "business_role", "") == "duration" or any(k in c.name.lower() for k in ("delivery", "shipping", "transit"))),
        None
    )

    categories = [
        c for c in columns
        if c.semantic_type in ("CATEGORY", "DIMENSION") and c not in date_cols and c not in id_cols
    ]

    city_col = next(
        (c for c in columns if getattr(c, "business_role", "") == "geography" or any(k in c.name.lower() for k in ("city", "town", "location"))),
        None
    )
    product_cat_col = next(
        (c for c in columns if getattr(c, "business_role", "") == "category" or "category" in c.name.lower()),
        None
    )
    product_col = next(
        (c for c in columns if getattr(c, "business_role", "") == "product_name" or c.name.lower() in ("product", "product_name", "item")),
        None
    )
    status_col = next(
        (c for c in columns if getattr(c, "business_role", "") == "status" or "status" in c.name.lower()),
        None
    )

    suggestions: list[str] = []

    # 1. Primary Revenue / Metric KPI
    if rev_col:
        m_name = getattr(rev_col, "display_name", "") or friendly_name(rev_col.name)
        if "revenue" in m_name.lower():
            suggestions.append("What is the total revenue?")
        else:
            suggestions.append(f"What is the total {m_name.lower()}?")

    # 2. Category & Dimension Breakdown
    if product_cat_col and rev_col:
        cat_disp = getattr(product_cat_col, "display_name", "") or friendly_name(product_cat_col.name)
        m_disp = "revenue" if ("revenue" in rev_col.name.lower() or getattr(rev_col, "business_role", "") == "revenue") else friendly_name(rev_col.name).lower()
        suggestions.append(f"Which {cat_disp.lower()} generates the most {m_disp}?")
        suggestions.append(f"Show {m_disp} by {cat_disp.lower()}.")
    elif categories and rev_col:
        c_disp = getattr(categories[0], "display_name", "") or friendly_name(categories[0].name)
        m_disp = "revenue" if ("revenue" in rev_col.name.lower() or getattr(rev_col, "business_role", "") == "revenue") else friendly_name(rev_col.name).lower()
        suggestions.append(f"Show {m_disp} by {c_disp.lower()}.")

    # 3. Product Ranking
    if product_col and rev_col:
        m_disp = "revenue" if ("revenue" in rev_col.name.lower() or getattr(rev_col, "business_role", "") == "revenue") else friendly_name(rev_col.name).lower()
        suggestions.append(f"What are the top 5 products by {m_disp}?")
    elif product_col and measures:
        suggestions.append(f"What are the top 5 products by {friendly_name(measures[0].name).lower()}?")

    # 4. Order Volume & Count Questions (Correct analytical phrasing for IDs)
    if order_id_col:
        suggestions.append("How many orders are there?")
        if city_col:
            city_disp = getattr(city_col, "display_name", "") or friendly_name(city_col.name)
            suggestions.append(f"Which {city_disp.lower()} has the most orders?")
        if date_cols:
            suggestions.append("How do orders change over time?")
    elif customer_id_col:
        suggestions.append("How many customers are there?")
    elif id_cols:
        raw_name = id_cols[0].name.lower().replace("_id", "").replace("id", "") or "record"
        suggestions.append(f"How many {raw_name}s are there?")

    # 5. Date / Time Series Questions (Revenue / Sales trend)
    if date_cols and rev_col:
        m_disp = "revenue" if ("revenue" in rev_col.name.lower() or getattr(rev_col, "business_role", "") == "revenue") else friendly_name(rev_col.name).lower()
        suggestions.append(f"How does {m_disp} change over time?")
        suggestions.append(f"Show monthly {m_disp}.")

    # 6. Geography Ranking
    if city_col and rev_col:
        city_disp = getattr(city_col, "display_name", "") or friendly_name(city_col.name)
        m_disp = "revenue" if ("revenue" in rev_col.name.lower() or getattr(rev_col, "business_role", "") == "revenue") else friendly_name(rev_col.name).lower()
        suggestions.append(f"Which {city_disp.lower()} has the highest {m_disp}?")

    # 7. Delivery Duration Questions
    if delivery_col:
        suggestions.append("What is the average delivery time?")
        if city_col:
            city_disp = getattr(city_col, "display_name", "") or friendly_name(city_col.name)
            suggestions.append(f"Which {city_disp.lower()} has the longest delivery time?")

    # 8. Customer Rating Questions
    if rating_col:
        suggestions.append("What is the average customer rating?")
        if city_col:
            city_disp = getattr(city_col, "display_name", "") or friendly_name(city_col.name)
            suggestions.append(f"Which {city_disp.lower()} has the highest average customer rating?")

    # 9. Status Filter Questions
    if status_col and order_id_col:
        suggestions.append("How many orders are completed?")

    # Deduplicate while preserving priority order
    seen = set()
    unique_suggestions: list[str] = []
    for s in suggestions:
        s_norm = s.strip()
        # Filter out any lingering nonsensical identifier aggregations
        s_lower = s_norm.lower()
        if "total order id" in s_lower or "average order id" in s_lower or "monthly order id" in s_lower:
            continue
        if s_lower not in seen:
            seen.add(s_lower)
            unique_suggestions.append(s_norm)

    # Return between 6 and 10 questions
    return unique_suggestions[:8]


def get_dataset_suggestions(dataset: Any, use_ai: bool = True) -> list[str]:

    """Hybrid suggestion engine: blends schema-based deterministic suggestions with optional AI suggestions."""
    deterministic = generate_deterministic_suggestions(dataset)

    # For local/custom providers, use instant deterministic suggestions for speed
    active_provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    enable_ai_suggestions = os.environ.get("LLM_AI_SUGGESTIONS", "").strip().lower()

    if active_provider in ("custom", "ollama", "local", "vllm") and enable_ai_suggestions != "true":
        return deterministic

    if not use_ai or not openai_service.is_configured():
        return deterministic

    try:
        context = build_dataset_context(dataset)
        ai_suggestions = openai_service.generate_ai_suggestions(context)
        if not ai_suggestions:
            return deterministic

        # Merge suggestions, prioritizing top deterministic, then AI
        merged = []
        seen = set()

        for s in deterministic[:5]:
            if s.lower() not in seen:
                seen.add(s.lower())
                merged.append(s)

        for s in ai_suggestions:
            s_clean = s.strip()
            # Safety filter against bad identifier aggregations from LLM
            if "total order id" in s_clean.lower() or "average order id" in s_clean.lower():
                continue
            if s_clean.lower() not in seen:
                seen.add(s_clean.lower())
                merged.append(s_clean)

        for s in deterministic[5:]:
            if s.lower() not in seen and len(merged) < 8:
                seen.add(s.lower())
                merged.append(s)

        return merged[:8]
    except Exception as e:
        logger.info("AI suggestions skipped or timed out (%s), using instant schema suggestions.", e)
        return deterministic
