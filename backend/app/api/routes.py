"""All API routes for the prototype."""
import math
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ..connectors.registry import available_connectors, fetch_via_connector
from ..core.config import UPLOADS_DIR
from ..ingestion.models import IngestionRequest, IngestionResponse
from ..ingestion.service import refresh_dataset, start_ingestion_job
from ..jobs.job_manager import JobManager
from ..jobs.job_models import IngestionJob, JobStatus
from ..models.schemas import (
    AddToDashboardPayload,
    AIAnalyzeRequest,
    ChartSpec,
    DashboardConfig,
    GoogleSheetsConfig,
    PostgresConfig,
)
from ..prediction.models import PredictRequest, TrainRequest
from ..ai.analyst import process_question
from ..ai.llm_client import list_available_providers
from ..ai.openai_client import OpenAIConfigError, OpenAIServiceError
from ..ai.query_validator import QueryValidationError
from ..ai.suggestion_engine import get_dataset_suggestions
from ..services.analyst import answer_question, execute_chart_spec
from ..standardization.semantics import get_semantic_model
from ..storage.dashboard_store import (
    add_chart,
    get_dashboard,
    get_default_dashboard,
    list_dashboards,
    remove_chart,
    save_dashboard,
    update_chart_position,
)
from ..storage.dataset_store import (
    create_dataset,
    delete_dataset,
    get_dataset,
    get_metadata,
    get_parquet_path,
    list_datasets,
)

router = APIRouter(prefix="/api")


# ---------- Health ----------
@router.get("/health")
def health():
    return {"status": "ok", "service": "ai-analytics-prototype"}


# ---------- Ingestion Jobs ----------
@router.post("/ingestion/jobs")
async def create_ingestion_job(
    request: Optional[IngestionRequest] = None,
    file: Optional[UploadFile] = File(None),
):
    """Creates and starts an asynchronous ingestion job for CSV, Excel, or configured connector."""
    if file:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in (".csv", ".xlsx", ".xls"):
            raise HTTPException(400, "Only .csv and .xlsx/.xls files are supported")
        dest = UPLOADS_DIR / file.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        source_type = "csv" if ext == ".csv" else "excel"
        job = start_ingestion_job(
            source_type=source_type,
            dataset_name=Path(file.filename).stem,
            source_config={"path": str(dest)},
        )
        return job.model_dump()

    if not request:
        raise HTTPException(400, "Either a file or ingestion request payload is required")

    job = start_ingestion_job(
        source_type=request.source_type,
        dataset_name=request.dataset_name,
        source_config=request.source_config,
    )
    return job.model_dump()


@router.get("/ingestion/jobs/{job_id}")
def get_ingestion_job(job_id: str):
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job.model_dump()


@router.get("/ingestion/jobs")
def list_ingestion_jobs(limit: int = 50):
    jobs = JobManager.list_jobs(limit=limit)
    return {"jobs": [j.model_dump() for j in jobs]}


@router.post("/datasets/{dataset_id}/refresh")
def refresh_dataset_route(dataset_id: str):
    """Safely refreshes a dataset into version N+1 while version N remains queryable."""
    try:
        job = refresh_dataset(dataset_id)
        return job.model_dump()
    except KeyError:
        raise HTTPException(404, "Dataset not found")
    except Exception as e:
        raise HTTPException(400, str(e))


# ---------- Connectors ----------
@router.get("/connectors")
def connectors():
    return {"connectors": available_connectors()}


@router.post("/connect/csv")
async def connect_csv(file: UploadFile = File(...), async_job: bool = Query(False)):
    ext = Path(file.filename or "").suffix.lower()
    if ext != ".csv":
        raise HTTPException(400, "Only .csv files are accepted here (use /connect/excel for Excel)")
    dest = UPLOADS_DIR / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    if async_job:
        job = start_ingestion_job("csv", Path(file.filename).stem, {"path": str(dest)})
        return job.model_dump()

    try:
        df = pd.read_csv(dest)
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")
    if df.empty:
        raise HTTPException(400, "CSV has no data rows")
    ds = create_dataset("csv", Path(file.filename).stem, df, {"path": str(dest)})
    return _dataset_summary(ds)


@router.post("/connect/excel")
async def connect_excel(file: UploadFile = File(...), async_job: bool = Query(False)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".xlsx", ".xls"):
        raise HTTPException(400, "Only .xlsx/.xls files are accepted")
    dest = UPLOADS_DIR / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    if async_job:
        job = start_ingestion_job("excel", Path(file.filename).stem, {"path": str(dest)})
        return job.model_dump()

    try:
        df = pd.read_excel(dest, sheet_name=0)
    except Exception as e:
        raise HTTPException(400, f"Could not parse Excel: {e}")
    if df.empty:
        raise HTTPException(400, "Excel sheet has no data rows")
    ds = create_dataset("excel", Path(file.filename).stem, df, {"path": str(dest)})
    return _dataset_summary(ds)


@router.post("/connect/google-sheets")
def connect_google_sheets(config: GoogleSheetsConfig, async_job: bool = Query(False)):
    name = config.sheet_name or f"sheet_{config.sheet_id[:8]}"
    if async_job:
        job = start_ingestion_job("google_sheets", name, config.model_dump())
        return job.model_dump()

    try:
        df = fetch_via_connector("google_sheets", config.model_dump(), dataset="")
    except Exception as e:
        raise HTTPException(400, f"Google Sheets connection failed: {e}")
    ds = create_dataset("google_sheets", name, df, config.model_dump())
    return _dataset_summary(ds)


@router.post("/connect/postgresql")
def connect_postgresql(config: PostgresConfig, async_job: bool = Query(False)):
    if async_job:
        job = start_ingestion_job("postgresql", config.table, config.model_dump())
        return job.model_dump()

    try:
        df = fetch_via_connector("postgresql", config.model_dump(), dataset=config.table)
    except Exception as e:
        raise HTTPException(400, f"PostgreSQL connection failed: {e}")
    ds = create_dataset("postgresql", config.table, df, config.model_dump())
    return _dataset_summary(ds)


def _dataset_summary(ds) -> dict:
    return {
        "dataset_id": ds.dataset_id,
        "dataset_name": ds.dataset_name,
        "source_type": ds.source_type,
        "rows": ds.profile.rows,
        "columns": ds.profile.columns,
        "created_at": ds.created_at,
        "version": getattr(ds, "version", 1),
        "status": getattr(ds, "status", "READY"),
    }


# ---------- Datasets ----------
@router.get("/datasets")
def datasets():
    return {"datasets": list_datasets()}


@router.get("/datasets/{dataset_id}")
def dataset_detail(dataset_id: str):
    meta = get_metadata(dataset_id)
    if not meta:
        raise HTTPException(404, "Dataset not found")
    return meta


@router.get("/datasets/{dataset_id}/preview")
def dataset_preview(
    dataset_id: str,
    page: int = 1,
    page_size: int = 50,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    search: Optional[str] = None,
    filter_col: Optional[str] = None,
    filter_val: Optional[str] = None,
):
    """Server-side paginated, sorted, and filtered preview querying Parquet directly via DuckDB."""
    parquet_path = get_parquet_path(dataset_id)

    # Effective limit and offset
    if limit is not None:
        eff_limit = limit
        eff_offset = offset or 0
    else:
        eff_limit = max(1, page_size)
        eff_offset = max(0, (page - 1) * page_size)

    if parquet_path and parquet_path.exists():
        import duckdb
        con = duckdb.connect()
        try:
            p_str = str(parquet_path).replace("\\", "/")
            con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{p_str}')")
            desc = con.query("DESCRIBE t").fetchall()
            col_names = [r[0] for r in desc]

            where_clauses = []
            if search:
                search_sub = []
                val_q = "'" + search.replace("'", "''") + "'"
                for c, t in desc:
                    if any(s in str(t).lower() for s in ("varchar", "text", "string")):
                        c_safe = str(c).replace('"', '""')
                        search_sub.append(f'contains(lower(CAST("{c_safe}" AS VARCHAR)), lower({val_q}))')
                if search_sub:
                    where_clauses.append("(" + " OR ".join(search_sub) + ")")

            if filter_col and filter_val is not None and filter_col in col_names:
                fc_safe = str(filter_col).replace('"', '""')
                fv_q = "'" + str(filter_val).replace("'", "''") + "'"
                where_clauses.append(f'contains(lower(CAST("{fc_safe}" AS VARCHAR)), lower({fv_q}))')

            where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # Count total matching rows
            total_rows = con.query(f"SELECT COUNT(*) FROM t{where_sql}").fetchone()[0]

            order_sql = ""
            if sort_by and sort_by in col_names:
                direction = "DESC" if sort_order.lower() == "desc" else "ASC"
                sb_safe = str(sort_by).replace('"', '""')
                order_sql = f' ORDER BY "{sb_safe}" {direction}'

            data_sql = f"SELECT * FROM t{where_sql}{order_sql} LIMIT {eff_limit} OFFSET {eff_offset}"

            out_df = con.query(data_sql).df()

            def _cell(v):
                if pd.isna(v):
                    return None
                if hasattr(v, "isoformat"):
                    return str(v)[:10]
                return v.item() if hasattr(v, "item") else v

            rows = [{c: _cell(v) for c, v in zip(out_df.columns, row)} for row in out_df.itertuples(index=False)]
            total_pages = math.ceil(total_rows / eff_limit) if eff_limit > 0 else 1

            return {
                "dataset_id": dataset_id,
                "page": page,
                "page_size": eff_limit,
                "total_rows": total_rows,
                "total_pages": total_pages,
                "columns": list(out_df.columns),
                "rows": rows,
            }
        finally:
            con.close()

    # Fallback to in-memory DataFrame
    ds = get_dataset(dataset_id)
    if ds is None:
        raise HTTPException(404, "Dataset not found")
    df = ds.dataframe
    total_rows = len(df)
    d = df.iloc[eff_offset:eff_offset + eff_limit]

    def _cell(v):
        if pd.isna(v):
            return None
        if hasattr(v, "isoformat"):
            return str(v)[:10]
        return v.item() if hasattr(v, "item") else v

    rows = [{c: _cell(v) for c, v in zip(d.columns, row)} for row in d.itertuples(index=False)]
    return {
        "dataset_id": dataset_id,
        "page": page,
        "page_size": eff_limit,
        "total_rows": total_rows,
        "total_pages": math.ceil(total_rows / eff_limit) if eff_limit > 0 else 1,
        "columns": list(df.columns),
        "rows": rows,
    }


@router.get("/datasets/{dataset_id}/profile")
def dataset_profile(dataset_id: str):
    meta = get_metadata(dataset_id)
    if not meta:
        raise HTTPException(404, "Dataset not found")
    return {"dataset_id": dataset_id, "profile": meta["profile"]}


@router.get("/datasets/{dataset_id}/schema")
def dataset_schema(dataset_id: str):
    meta = get_metadata(dataset_id)
    if not meta:
        raise HTTPException(404, "Dataset not found")
    return {"dataset_id": dataset_id, "columns": meta["columns"]}


@router.get("/datasets/{dataset_id}/semantic-model")
def dataset_semantic_model(dataset_id: str):
    """Returns business semantic model from stored metadata without reloading dataset."""
    meta = get_metadata(dataset_id)
    if meta and meta.get("semantic_model"):
        return meta["semantic_model"]
    ds = get_dataset(dataset_id)
    if ds is None:
        raise HTTPException(404, "Dataset not found")
    return get_semantic_model(ds)


@router.delete("/datasets/{dataset_id}")
def dataset_delete(dataset_id: str):
    if not delete_dataset(dataset_id):
        raise HTTPException(404, "Dataset not found")
    return {"deleted": dataset_id}


# ---------- Query / Analyst ----------
@router.post("/query")
def run_query(payload: dict):
    """NL question (question=...) or a structured query."""
    ds_id = payload.get("dataset_id")
    meta = get_metadata(ds_id)
    if not meta and not get_dataset(ds_id):
        raise HTTPException(404, "Dataset not found")

    if payload.get("question"):
        return answer_question(ds_id, payload["question"])

    from ..models.schemas import AggregationQuery
    from ..query_engine.executor import execute_query
    from ..charts.recommender import recommend_chart
    from ..query_engine.insights import generate_insight

    q = AggregationQuery(**{k: v for k, v in payload.items() if k in AggregationQuery.model_fields})
    parquet_path = get_parquet_path(ds_id)
    source = parquet_path if (parquet_path and parquet_path.exists()) else get_dataset(ds_id).dataframe
    res = execute_query(source, q)

    schema = meta.get("columns", []) if meta else [{"name": c.name, "semantic_type": c.semantic_type} for c in get_dataset(ds_id).columns]
    rec = recommend_chart(res, schema)
    return {
        "question": None,
        "query": q.model_dump(),
        "result": res,
        "chart_type": rec["chart_type"],
        "chart_reason": rec["reason"],
        "insight": generate_insight(res),
        "parser_used": "structured",
    }


@router.post("/chart")
def run_chart(spec: ChartSpec):
    """Chart Builder: execute a manual chart spec."""
    try:
        return execute_chart_spec(spec.dataset_id, spec)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- NLP AI Analyst ----------
@router.get("/ai/providers")
def ai_providers():
    """Lists available LLM providers (OpenAI, Groq, Gemini, Anthropic, Custom) and their setup status."""
    import os
    providers = list_available_providers()
    active = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if not active:
        active = next((p["id"] for p in providers if p["configured"]), "openai")
    return {"providers": providers, "active_provider": active}


@router.post("/ai/analyze")
def ai_analyze(payload: AIAnalyzeRequest):
    """NLP AI Analyst endpoint: translates questions into safe validated analytical queries."""
    meta = get_metadata(payload.dataset_id)
    if not meta and not get_dataset(payload.dataset_id):
        raise HTTPException(404, "Dataset not found")

    if meta and meta.get("status") == "PROCESSING":
        raise HTTPException(400, "Dataset is currently processing. Please wait until status is READY.")
    if meta and meta.get("status") == "FAILED":
        raise HTTPException(400, f"Dataset ingestion failed: {meta.get('error')}")

    try:
        return process_question(
            dataset_id=payload.dataset_id,
            question=payload.question,
            conversation_id=payload.conversation_id,
            allow_fallback=payload.allow_fallback if payload.allow_fallback is not None else False,
            provider=payload.provider,
            model=payload.model,
        )
    except OpenAIConfigError as e:
        raise HTTPException(400, str(e) or "OpenAI API key is not configured.")
    except OpenAIServiceError as e:
        raise HTTPException(503, str(e) or "AI service is currently unavailable.")
    except QueryValidationError as e:
        err_msg = str(e)
        if "does not contain" in err_msg:
            raise HTTPException(400, "The dataset does not contain a field that can answer this question.")
        raise HTTPException(400, f"Query validation failed: {err_msg}")
    except ValueError as e:
        err_msg = str(e)
        if "cannot be empty" in err_msg or "cannot be understood" in err_msg:
            raise HTTPException(400, "I couldn't determine which analysis you want.\nTry asking something like:\n\"Show revenue by city.\"")
        raise HTTPException(400, err_msg)
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")


@router.get("/ai/suggestions/{dataset_id}")
def ai_suggestions(dataset_id: str, provider: Optional[str] = None):
    """Returns dataset-specific question suggestions based on actual schema metadata."""
    meta = get_metadata(dataset_id)
    if meta and meta.get("columns"):
        suggestions = get_dataset_suggestions(meta)
        return {"suggestions": suggestions}

    ds = get_dataset(dataset_id)
    if ds is None:
        raise HTTPException(404, "Dataset not found")
    suggestions = get_dataset_suggestions(ds)
    return {"suggestions": suggestions}


# ---------- Dashboards ----------
@router.get("/dashboards")
def dashboards():
    return {"dashboards": list_dashboards()}


@router.post("/dashboards")
def create_dashboard(payload: dict):
    from datetime import datetime, timezone
    dash = DashboardConfig(
        id=f"dash_{uuid.uuid4().hex[:6]}",
        name=payload.get("name", "Dashboard"),
        layout=[],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    save_dashboard(dash)
    return dash


@router.get("/dashboards/{dashboard_id}")
def dashboard_detail(dashboard_id: str):
    try:
        return get_dashboard(dashboard_id)
    except KeyError:
        raise HTTPException(404, "Dashboard not found")


@router.post("/dashboards/{dashboard_id}/save")
def save_dashboard_config(dashboard_id: str, dash: DashboardConfig):
    if dashboard_id != dash.id:
        raise HTTPException(400, "Dashboard ID mismatch")
    return save_dashboard(dash)


@router.get("/default-dashboard")
def default_dashboard():
    return get_default_dashboard()


@router.post("/dashboards/{dashboard_id}/charts")
def add_dashboard_chart(dashboard_id: str, payload: AddToDashboardPayload):
    try:
        return add_chart(dashboard_id, payload)
    except KeyError:
        raise HTTPException(404, "Dashboard not found")


@router.delete("/dashboards/{dashboard_id}/charts/{chart_id}")
def delete_dashboard_chart(dashboard_id: str, chart_id: str):
    try:
        return remove_chart(dashboard_id, chart_id)
    except KeyError:
        raise HTTPException(404, "Dashboard not found")


@router.post("/dashboards/{dashboard_id}/charts/{chart_id}/move")
def move_dashboard_chart(dashboard_id: str, chart_id: str, payload: dict):
    direction = payload.get("direction", "next")
    try:
        return update_chart_position(dashboard_id, chart_id, direction)
    except KeyError:
        raise HTTPException(404, "Dashboard or chart not found")


# ---------- Prediction Layer ----------
@router.get("/prediction/feasibility/{dataset_id}")
def prediction_feasibility(dataset_id: str):
    from ..prediction.service import PredictionService
    try:
        return PredictionService.get_feasibility(dataset_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Feasibility check failed: {e}")


@router.post("/prediction/train")
def prediction_train(payload: TrainRequest):
    from ..prediction.service import PredictionService
    try:
        return PredictionService.train_model(payload)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Training failed: {e}")


@router.get("/prediction/models/{identifier}")
def prediction_models(identifier: str, current_version_only: bool = False):
    """Retrieves model details if identifier starts with model_, or lists models if dataset_id."""
    from ..prediction.service import PredictionService
    if identifier.startswith("model_"):
        try:
            return PredictionService.get_model(identifier)
        except KeyError:
            raise HTTPException(404, f"Model '{identifier}' not found")
    else:
        return {"models": PredictionService.list_models(identifier, current_version_only=current_version_only)}


@router.get("/prediction/models/{model_id}/details")
def prediction_model_details(model_id: str):
    from ..prediction.service import PredictionService
    try:
        return PredictionService.get_model(model_id)
    except KeyError:
        raise HTTPException(404, f"Model '{model_id}' not found")


@router.post("/prediction/predict")
def prediction_predict(payload: PredictRequest):
    from ..prediction.service import PredictionService
    try:
        return PredictionService.predict(payload)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Prediction failed: {e}")

