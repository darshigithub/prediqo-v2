# Prediqo Development Guide

This guide provides step-by-step instructions for common engineering and extension tasks in Prediqo, covering the Phase 2.5 modular monolith architecture, background ingestion jobs, DuckDB query execution, query caching, and performance verification.

---

## 1. Local Development Setup

### Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-flex.txt
pip install pytest httpx
uvicorn app.main:app --reload --port 8000
```
- API Documentation (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### Frontend
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```
- Frontend application: [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## 2. Running Tests & Quality Checks

### Backend Unit, Integration & Architecture Tests
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```
This runs all 53 test cases across:
- `test_phase25_architecture.py`: Ingestion jobs, DuckDB direct Parquet execution, query cache hit/invalidation, and versioned refresh.
- `test_ai_analyst.py`: Natural language translation, validation, and multi-provider LLMs.
- `test_semantic_intelligence.py`: Business roles, aggregation policies, and derived metrics.
- `test_core.py`: Standardization, rule-based parsing, and query execution.

### Section 35 Acceptance Test Workflow
Run the end-to-end 10-step acceptance verification script:
```powershell
.\backend\.venv\Scripts\python.exe scripts\verify_acceptance_workflow.py
```
This script tests the entire lifecycle from job creation through server-side pagination, DuckDB queries, cache hits, dashboard query specs, and zero-downtime refresh with cache invalidation.

### Large Dataset Benchmarking
Run the automated benchmark suite on 100k and 1M row synthetic datasets:
```powershell
.\backend\.venv\Scripts\python.exe scripts\benchmark_large_dataset.py
```
Outputs execution durations and compression ratios to console and saves JSON results to [`scripts/benchmark_results.json`](file:///D:/AIML/prediqo-v1/scripts/benchmark_results.json).

### Frontend Typechecking & Linting
```powershell
cd frontend
npm run build     # runs 'tsc -b && vite build'
npm run lint      # runs oxlint
```

---

## 3. How the Ingestion Job System Works

Ingestion jobs decouple data preparation from the query path. They are managed by [`JobManager`](file:///D:/AIML/prediqo-v1/backend/app/jobs/job_manager.py) in `backend/app/jobs/`.

### Starting an Ingestion Job
To run an ingestion pipeline in the background:
```python
from app.jobs.job_manager import JobManager
from app.jobs.ingestion_job import run_ingestion_job

job = JobManager.create_job(
    dataset_id=dataset_id,
    source_type="csv",
    source_path=str(uploaded_file_path),
    dataset_name=dataset_name,
)
JobManager.submit_task(job.job_id, run_ingestion_job, job.job_id)
```

### Stage Transitions & Progress Reporting
Workers update progress via `JobManager.update_job`:
```python
JobManager.update_job(job_id, stage=JobStage.STANDARDIZING, progress=30)
...
JobManager.update_job(job_id, stage=JobStage.WRITING, progress=85)
...
JobManager.update_job(job_id, stage=JobStage.COMPLETED, status=JobStatus.COMPLETED, progress=100)
```

---

## 4. Querying Direct Parquet with DuckDB

DuckDB should query Parquet files directly without loading full DataFrames into Pandas:

```python
import duckdb

con = duckdb.connect()
# Register Parquet file as a virtual SQL view
con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{parquet_path}')")

# Apply column pruning (only select dimensions and required metrics)
sql = 'SELECT "City", SUM("Total_Amount") AS "Total_Amount" FROM t GROUP BY "City" ORDER BY "Total_Amount" DESC LIMIT 50'
df_result = con.execute(sql).df()
```

### Best Practices:
1. **Always Quote Column Names**: Wrap column identifiers in double quotes via `_quote_ident()` to prevent SQL syntax errors on spaces or reserved keywords.
2. **Push Filters Down**: Convert plan filters directly to SQL `WHERE` expressions so Parquet can skip irrelevant row groups.
3. **Sanitize NaN Values**: Map all `pd.isna(v) -> None` before JSON serialization to avoid runtime errors on float `NaN`.

---

## 5. Working with the Query Cache

The query cache is managed by [`QueryCache`](file:///D:/AIML/prediqo-v1/backend/app/cache/query_cache.py) and stores execution results in `data/cache/query/`.

### Computing Cache Keys
Cache keys are canonical SHA-256 hashes incorporating `dataset_id`, `version`, and the normalized query dictionary:
```python
from app.cache.query_cache import QueryCache, compute_query_hash

q_hash = compute_query_hash(dataset_id=dataset_id, version=meta["version"], query=query_spec)
cached = QueryCache.get(q_hash)
if cached:
    return cached  # Sub-10ms response!
```

### Invalidation
- **Version-based**: When a dataset is refreshed, `version` increments from `1` to `2`. Any subsequent hash computation naturally points to a new key, instantly invalidating stale caches.
- **Manual Cleanup**: Call `QueryCache.clear()` to remove all cached query files.

---

## 6. How to Add a New Data Connector

1. **Implement `DataConnector` ABC**:
   Create `backend/app/connectors/<name>_connector.py`:
   ```python
   from .base import DataConnector
   import pandas as pd

   class MyNewConnector(DataConnector):
       def test_connection(self, config: dict) -> bool:
           ...
       def list_datasets(self, config: dict) -> list[dict]:
           ...
       def get_schema(self, config: dict, dataset: str) -> list[dict]:
           ...
       def fetch_data(self, config: dict, dataset: str) -> pd.DataFrame:
           ...
   ```

2. **Register in `registry.py`**:
   Add to `_REGISTRY` in `backend/app/connectors/registry.py`:
   ```python
   _REGISTRY["my_source"] = MyNewConnector
   ```

3. **Hook into Asynchronous Ingestion Job**:
   In `backend/app/api/routes.py`, trigger an ingestion job rather than blocking:
   ```python
   @router.post("/connect/my-source")
   def connect_my_source(config: MySourceConfig):
       job = JobManager.create_job(
           dataset_id=f"ds_{uuid.uuid4().hex[:8]}",
           source_type="my_source",
           dataset_name=config.name,
       )
       JobManager.submit_task(job.job_id, run_ingestion_job, job.job_id)
       return {"job_id": job.job_id, "dataset_id": job.dataset_id, "status": "QUEUED"}
   ```

---

## 7. Configuring Multi-Provider LLMs

Optional AI providers can be configured in `backend/.env` or `.env` at root:

```env
# Provider options: openai, groq, gemini, anthropic, custom
LLM_PROVIDER=openai

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Groq
GROQ_API_KEY=gsk-...
GROQ_MODEL=llama-3.3-70b-versatile

# Google Gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-1.5-flash

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-latest

# Custom OpenAI-compatible endpoint (Local Ollama / vLLM)
CUSTOM_BASE_URL=http://localhost:11434/v1
CUSTOM_API_KEY=ollama
CUSTOM_MODEL=llama3.1
```

If no keys are provided, Prediqo runs automatically in deterministic mode without error.

---

## 8. Extending Business Roles and Aggregation Policies

Business semantic inference is centralized in `backend/app/standardization/semantics.py`:

1. **Adding a New Business Role**:
   - In `infer_business_role(col_name, semantic_type, data_type, ...)`:
     - Add regex or substring patterns in the appropriate category block (e.g. `_is_churn_col`).
     - Return the standard role string (e.g. `"churn"`).

2. **Configuring Allowed Aggregations**:
   - In `get_allowed_aggregations(semantic_type, business_role)`:
     - Define which SQL aggregations (`COUNT`, `DISTINCT_COUNT`, `SUM`, `AVG`, `MIN`, `MAX`) are mathematically sensible.

3. **Registering Derived Metrics**:
   - In `discover_derived_metrics(columns)`:
     - Define new derived metrics referencing real columns:
       ```python
       DerivedMetric(
           id="churn_rate",
           name="Churn Rate",
           description="Percentage of churned customers",
           formula="AVG(is_churned)",
           underlying_column=col.name,
           aggregation="AVG",
       )
       ```

---

## 9. Working with the Machine Learning Prediction Layer

The Prediction Layer (`backend/app/prediction/`) enables automated supervised machine learning models (Regression and Classification) trained locally using `scikit-learn`.

### How to Check Feasibility Programmatically
```python
from app.prediction.service import PredictionService

feasibility = PredictionService.get_feasibility(dataset_id="ds_a377a26e")
print("Prediction possible:", feasibility.prediction_possible)
print("Regression targets:", [t.name for t in feasibility.regression_targets])
print("Classification targets:", [t.name for t in feasibility.classification_targets])
```

### How to Train a Model
```python
from app.prediction.models import TrainRequest
from app.prediction.service import PredictionService

req = TrainRequest(
    dataset_id="ds_a377a26e",
    target_column="Delivery_Days",
    problem_type="regression",
    features=["Customer_Age", "City", "Product_Category", "Quantity", "Unit_Price", "Discount_Percent"],
    test_size=0.2,
    random_state=42,
)
resp = PredictionService.train_model(req)
print(f"Trained model {resp.model_id}: Best algorithm is {resp.best_model.algorithm} (MAE: {resp.best_model.metrics['mae']})")
```

### How to Make Predictions
```python
from app.prediction.models import PredictRequest
from app.prediction.service import PredictionService

pred_req = PredictRequest(
    model_id=resp.model_id,
    features={
        "Customer_Age": 28,
        "City": "Bangalore",
        "Product_Category": "Electronics",
        "Quantity": 2,
        "Unit_Price": 1500.0,
        "Discount_Percent": 10,
    },
)
res = PredictionService.predict(pred_req)
print("Prediction:", res.prediction, res.unit)
print("Explanation:", res.explanation)
```

### Supported Algorithms & Selection Strategy
- **Regression**: `LinearRegression`, `RandomForestRegressor`, `GradientBoostingRegressor`. Selected by **Lowest MAE**.
- **Classification**: `LogisticRegression`, `RandomForestClassifier`, `GradientBoostingClassifier`. Selected by **Highest F1**.
- All artifacts are persisted under `data/models/{model_id}/` (`model.joblib`, `metadata.json`, `metrics.json`, `feature_schema.json`).

