"""Dashboard persistence: one JSON file per dashboard in data/metadata.
Stores query specifications rather than huge result datasets for high performance.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..core.config import METADATA_DIR
from ..models.schemas import AddToDashboardPayload, ChartSpec, DashboardChart, DashboardConfig

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(dashboard_id: str) -> Path:
    return METADATA_DIR / f"dashboard_{dashboard_id}.json"


def populate_dashboard_charts(dash: DashboardConfig) -> DashboardConfig:
    """Refreshes chart data on demand from DuckDB / QueryCache using stored query specs."""
    from ..cache.query_cache import QueryCache, compute_query_hash
    from ..services.analyst import execute_chart_spec
    from ..storage.dataset_store import get_metadata

    for chart in dash.layout:
        if chart.spec and chart.dataset_id:
            try:
                meta = get_metadata(chart.dataset_id)
                version = meta.get("version", 1) if meta else 1
                q_hash = compute_query_hash(chart.dataset_id, version, chart.spec)
                cached = QueryCache.get(q_hash)
                if cached and "result" in cached and "data" in cached["result"]:
                    chart.data = cached["result"]["data"]
                else:
                    spec_fields = {k: v for k, v in chart.spec.items() if k in ChartSpec.model_fields}
                    spec_obj = ChartSpec(dataset_id=chart.dataset_id, **spec_fields)
                    res = execute_chart_spec(chart.dataset_id, spec_obj)
                    chart.data = res.get("result", {}).get("data", [])
                    QueryCache.set(
                        q_hash,
                        chart.dataset_id,
                        version,
                        res.get("result", {}),
                        chart={"type": chart.chart_type},
                        insight=chart.insight,
                    )
            except Exception as e:
                logger.debug("Could not refresh dashboard chart %s via DuckDB: %s", chart.id, e)
    return dash


def get_default_dashboard() -> DashboardConfig:
    existing = list_dashboards()
    if existing:
        return get_dashboard(existing[0]["id"])
    dash = DashboardConfig(
        id=f"dash_{uuid.uuid4().hex[:6]}",
        name="Default Dashboard",
        layout=[],
        created_at=_now(),
        updated_at=_now(),
    )
    save_dashboard(dash)
    return dash


def list_dashboards() -> list[dict]:
    out = []
    for f in sorted(METADATA_DIR.glob("dashboard_*.json")):
        try:
            d = json.loads(f.read_text())
            out.append({
                "id": d["id"],
                "name": d.get("name", "Dashboard"),
                "chart_count": len(d.get("layout", [])),
                "updated_at": d.get("updated_at"),
            })
        except Exception:
            continue
    return out


def get_dashboard(dashboard_id: str) -> DashboardConfig:
    f = _path(dashboard_id)
    if not f.exists():
        raise KeyError(f"Dashboard not found: {dashboard_id}")
    dash = DashboardConfig(**json.loads(f.read_text()))
    return populate_dashboard_charts(dash)


def save_dashboard(dash: DashboardConfig) -> DashboardConfig:
    dash.updated_at = _now()
    _path(dash.id).write_text(dash.model_dump_json(indent=2))
    return dash


def add_chart(dashboard_id: str, payload: AddToDashboardPayload) -> DashboardConfig:
    dash = get_dashboard(dashboard_id)
    spec_dict = payload.chart_spec.model_dump() if payload.chart_spec else {}
    chart_type = payload.chart_type or spec_dict.get("type") or "bar"
    title = (payload.question or spec_dict.get("title") or f"{chart_type.capitalize()} chart")

    # Store query spec and at most small fallback rows (do not store millions of rows in JSON)
    preview_data = (payload.result or [])[:50]

    chart = DashboardChart(
        id=f"ch_{uuid.uuid4().hex[:6]}",
        title=title,
        chart_type=chart_type,
        dataset_id=payload.dataset_id,
        question=payload.question,
        spec=spec_dict,
        data=preview_data,
        insight=payload.insight,
    )
    dash.layout.append(chart)
    return save_dashboard(dash)


def remove_chart(dashboard_id: str, chart_id: str) -> DashboardConfig:
    dash = get_dashboard(dashboard_id)
    dash.layout = [c for c in dash.layout if c.id != chart_id]
    return save_dashboard(dash)


def update_chart_position(dashboard_id: str, chart_id: str, direction: str) -> DashboardConfig:
    """Simple arrange: move a chart left/up ('prev') or right/down ('next')."""
    dash = get_dashboard(dashboard_id)
    ids = [c.id for c in dash.layout]
    if chart_id not in ids:
        raise KeyError("chart not found")
    i = ids.index(chart_id)
    j = i - 1 if direction == "prev" else i + 1
    if 0 <= j < len(dash.layout):
        dash.layout[i], dash.layout[j] = dash.layout[j], dash.layout[i]
    return save_dashboard(dash)
