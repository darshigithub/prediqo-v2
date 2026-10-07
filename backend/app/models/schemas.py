"""Pydantic request/response schemas for the prototype API."""
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------- Connect ----------
class GoogleSheetsConfig(BaseModel):
    sheet_id: str = Field(..., description="Google Sheets document ID from its URL")
    sheet_name: Optional[str] = None
    gid: Optional[int] = None


class PostgresConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str
    user: str
    password: str = ""
    table: str


class DatasetRef(BaseModel):
    dataset_id: str


class AggregationQuery(BaseModel):
    dataset_id: str
    operation: str = "aggregate"
    group_by: list[str] = []
    metric: str
    aggregation: str = "sum"
    filters: list[dict[str, Any]] = []
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    top_n: Optional[int] = None


# ---------- AI Analyst ----------
class AIAnalyzeRequest(BaseModel):
    dataset_id: str
    question: str
    conversation_id: Optional[str] = None
    allow_fallback: Optional[bool] = None
    provider: Optional[str] = None
    model: Optional[str] = None


# ---------- Charts ----------
class ChartSpec(BaseModel):
    dataset_id: str
    type: str = "bar"                 # bar|line|pie|area|scatter|kpi|table
    dimension: Optional[str] = None
    metric: Optional[str] = None
    aggregation: str = "sum"
    filters: list[dict[str, Any]] = []
    sort: str = "desc"
    top_n: Optional[int] = None
    title: Optional[str] = None


class AddToDashboardPayload(BaseModel):
    dataset_id: str
    question: Optional[str] = None
    chart_spec: Optional[ChartSpec] = None
    result: Optional[list[dict[str, Any]]] = None
    chart_type: Optional[str] = None
    recommendation: Optional[dict[str, Any]] = None
    insight: Optional[str] = None


class DashboardChart(BaseModel):
    id: str
    title: str
    chart_type: str
    dataset_id: Optional[str] = None
    question: Optional[str] = None
    spec: dict[str, Any]
    data: list[dict[str, Any]] = []
    insight: Optional[str] = None


class DashboardConfig(BaseModel):
    id: str
    name: str = "Default Dashboard"
    layout: list[DashboardChart] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
