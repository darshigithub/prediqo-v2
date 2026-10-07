"""Verification script for Section 35 Acceptance Test Workflow."""
import time
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.jobs.job_manager import JobManager
from app.jobs.job_models import JobStatus

client = TestClient(app)

def test_acceptance_workflow():
    print("=== ACCEPTANCE TEST WORKFLOW ===")
    sample_csv = Path(__file__).resolve().parents[1] / "data" / "uploads" / "ecommerce_sales.csv"
    assert sample_csv.exists()

    # STEP 1: Upload dataset -> Ingestion job created
    print("STEP 1: Upload dataset...")
    with open(sample_csv, "rb") as f:
        resp = client.post("/api/ingestion/jobs", files={"file": ("acceptance_sales.csv", f, "text/csv")})
    assert resp.status_code == 200, resp.text
    job_data = resp.json()
    job_id = job_data["job_id"]
    dataset_id = job_data["dataset_id"]
    print(f"  [OK] Ingestion job created: {job_id} for dataset: {dataset_id}")

    # STEP 2: Monitor job -> Stages progress to COMPLETED / READY
    print("STEP 2: Monitor job...")
    stages_seen = []
    for _ in range(60):
        time.sleep(0.1)
        r = client.get(f"/api/ingestion/jobs/{job_id}")
        assert r.status_code == 200
        cur_job = r.json()
        stage = cur_job.get("stage")
        if stage and stage not in stages_seen:
            stages_seen.append(stage)
        if cur_job["status"] in ("COMPLETED", "FAILED"):
            break

    assert cur_job["status"] == "COMPLETED"
    print(f"  [OK] Stages observed: {' -> '.join(stages_seen)}")
    print(f"  [OK] Job COMPLETED, progress: {cur_job['progress']}%, rows: {cur_job['row_count']}")

    # STEP 3: Open dataset -> Metadata loads without re-profiling
    print("STEP 3: Open dataset...")
    resp = client.get(f"/api/datasets/{dataset_id}")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["status"] == "READY"
    assert meta["version"] == 1
    assert meta["profile"]["rows"] == 50
    print(f"  [OK] Dataset metadata loaded directly: {meta['dataset_name']} (v{meta['version']}, status={meta['status']})")

    # STEP 4: Open Data Explorer -> Paginated preview via DuckDB
    print("STEP 4: Open Data Explorer...")
    resp = client.get(f"/api/datasets/{dataset_id}/preview?page=1&page_size=10")
    assert resp.status_code == 200
    preview = resp.json()
    assert preview["total_rows"] == 50
    assert len(preview["rows"]) == 10
    assert preview["page"] == 1
    assert preview["total_pages"] == 5
    print(f"  [OK] Only requested rows loaded: {len(preview['rows'])} rows out of {preview['total_rows']} total")

    # STEP 5: AI Analyst: "What is the total revenue?"
    print("STEP 5: Ask 'What is the total revenue?'...")
    resp = client.post("/api/ai/analyze", json={
        "dataset_id": dataset_id,
        "question": "What is the total revenue?",
        "allow_fallback": True,
    })
    assert resp.status_code == 200
    a1 = resp.json()
    assert a1["cache_hit"] is False
    assert len(a1["result"]["rows"]) > 0
    print(f"  [OK] Result received via stored semantic model (No re-ingestion, DuckDB: {a1['timing']['duckdb_ms']}ms)")

    # STEP 6: Ask "Show revenue by city." -> DuckDB queries Parquet
    print("STEP 6: Ask 'Show revenue by city.'...")
    resp = client.post("/api/ai/analyze", json={
        "dataset_id": dataset_id,
        "question": "Show revenue by city.",
        "allow_fallback": True,
    })
    assert resp.status_code == 200
    a2 = resp.json()
    assert a2["cache_hit"] is False
    assert a2["result"]["dimension"] == "City"
    print(f"  [OK] DuckDB direct Parquet query executed (Rows: {len(a2['result']['rows'])}, DuckDB: {a2['timing']['duckdb_ms']}ms)")

    # STEP 7: Ask the same question again -> Cache Hit
    print("STEP 7: Repeat same question...")
    resp = client.post("/api/ai/analyze", json={
        "dataset_id": dataset_id,
        "question": "Show revenue by city.",
        "allow_fallback": True,
    })
    assert resp.status_code == 200
    a3 = resp.json()
    assert a3["cache_hit"] is True
    print(f"  [OK] Cache Hit confirmed! (Cache Hit: {a3['cache_hit']}, Total: {a3['timing']['total_ms']}ms)")

    # STEP 8: Open Dashboard -> Charts use query spec
    print("STEP 8: Open Dashboard...")
    # Add chart to default dashboard
    resp = client.get("/api/default-dashboard")
    assert resp.status_code == 200, resp.text
    dash = resp.json()
    dash_id = dash["id"]
    client.post(f"/api/dashboards/{dash_id}/charts", json={
        "dataset_id": dataset_id,
        "question": "Show revenue by city.",
        "chart_spec": {
            "dataset_id": dataset_id,
            "type": "bar",
            "dimension": "City",
            "metric": "Total_Amount",
            "aggregation": "sum",
        },
        "chart_type": "bar",
        "result": a2["result"]["rows"],
    })
    dash_detail = client.get(f"/api/dashboards/{dash_id}").json()
    assert len(dash_detail["layout"]) > 0
    assert dash_detail["layout"][-1]["spec"]["dimension"] == "City"
    print(f"  [OK] Dashboard chart rendered using stored query specification")

    # STEP 9: Refresh dataset -> New job starts, old READY version remains available
    print("STEP 9: Refresh dataset...")
    r_resp = client.post(f"/api/datasets/{dataset_id}/refresh")
    assert r_resp.status_code == 200
    ref_job = r_resp.json()
    assert ref_job["version"] == 2
    # Verify old version is still accessible during refresh
    old_meta = client.get(f"/api/datasets/{dataset_id}").json()
    assert old_meta["status"] == "READY"
    print(f"  [OK] Refresh job started (v{ref_job['version']}). Old version remains accessible as READY.")

    # STEP 10: Refresh succeeds -> Version becomes READY, old cache invalid
    print("STEP 10: Refresh completion & cache invalidation...")
    for _ in range(60):
        time.sleep(0.1)
        r_poll = client.get(f"/api/ingestion/jobs/{ref_job['job_id']}").json()
        if r_poll["status"] in ("COMPLETED", "FAILED"):
            break
    assert r_poll["status"] == "COMPLETED"

    new_meta = client.get(f"/api/datasets/{dataset_id}").json()
    assert new_meta["version"] == 2
    assert new_meta["status"] == "READY"

    # Query again: old cache is invalid due to version increment
    resp = client.post("/api/ai/analyze", json={
        "dataset_id": dataset_id,
        "question": "Show revenue by city.",
        "allow_fallback": True,
    })
    a4 = resp.json()
    assert a4["cache_hit"] is False
    print(f"  [OK] New version v2 is READY. Old cache is successfully invalidated (cache_hit={a4['cache_hit']}).")

    print("\n>>> ALL 10 STEPS OF ACCEPTANCE WORKFLOW PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_acceptance_workflow()
