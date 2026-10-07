"""Comprehensive tests for Phase 2.5: Data Processing, Ingestion & Performance Architecture."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
from fastapi.testclient import TestClient


from app.cache.query_cache import QueryCache, compute_query_hash
from app.core.config import DATASETS_DIR, METADATA_DIR, UPLOADS_DIR
from app.ingestion.pipeline import execute_ingestion_pipeline
from app.ingestion.service import refresh_dataset, start_ingestion_job
from app.jobs.job_manager import JobManager
from app.jobs.job_models import JobStage, JobStatus
from app.main import app
from app.models.dataset import DatasetStatus
from app.models.schemas import AggregationQuery
from app.query_engine.executor import execute_query, execute_query_plan
from app.storage.dataset_store import get_dataset, get_metadata, get_parquet_path

client = TestClient(app)


@pytest.fixture(scope="module")
def sample_csv(tmp_path_factory):
    """Creates a temporary sample CSV for testing ingestion."""
    fn = tmp_path_factory.mktemp("data") / "sample_sales.csv"
    data = {
        "Order_ID": [f"ORD_{i:04d}" for i in range(1, 201)],
        "Customer_Name": [f"Customer_{i % 10}" for i in range(1, 201)],
        "City": ["Bengaluru", "Mumbai", "Delhi", "Chennai"] * 50,
        "Total_Amount": [float(i * 10) for i in range(1, 201)],
        "Quantity": [(i % 5) + 1 for i in range(1, 201)],
        "Order_Status": ["Completed", "Pending", "Cancelled", "Completed"] * 50,
        "Order_Date": ["2025-01-15", "2025-02-10", "2025-03-05", "2025-04-20"] * 50,
    }
    df = pd.DataFrame(data)
    df.to_csv(fn, index=False)
    return str(fn)


# ==========================================
# 1. INGESTION JOB TESTS
# ==========================================

def test_job_creation_and_execution(sample_csv):
    """Test job creation, lifecycle stages, metadata persistence, and completion."""
    job = start_ingestion_job(
        source_type="csv",
        dataset_name="test_sales",
        source_config={"path": sample_csv},
    )

    assert job.job_id.startswith("job_")
    assert job.status in (JobStatus.QUEUED, JobStatus.PROCESSING)

    # Poll until completed (local execution is fast)
    for _ in range(50):
        time.sleep(0.1)
        latest = JobManager.get_job(job.job_id)
        if latest.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    assert latest.status == JobStatus.COMPLETED
    assert latest.stage == "READY"
    assert latest.progress == 100
    assert latest.row_count == 200

    # Verify dataset is in READY state
    meta = get_metadata(latest.dataset_id)
    assert meta is not None
    assert meta["status"] == DatasetStatus.READY
    assert meta["version"] == 1
    assert meta["profile"]["rows"] == 200
    assert Path(meta["file"]).exists()


def test_failed_ingestion_job():
    """Test handling of invalid/missing source file."""
    job = start_ingestion_job(
        source_type="csv",
        dataset_name="non_existent",
        source_config={"path": "non_existent_file.csv"},
    )

    for _ in range(30):
        time.sleep(0.1)
        latest = JobManager.get_job(job.job_id)
        if latest.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    assert latest.status == JobStatus.FAILED
    assert latest.error is not None
    assert "not found" in latest.error.lower()


# ==========================================
# 2. METADATA & PROFILE PERSISTENCE TESTS
# ==========================================

def test_profile_and_semantic_model_persisted(sample_csv):
    """Verify that profiling and semantic intelligence are persisted in metadata."""
    dest = UPLOADS_DIR / "sample_sales_persist.csv"
    shutil.copy(sample_csv, dest)

    job = start_ingestion_job("csv", "sales_persist", {"path": str(dest)})
    for _ in range(50):
        time.sleep(0.1)
        latest = JobManager.get_job(job.job_id)
        if latest.status == JobStatus.COMPLETED:
            break

    ds_id = latest.dataset_id
    meta = get_metadata(ds_id)

    # Check profile
    assert meta["profile"]["rows"] == 200
    assert meta["profile"]["columns"] == 7
    assert "Total_Amount" in meta["profile"]["numeric_columns"]

    # Check semantic model
    assert "semantic_model" in meta
    sem = meta["semantic_model"]
    assert "dimensions" in sem
    assert "City" in sem["dimensions"]
    assert "Total_Amount" in sem["measures"]

    # API endpoints should serve stored metadata directly without reload
    resp = client.get(f"/api/datasets/{ds_id}/semantic-model")
    assert resp.status_code == 200
    assert resp.json()["dataset_id"] == ds_id
    assert "Total_Amount" in resp.json()["measures"]

    resp = client.get(f"/api/datasets/{ds_id}/profile")
    assert resp.status_code == 200
    assert resp.json()["profile"]["rows"] == 200


# ==========================================
# 3. DUCKDB DIRECT PARQUET EXECUTION TESTS
# ==========================================

def test_duckdb_queries_parquet_directly(sample_csv):
    """Verify that DuckDB directly queries Parquet file paths."""
    job = start_ingestion_job("csv", "sales_duckdb", {"path": sample_csv})
    for _ in range(50):
        time.sleep(0.1)
        latest = JobManager.get_job(job.job_id)
        if latest.status == JobStatus.COMPLETED:
            break

    ds_id = latest.dataset_id
    parquet_path = get_parquet_path(ds_id)
    assert parquet_path is not None
    assert parquet_path.exists()

    # Direct aggregation query over Parquet
    q = AggregationQuery(
        dataset_id=ds_id,
        group_by=["City"],
        metric="Total_Amount",
        aggregation="sum",
    )
    res = execute_query(parquet_path, q)
    assert res["dimension"] == "City"
    assert len(res["data"]) == 4  # 4 cities
    assert "timing" in res
    assert "duckdb_ms" in res["timing"]

    # Direct filtered aggregation query
    q_filtered = AggregationQuery(
        dataset_id=ds_id,
        group_by=["City"],
        metric="Total_Amount",
        aggregation="sum",
        filters=[{"column": "Order_Status", "op": "eq", "value": "Completed"}],
    )
    res_filtered = execute_query(parquet_path, q_filtered)
    assert len(res_filtered["data"]) == 2  # Bengaluru and Chennai only have Completed orders in fixture
    assert all(r["City"] in ("Bengaluru", "Chennai") for r in res_filtered["data"])



def test_preview_pagination_duckdb(sample_csv):
    """Verify server-side pagination with DuckDB directly on Parquet."""
    job = start_ingestion_job("csv", "sales_preview", {"path": sample_csv})
    for _ in range(50):
        time.sleep(0.1)
        latest = JobManager.get_job(job.job_id)
        if latest.status == JobStatus.COMPLETED:
            break

    ds_id = latest.dataset_id

    # Page 1, page_size 20
    resp = client.get(f"/api/datasets/{ds_id}/preview?page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 200
    assert len(data["rows"]) == 20
    assert data["total_pages"] == 10
    assert data["page"] == 1

    # Filtered and sorted preview
    resp_filtered = client.get(f"/api/datasets/{ds_id}/preview?filter_col=City&filter_val=Bengaluru&sort_by=Total_Amount&sort_order=desc&page=1&page_size=10")
    assert resp_filtered.status_code == 200
    data_f = resp_filtered.json()
    assert len(data_f["rows"]) == 10
    assert all(r["City"] == "Bengaluru" for r in data_f["rows"])


# ==========================================
# 4. QUERY RESULT CACHE TESTS
# ==========================================

def test_query_result_cache_hit_and_invalidation(sample_csv):
    """Verify cache miss -> cache hit -> version invalidation cycle."""
    job = start_ingestion_job("csv", "sales_cache", {"path": sample_csv})
    for _ in range(50):
        time.sleep(0.1)
        latest = JobManager.get_job(job.job_id)
        if latest.status == JobStatus.COMPLETED:
            break

    ds_id = latest.dataset_id

    # 1. First analysis: Cache miss
    resp1 = client.post("/api/ai/analyze", json={
        "dataset_id": ds_id,
        "question": "Show revenue by city.",
        "allow_fallback": True,
    })
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["cache_hit"] is False
    assert "timing" in data1
    assert data1["timing"]["cache_hit"] is False

    # 2. Repeated question: Cache HIT!
    resp2 = client.post("/api/ai/analyze", json={
        "dataset_id": ds_id,
        "question": "Show revenue by city.",
        "allow_fallback": True,
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["cache_hit"] is True
    assert data2["timing"]["cache_hit"] is True

    # 3. Safe Refresh to version 2
    refresh_job = refresh_dataset(ds_id)
    for _ in range(50):
        time.sleep(0.1)
        r_latest = JobManager.get_job(refresh_job.job_id)
        if r_latest.status == JobStatus.COMPLETED:
            break

    meta_refreshed = get_metadata(ds_id)
    assert meta_refreshed["version"] == 2

    # 4. Question after refresh: Old cache is invalidated due to version increment -> Cache Miss!
    resp3 = client.post("/api/ai/analyze", json={
        "dataset_id": ds_id,
        "question": "Show revenue by city.",
        "allow_fallback": True,
    })
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["cache_hit"] is False


# ==========================================
# 5. SAFE DATASET REFRESH TESTS
# ==========================================

def test_safe_refresh_preserves_old_version_on_failure(sample_csv):
    """Verify that a failing refresh does NOT destroy the existing working READY version."""
    job = start_ingestion_job("csv", "sales_safe_refresh", {"path": sample_csv})
    for _ in range(50):
        time.sleep(0.1)
        latest = JobManager.get_job(job.job_id)
        if latest.status == JobStatus.COMPLETED:
            break

    ds_id = latest.dataset_id
    original_meta = get_metadata(ds_id)
    assert original_meta["status"] == DatasetStatus.READY
    assert original_meta["version"] == 1

    # Tamper source_config to cause the refresh to fail
    original_meta["source_config"] = {"path": "corrupt_or_missing_path.csv"}
    (METADATA_DIR / f"{ds_id}.json").write_text(json.dumps(original_meta, indent=2))

    # Trigger refresh
    refresh_job = refresh_dataset(ds_id)
    for _ in range(50):
        time.sleep(0.1)
        r_latest = JobManager.get_job(refresh_job.job_id)
        if r_latest.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    assert r_latest.status == JobStatus.FAILED

    # Version 1 must still remain READY and queryable!
    current_meta = get_metadata(ds_id)
    assert current_meta["status"] == DatasetStatus.READY
    assert current_meta["version"] == 1
    assert get_parquet_path(ds_id).exists()
