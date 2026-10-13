"""Semantic intelligence module: business role inference, aggregation rules, and metric discovery."""
from __future__ import annotations

import re
from typing import Any, Optional
import pandas as pd


# ---------- Business Roles and Recognition Rules ----------

# Priority keyword mapping for column names -> business roles
_ROLE_PATTERNS = [
    # Identifiers
    (r"\b(order_id|order_number|order_no|order_code|order_key|orderid|invoice_number|invoice_no)\b", "order_identifier"),
    (r"\b(customer_id|user_id|client_id|account_id|buyer_id|customerid|userid)\b", "customer_identifier"),
    (r"\b(product_id|item_id|sku|asin|barcode|productid|itemid)\b", "product_identifier"),
    (r"\b(transaction_id|txn_id|invoice_id|payment_id)\b", "transaction_identifier"),
    (r"\b(id|uuid|guid|code|key)\b", "identifier"),

    # Monetary / Revenue / Cost / Profit
    (r"\b(total_amount|gross_revenue|net_revenue|revenue|sales|total_sales|turnover|gmv|sales_amount|net_sales|daily_revenue|gross_sales)\b", "revenue"),
    (r"\b(cost|cogs|expense|expenses|spending|spend|purchase_cost)\b", "cost"),
    (r"\b(profit|net_profit|gross_profit|margin|net_income|earnings)\b", "profit"),
    (r"\b(amount|total|charge|fee|balance|tax|vat)\b", "monetary_amount"),
    (r"\b(unit_price|price_per_unit)\b", "unit_price"),
    (r"\b(price|mrp|list_price|selling_price|discounted_price)\b", "price"),
    (r"\b(discount|discount_amount|discount_value|discount_percentage|discount_pct)\b", "discount"),

    # Quantities & Counts
    (r"\b(quantity|qty|units|units_sold|volume|count|stock|inventory)\b", "quantity"),

    # Durations & Time Spans
    (r"\b(delivery_days|delivery_time|shipping_days|transit_days|lead_time|duration|tenure|wait_time|response_time|latency)\b", "duration"),

    # Ratings & Scores
    (r"\b(customer_rating|user_rating|product_rating|rating|score|stars|review_score|satisfaction|nps)\b", "rating"),
    (r"\b(percentage|percent|pct|rate|ratio|conversion_rate)\b", "rate"),

    # Dates & Timestamps
    (r"\b(order_date|transaction_date|purchase_date|booking_date|purchased_on|sale_date|invoice_date|event_date)\b", "transaction_date"),
    (r"\b(delivery_date|ship_date|shipping_date|dispatch_date)\b", "delivery_date"),
    (r"\b(created_at|created_date|signup_date|registration_date)\b", "creation_date"),
    (r"\b(updated_at|modified_at)\b", "modification_date"),

    # Dimensions: Geography
    (r"\b(city|town|municipality)\b", "geography"),
    (r"\b(country|nation)\b", "geography"),
    (r"\b(state|province|region|territory|zone)\b", "geography"),
    (r"\b(postal_code|zip_code|zipcode|pincode)\b", "geography"),

    # Dimensions: Categorization
    (r"\b(product_category|category|department|genre|division|segment)\b", "category"),
    (r"\b(product_name|product|item_name|item|title)\b", "product_name"),
    (r"\b(customer_name|client_name|user_name|full_name|name)\b", "person_name"),
    (r"\b(order_status|payment_status|delivery_status|status|state_code)\b", "status"),
    (r"\b(payment_method|payment_mode|payment_type)\b", "payment_method"),
    (r"\b(channel|source|traffic_source|medium|campaign)\b", "channel"),
]


def infer_business_role(
    name: str,
    series: Optional[pd.Series] = None,
    dtype: str = "",
    semantic_type: str = "",
    unique_count: int = 0,
    rows: int = 0,
) -> str:
    """Deterministically infers the business role for a column using name, type, and distribution."""
    col_clean = re.sub(r"[_\s\-]+", " ", name.lower()).strip()
    col_norm = name.lower().strip()

    # 1. First, check identifier heuristics
    if semantic_type == "ID":
        if any(k in col_norm for k in ("order", "booking")):
            return "order_identifier"
        if any(k in col_norm for k in ("customer", "user", "client", "buyer")):
            return "customer_identifier"
        if any(k in col_norm for k in ("product", "item", "sku")):
            return "product_identifier"
        return "identifier"

    # 2. Check regex pattern list
    for pattern, role in _ROLE_PATTERNS:
        if re.search(pattern, col_norm) or re.search(pattern, col_clean):
            # Verify role plausibility against semantic type
            if role in ("revenue", "cost", "profit", "monetary_amount", "quantity", "unit_price", "price", "duration", "rating", "rate"):
                if semantic_type == "MEASURE" or "int" in dtype or "float" in dtype:
                    return role
            elif role in ("transaction_date", "delivery_date", "creation_date", "modification_date"):
                if semantic_type == "DATE" or "date" in dtype or "time" in dtype:
                    return role
            elif role in ("geography", "category", "product_name", "person_name", "status", "payment_method", "channel"):
                return role
            elif "identifier" in role:
                return role

    # 3. Fallbacks based on semantic type and name signals
    if semantic_type == "DATE":
        return "date"

    if semantic_type == "MEASURE":
        if any(k in col_norm for k in ("amount", "rev", "sale", "val")):
            return "monetary_amount"
        if any(k in col_norm for k in ("qty", "cnt", "num")):
            return "quantity"
        if any(k in col_norm for k in ("day", "hour", "sec", "min", "time")):
            return "duration"
        if any(k in col_norm for k in ("rate", "pct")):
            return "rate"
        return "measure"

    if semantic_type in ("CATEGORY", "DIMENSION"):
        if any(k in col_norm for k in ("city", "country", "state", "region", "zip")):
            return "geography"
        if any(k in col_norm for k in ("cat", "dept", "group", "type")):
            return "category"
        if any(k in col_norm for k in ("status", "state", "flag")):
            return "status"
        return "dimension"

    if semantic_type == "TEXT":
        return "free_text"

    return "unknown"


def get_display_name(name: str, business_role: str = "") -> str:
    """Formats a clean human-readable display name from column name and business role."""
    # Special well-known overrides
    overrides = {
        "order_id": "Order ID",
        "customer_id": "Customer ID",
        "product_id": "Product ID",
        "user_id": "User ID",
        "total_amount": "Total Revenue" if business_role == "revenue" else "Total Amount",
        "customer_rating": "Customer Rating",
        "delivery_days": "Delivery Time (Days)",
        "order_date": "Order Date",
        "product_category": "Product Category",
        "payment_method": "Payment Method",
    }
    if name.lower() in overrides:
        return overrides[name.lower()]

    # Clean words and capitalize
    words = re.sub(r"[_\-]+", " ", name).split()
    capitalized = []
    for w in words:
        if w.lower() in ("id", "sku", "url", "kpi", "api", "vat", "gst", "cogs", "gmv"):
            capitalized.append(w.upper())
        else:
            capitalized.append(w.capitalize())
    return " ".join(capitalized)


def get_allowed_aggregations(semantic_type: str, business_role: str = "", dtype: str = "") -> list[str]:
    """Central policy returning allowed SQL aggregations for a column."""
    sem = (semantic_type or "").upper()
    role = (business_role or "").lower()

    if sem == "ID":
        # IDs must NEVER be summed or averaged
        return ["COUNT", "DISTINCT_COUNT"]

    if sem in ("CATEGORY", "DIMENSION", "TEXT"):
        # Categorical text fields only allow counting
        return ["COUNT", "DISTINCT_COUNT"]

    if sem == "DATE":
        # Dates support counts and chronological extrema
        return ["COUNT", "DISTINCT_COUNT", "MIN", "MAX"]

    if sem == "MEASURE":
        if role in ("rating", "score"):
            # Ratings are averaged or evaluated for min/max; summing ratings is nonsensical
            return ["AVG", "MIN", "MAX", "COUNT", "DISTINCT_COUNT"]
        if role in ("duration", "latency", "unit_price", "rate", "discount"):
            # Durations and rates are primarily averaged
            return ["AVG", "MIN", "MAX", "COUNT", "DISTINCT_COUNT"]
        if role in ("revenue", "cost", "profit", "monetary_amount", "quantity"):
            # Additive measures fully support sum, avg, min, max
            return ["SUM", "AVG", "MIN", "MAX", "COUNT", "DISTINCT_COUNT"]
        # Default numeric measure
        return ["SUM", "AVG", "MIN", "MAX", "COUNT", "DISTINCT_COUNT"]

    return ["COUNT", "DISTINCT_COUNT"]


def discover_derived_metrics(columns: list[Any]) -> list[dict[str, Any]]:
    """Discovers high-value analytical metrics from available dataset columns.

    Each metric points to a real existing column in the dataset.
    """
    derived: list[dict[str, Any]] = []
    col_map = {c.name.lower(): c for c in columns}

    # 1. Order Volume Metric
    order_col = next((c for c in columns if getattr(c, "business_role", "") == "order_identifier" or (c.semantic_type == "ID" and "order" in c.name.lower())), None)
    if order_col:
        derived.append({
            "name": "total_orders",
            "display_name": "Total Orders",
            "column": order_col.name,
            "aggregation": "COUNT",
            "business_role": "order_count",
            "description": f"Total volume of orders counted via {order_col.name}",
        })

    # 2. Customer Base Metric
    cust_col = next((c for c in columns if getattr(c, "business_role", "") == "customer_identifier" or (c.semantic_type == "ID" and any(k in c.name.lower() for k in ("customer", "user")))), None)
    if cust_col:
        derived.append({
            "name": "total_customers",
            "display_name": "Total Customers",
            "column": cust_col.name,
            "aggregation": "DISTINCT_COUNT",
            "business_role": "customer_count",
            "description": f"Distinct count of unique customers ({cust_col.name})",
        })

    # 3. Revenue / Monetary Metric
    rev_col = next((c for c in columns if getattr(c, "business_role", "") == "revenue" or (c.semantic_type == "MEASURE" and any(k in c.name.lower() for k in ("revenue", "sales", "total_amount")))), None)
    if rev_col:
        derived.append({
            "name": "total_revenue",
            "display_name": "Total Revenue",
            "column": rev_col.name,
            "aggregation": "SUM",
            "business_role": "revenue",
            "description": f"Total revenue generated from {rev_col.name}",
        })
        derived.append({
            "name": "average_order_value",
            "display_name": "Average Order Value",
            "column": rev_col.name,
            "aggregation": "AVG",
            "business_role": "average_revenue",
            "description": f"Mean monetary value per order from {rev_col.name}",
        })

    # 4. Units / Quantity Metric
    qty_col = next((c for c in columns if getattr(c, "business_role", "") == "quantity" or (c.semantic_type == "MEASURE" and any(k in c.name.lower() for k in ("quantity", "units", "qty")))), None)
    if qty_col:
        derived.append({
            "name": "units_sold",
            "display_name": "Units Sold",
            "column": qty_col.name,
            "aggregation": "SUM",
            "business_role": "quantity",
            "description": f"Total units sold from {qty_col.name}",
        })

    # 5. Delivery Time Metric
    delivery_col = next((c for c in columns if getattr(c, "business_role", "") == "duration" or (c.semantic_type == "MEASURE" and any(k in c.name.lower() for k in ("delivery", "shipping")))), None)
    if delivery_col:
        disp = getattr(delivery_col, "display_name", delivery_col.name)
        derived.append({
            "name": "avg_delivery_time",
            "display_name": "Average Delivery Time",
            "column": delivery_col.name,
            "aggregation": "AVG",
            "business_role": "duration",
            "description": f"Mean delivery duration in days from {delivery_col.name}",
        })

    # 6. Customer Rating Metric
    rating_col = next((c for c in columns if getattr(c, "business_role", "") == "rating" or (c.semantic_type == "MEASURE" and any(k in c.name.lower() for k in ("rating", "score")))), None)
    if rating_col:
        derived.append({
            "name": "avg_customer_rating",
            "display_name": "Average Customer Rating",
            "column": rating_col.name,
            "aggregation": "AVG",
            "business_role": "rating",
            "description": f"Average customer rating from {rating_col.name}",
        })

    # 7. Cost Metric
    cost_col = next((c for c in columns if getattr(c, "business_role", "") == "cost" or (c.semantic_type == "MEASURE" and "cost" in c.name.lower())), None)
    if cost_col:
        derived.append({
            "name": "total_cost",
            "display_name": "Total Cost",
            "column": cost_col.name,
            "aggregation": "SUM",
            "business_role": "cost",
            "description": f"Total cost from {cost_col.name}",
        })

    return derived


def get_semantic_model(dataset: Any) -> dict[str, Any]:
    """Builds a comprehensive semantic model dictionary for a dataset."""
    columns = dataset.columns
    derived_metrics = discover_derived_metrics(columns)

    dimensions = [c.name for c in columns if c.semantic_type in ("DIMENSION", "CATEGORY")]
    measures = [c.name for c in columns if c.semantic_type == "MEASURE"]
    date_fields = [c.name for c in columns if c.semantic_type == "DATE"]
    identifiers = [c.name for c in columns if c.semantic_type == "ID"]
    categories = [c.name for c in columns if c.semantic_type == "CATEGORY"]

    col_meta_list = []
    for c in columns:
        col_meta_list.append({
            "name": c.name,
            "dtype": c.dtype,
            "semantic_type": c.semantic_type,
            "business_role": getattr(c, "business_role", "unknown"),
            "display_name": getattr(c, "display_name", c.name),
            "allowed_aggregations": getattr(c, "allowed_aggregations", []),
            "unique_count": c.unique_count,
            "null_count": c.null_count,
            "min": c.min,
            "max": c.max,
            "avg": c.avg,
            "top_values": c.top_values,
        })

    return {
        "dataset_id": dataset.dataset_id,
        "dataset_name": dataset.dataset_name,
        "columns": col_meta_list,
        "dimensions": dimensions,
        "measures": measures,
        "date_fields": date_fields,
        "identifiers": identifiers,
        "categories": categories,
        "derived_metrics": derived_metrics,
    }
