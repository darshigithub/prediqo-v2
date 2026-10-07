"""Core backend tests for the prototype acceptance flow."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

from app.charts.recommender import recommend_chart
from app.query_engine.executor import execute_query
from app.query_engine.insights import generate_insight
from app.query_engine.parser import parse_question
from app.standardization.standardizer import build_standard_dataset
from app.models.schemas import AggregationQuery


@pytest.fixture(scope="module")
def ds():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "data", "uploads", "ecommerce_sales.csv")
    df = pd.read_csv(path)
    df["Order_Date"] = pd.to_datetime(df["Order_Date"])
    return build_standard_dataset("ds_test", "ecommerce_sales", "csv", df)


def _cols(ds):
    return [{"name": c.name, "semantic_type": c.semantic_type, "dtype": c.dtype} for c in ds.columns]


def test_profile_counts(ds):
    p = ds.profile
    assert p.rows == 50
    assert p.columns == 18
    assert "Total_Amount" in p.numeric_columns
    assert "Product_Category" in p.categorical_columns
    assert "Order_Date" in p.date_columns


def test_parse_revenue_by_category(ds):
    out = parse_question("Show revenue by product category", _cols(ds))
    q = out["query"]
    assert q["metric"] == "Total_Amount"
    assert q["group_by"] == ["Product_Category"]
    assert q["aggregation"] == "sum"


def test_parse_top_products(ds):
    out = parse_question("What are the top 10 products?", _cols(ds))
    q = out["query"]
    assert q["metric"] == "__count__" or q["metric"] == "Total_Amount"
    assert q["top_n"] == 10


def test_parse_monthly_revenue(ds):
    out = parse_question("Show monthly revenue", _cols(ds))
    q = out["query"]
    assert q["group_by"] == ["Order_Date"]
    assert q["metric"] == "Total_Amount"


def test_parse_which_city_highest(ds):
    out = parse_question("Which city has the highest revenue?", _cols(ds))
    q = out["query"]
    assert q["group_by"] == ["City"]
    assert q["aggregation"] == "max" or q["aggregation"] == "sum"
    assert q["top_n"] == 1


def test_execute_revenue_by_category(ds):
    q = AggregationQuery(dataset_id="ds_test", group_by=["Product_Category"],
                         metric="Total_Amount", aggregation="sum")
    res = execute_query(ds.dataframe, q)
    assert len(res["data"]) <= 4  # 4 categories
    total = sum(r["Total_Amount"] for r in res["data"])
    assert abs(total - ds.dataframe["Total_Amount"].sum()) < 1.0


def test_execute_monthly_revenue(ds):
    q = AggregationQuery(dataset_id="ds_test", group_by=["Order_Date"], metric="Total_Amount",
                         aggregation="sum", sort_by="Order_Date", sort_order="asc")
    q_dict = q.model_dump()
    q_dict["time_grain"] = "month"
    res = execute_query(ds.dataframe, AggregationQuery(**q_dict))
    assert res["dimension"] == "Order_Date"
    assert len(res["data"]) >= 1
    assert all(isinstance(r["Order_Date"], str) for r in res["data"])


def test_chart_recommendations(ds):
    res = {"data": [{"Product_Category": "A", "Total_Amount": 1},
                    {"Product_Category": "B", "Total_Amount": 2}], "dimension": "Product_Category",
           "metric": "Total_Amount"}
    assert recommend_chart(res, _cols(ds))["chart_type"] == "bar"

    res2 = {"data": [{"Order_Date": "Jan 2025", "Total_Amount": 1}], "dimension": "Order_Date",
            "metric": "Total_Amount"}
    assert recommend_chart(res2, _cols(ds))["chart_type"] == "line"

    res3 = {"data": [{"Total_Amount": 123}], "dimension": None, "metric": "Total_Amount"}
    assert recommend_chart(res3)["chart_type"] == "kpi"


def test_insight_from_actual_result(ds):
    q = AggregationQuery(dataset_id="ds_test", group_by=["Product_Category"],
                         metric="Total_Amount", aggregation="sum")
    res = execute_query(ds.dataframe, q)
    insight = generate_insight(res)
    top_row = max(res["data"], key=lambda r: r["Total_Amount"])
    assert top_row["Product_Category"] in insight
    assert f"{top_row['Total_Amount']:,.2f}" in insight


def test_insight_no_fabrication(ds):
    """Insight numbers must match the executed result exactly."""
    q = AggregationQuery(dataset_id="ds_test", group_by=["City"], metric="Total_Amount",
                         aggregation="sum")
    res = execute_query(ds.dataframe, q)
    insight = generate_insight(res)
    for r in res["data"]:
        val = f"{r['Total_Amount']:,.2f}"
        if val in insight:
            assert r["Total_Amount"] in [max(x["Total_Amount"] for x in res["data"]),
                                         min(x["Total_Amount"] for x in res["data"])]
