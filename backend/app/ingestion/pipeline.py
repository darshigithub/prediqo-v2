"""Ingestion Pipeline: clean separation between reading, standardization,
profiling, semantic analysis, and analytical storage persistence.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from ..connectors.registry import fetch_via_connector
from ..core.config import DATASETS_DIR, DATASETS_INDEX, METADATA_DIR
from ..models.dataset import ColumnMeta, DatasetProfile, DatasetStatus
from ..profiling.profiler import build_profile
from ..standardization.semantics import (
    discover_derived_metrics,
    get_allowed_aggregations,
    get_display_name,
    infer_business_role,
)
from ..standardization.standardizer import _infer_semantic_type, standardize_columns

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ProgressCallback = Callable[[str, int, Optional[int]], None]


def execute_ingestion_pipeline(
    dataset_id: str,
    dataset_name: str,
    source_type: str,
    source_config: dict[str, Any],
    version: int = 1,
    progress_callback: Optional[ProgressCallback] = None,
) -> dict[str, Any]:
    """Runs the full ingestion pipeline end-to-end and writes Parquet + JSON metadata."""
    timings: dict[str, int] = {}
    t_start = time.perf_counter()

    def report(stage: str, progress: int, rows: Optional[int] = None):
        if progress_callback:
            progress_callback(stage, progress, rows)
        logger.info("[%s] Stage: %s, Progress: %d%%", dataset_id, stage, progress)

    # 1. READ SOURCE
    report("READING", 15, None)
    t0 = time.perf_counter()
    df = _read_source_data(source_type, source_config)
    timings["reading_ms"] = int((time.perf_counter() - t0) * 1000)
    raw_rows = len(df)
    logger.info("INGESTION_READING_COMPLETE rows=%d ms=%d", raw_rows, timings["reading_ms"])

    if df.empty:
        raise ValueError("Source dataset has no data rows")

    # 2. STANDARDIZATION
    report("STANDARDIZING", 35, raw_rows)
    t0 = time.perf_counter()
    df = standardize_columns(df)
    timings["standardization_ms"] = int((time.perf_counter() - t0) * 1000)
    logger.info("INGESTION_STANDARDIZATION_COMPLETE ms=%d", timings["standardization_ms"])

    if df.empty:
        raise ValueError("Dataset is empty after standardization")

    rows = len(df)

    # 3. PROFILING & SEMANTIC ANALYSIS
    report("PROFILING", 55, rows)
    t0 = time.perf_counter()
    columns_meta: list[ColumnMeta] = []
    for col in df.columns:
        s = df[col]
        dtype = str(s.dtype)
        null_count = int(s.isna().sum())
        unique_count = int(s.nunique(dropna=True))
        semantic = _infer_semantic_type(s, dtype, unique_count, rows)
        role = infer_business_role(str(col), s, dtype, semantic, unique_count, rows)
        disp_name = get_display_name(str(col), role)
        allowed_aggs = get_allowed_aggregations(semantic, role, dtype)

        cm = ColumnMeta(
            name=str(col),
            dtype=dtype,
            semantic_type=semantic,
            unique_count=unique_count,
            null_count=null_count,
            business_role=role,
            display_name=disp_name,
            allowed_aggregations=allowed_aggs,
        )

        if semantic == "MEASURE":
            try:
                cm.min = float(s.min()) if pd.notna(s.min()) else None
                cm.max = float(s.max()) if pd.notna(s.max()) else None
                cm.avg = float(s.mean()) if pd.notna(s.mean()) else None
            except Exception:
                pass
        if semantic in ("CATEGORY", "TEXT", "DIMENSION"):
            try:
                top = s.value_counts().head(5)
                cm.top_values = [{"value": str(k), "count": int(v)} for k, v in top.items()]
            except Exception:
                pass

        columns_meta.append(cm)

    profile = build_profile(df, columns_meta)
    timings["profiling_ms"] = int((time.perf_counter() - t0) * 1000)
    logger.info("INGESTION_PROFILING_COMPLETE ms=%d", timings["profiling_ms"])

    # 4. BUILD COMPREHENSIVE SEMANTIC MODEL
    report("SEMANTIC_ANALYSIS", 75, rows)
    t0 = time.perf_counter()
    derived_metrics = discover_derived_metrics(columns_meta)
    dimensions = [c.name for c in columns_meta if c.semantic_type in ("DIMENSION", "CATEGORY")]
    measures = [c.name for c in columns_meta if c.semantic_type == "MEASURE"]
    date_fields = [c.name for c in columns_meta if c.semantic_type == "DATE"]
    identifiers = [c.name for c in columns_meta if c.semantic_type == "ID"]
    categories = [c.name for c in columns_meta if c.semantic_type == "CATEGORY"]

    columns_meta_dicts = [
        {
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
        }
        for c in columns_meta
    ]

    semantic_model = {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "columns": columns_meta_dicts,
        "dimensions": dimensions,
        "measures": measures,
        "date_fields": date_fields,
        "identifiers": identifiers,
        "categories": categories,
        "derived_metrics": derived_metrics,
    }
    timings["semantic_ms"] = int((time.perf_counter() - t0) * 1000)
    logger.info("INGESTION_SEMANTIC_COMPLETE ms=%d", timings["semantic_ms"])

    # 5. WRITE PARQUET AND METADATA
    report("WRITING", 90, rows)
    t0 = time.perf_counter()

    # Determine destination:
    # If versioning, we can save file as ds_123_v{version}.parquet or ds_123.parquet
    parquet_path = DATASETS_DIR / f"{dataset_id}.parquet"
    # For partitioned support if rows > 500k, write partitioned chunks; else single parquet
    if rows >= 500000:
        dataset_parts_dir = DATASETS_DIR / dataset_id
        dataset_parts_dir.mkdir(parents=True, exist_ok=True)
        chunk_size = 200000
        for i, chunk_start in enumerate(range(0, rows, chunk_size)):
            chunk_df = df.iloc[chunk_start:chunk_start + chunk_size]
            part_path = dataset_parts_dir / f"part-{i:03d}.parquet"
            chunk_df.to_parquet(part_path, index=False)
        target_file_str = str(dataset_parts_dir / "*.parquet")
    else:
        df.to_parquet(parquet_path, index=False)
        target_file_str = str(parquet_path)

    timings["writing_ms"] = int((time.perf_counter() - t0) * 1000)
    timings["total_ms"] = int((time.perf_counter() - t_start) * 1000)

    # 6. WRITE COMPLETE METADATA
    created_at = utc_now_iso()
    meta = {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "source_type": source_type,
        "source_config": source_config or {},
        "version": version,
        "status": DatasetStatus.READY,
        "error": None,
        "created_at": created_at,
        "updated_at": created_at,
        "file": target_file_str,
        "columns": columns_meta_dicts,
        "profile": {
            "rows": profile.rows,
            "columns": profile.columns,
            "missing_values": profile.missing_values,
            "duplicate_rows": profile.duplicate_rows,
            "numeric_columns": profile.numeric_columns,
            "categorical_columns": profile.categorical_columns,
            "date_columns": profile.date_columns,
            "column_stats": profile.column_stats,
        },
        "semantic_model": semantic_model,
        "timing": timings,
    }

    meta_file = METADATA_DIR / f"{dataset_id}.json"
    meta_file.write_text(json.dumps(meta, indent=2, default=str))

    # Rebuild index
    _rebuild_datasets_index()

    report("COMPLETED", 100, rows)
    logger.info("INGESTION_COMPLETE dataset_id=%s version=%d total_ms=%d", dataset_id, version, timings["total_ms"])

    return meta


def _read_source_data(source_type: str, source_config: dict[str, Any]) -> pd.DataFrame:
    path = source_config.get("path")
    if source_type == "csv":
        if not path or not Path(path).exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        # Optimize reading with chunking or low_memory
        return pd.read_csv(path, low_memory=False)
    elif source_type == "excel":
        if not path or not Path(path).exists():
            raise FileNotFoundError(f"Excel file not found: {path}")
        sheet = source_config.get("sheet", 0)
        return pd.read_excel(path, sheet_name=sheet)
    elif source_type in ("google_sheets", "postgresql"):
        dataset_param = source_config.get("table") or ""
        return fetch_via_connector(source_type, source_config, dataset=dataset_param)
    else:
        # Fallback to connector registry
        return fetch_via_connector(source_type, source_config, dataset="")


def _rebuild_datasets_index() -> None:
    entries = []
    for f in sorted(METADATA_DIR.glob("ds_*.json")):
        try:
            m = json.loads(f.read_text())
            entries.append({
                "dataset_id": m["dataset_id"],
                "dataset_name": m["dataset_name"],
                "source_type": m["source_type"],
                "version": m.get("version", 1),
                "status": m.get("status", DatasetStatus.READY),
                "error": m.get("error"),
                "created_at": m.get("created_at"),
                "updated_at": m.get("updated_at"),
                "rows": m.get("profile", {}).get("rows"),
                "columns": m.get("profile", {}).get("columns"),
            })
        except Exception:
            continue
    DATASETS_INDEX.write_text(json.dumps(entries, indent=2))
