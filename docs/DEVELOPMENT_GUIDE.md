# Prediqo Development Guide

This guide provides step-by-step instructions for common engineering and extension tasks in Prediqo, covering the modular monolith architecture, background ingestion jobs, DuckDB query execution, query caching, supervised machine learning prediction, time-series forecasting, and dataset capability assessment.

---

## 1. Local Development Setup

### Backend (Python 3.13)
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

### Frontend (React 19 + Vite)
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```
- Frontend application: [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## 2. Running Tests & Quality Checks

### Backend Full Test Suite (156 Tests)
```powershell
$env:PYTHONPATH="backend"
.\backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```
Runs all 156 test cases across:
- `test_ai_explanations.py` (34 tests): AI-Powered Business Explanation Layer, Ollama provider, deterministic fallback, semantic clause validation, negative disclaimer acceptance, corrective retries, fingerprint caching, and FastAPI endpoints.
- `test_decisions.py` (15 tests): Decision Layer rules engine, operator validation, condition evaluation, persistence, audit trails.
- `test_explainability.py` (22 tests): Local additive reconstruction, exact tree paths, multiclass classification, grouped one-hot global attributions, forecast trend drivers, collinearity warnings, and version mismatches.
- `test_phase3_reliability.py` (18 tests): Phase 3 reliability edge cases, high cardinality, zero-variance features, class imbalance, and backtest windows.
- `test_forecasting.py` (10 tests): Feasibility, staleness, DuckDB Parquet aggregation, backtesting, intervals, persistence.
- `test_prediction.py` (13 tests): Regression, classification, K-fold cross-validation, residuals, correlation leakage.
- `test_flexibility_and_capabilities.py` (9 tests): Datasets A–E, repeated line-item granularity, manual mapping overrides.
- `test_phase25_architecture.py` (8 tests): Ingestion jobs, DuckDB direct Parquet execution, query cache hit/invalidation, and versioned refresh.
- `test_ai_analyst.py` (11 tests): Natural language translation, validation, and multi-provider LLMs.
- `test_semantic_intelligence.py` (9 tests): Business roles, aggregation policies, and column synonyms.
- `test_core.py` (7 tests): Standardization, rule-based parsing, and query execution.

### Frontend Unit & Business Logic Tests (26 Tests)
```powershell
npx tsx --test frontend/tests/businessMetrics.test.ts frontend/tests/xaiNarratives.test.ts frontend/tests/decisionRules.test.ts frontend/tests/aiExplanation.test.ts frontend/tests/unifiedCenters.test.ts
```
Runs unit and business translation tests across:
- `unifiedCenters.test.ts` (7 tests): Prediction Center and Forecasting Center 4-tab navigation invariants (`Overview`, `Analytics`, `AI Explanation`, `Technical Details`), regression vs classification state handling, timeline chart separation (historical actuals vs future horizon), stale data detection, full projection schedule preservation, and state persistence across tab switching.
- `aiExplanation.test.ts` (4 tests): AI business explanation schema contract, prediction and forecast payload normalization, and limitation assertions.
- `decisionRules.test.ts` (5 tests): Decision layer rule validation, priority/status badges, and terminal state invariants.
- `businessMetrics.test.ts` (5 tests): Numeric and currency formatting with units (`$`, `%`, `days`, `units`), regression metrics translation, classification accuracy and F1 balance, forecasting WAPE and MAE, and baseline comparison uplift calculation.
- `xaiNarratives.test.ts` (5 tests): Local prediction drivers, positive and negative factors, log-odds margin scale notices, global dataset-wide drivers, collinearity disclosures, and forecast trajectory narrative generation.


### Frontend Production Build
```powershell
npm --prefix frontend run build
```
Executes TypeScript compilation (`tsc -b`) and Vite production bundling.

### Acceptance Test Workflow
Run the end-to-end 10-step acceptance verification script:
```powershell
.\backend\.venv\Scripts\python.exe scripts\verify_acceptance_workflow.py
```
Tests the entire lifecycle from job creation through server-side pagination, DuckDB queries, cache hits, dashboard query specs, and zero-downtime refresh with cache invalidation.

### Large Dataset Benchmarking
Run the automated benchmark suite on 100k and 1M row synthetic datasets:
```powershell
.\backend\.venv\Scripts\python.exe scripts\benchmark_large_dataset.py
```
Outputs execution durations and compression ratios to console and saves JSON results to [`scripts/benchmark_results.json`](file:///D:/AIML/prediqo-v2/scripts/benchmark_results.json).

### Frontend Typechecking & Linting
```powershell
cd frontend
npm run build     # runs 'tsc -b && vite build'
npm run lint      # runs oxlint
```

---

## 3. How the Ingestion Job System Works

Ingestion jobs decouple data preparation from the query path. They are managed by [`JobManager`](file:///D:/AIML/prediqo-v2/backend/app/jobs/job_manager.py) in `backend/app/jobs/`.

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

DuckDB queries Parquet files directly without loading full DataFrames into Pandas:

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
2. **Push Filters Down**: Convert plan filters directly to SQL `WHERE` expressions so DuckDB skips irrelevant Parquet row groups.
3. **Sanitize NaN Values**: Map all `pd.isna(v) -> None` before JSON serialization to avoid runtime errors on float `NaN`.

---

## 5. Working with the Query Cache

The query cache is managed by [`QueryCache`](file:///D:/AIML/prediqo-v2/backend/app/cache/query_cache.py) and stores execution results in `data/cache/query/`.

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
   - In `infer_business_role(...)`: Add regex or substring patterns in `_ROLE_PATTERNS`.
   - Supports non-standard synonyms (e.g. `purchased_on`, `net_sales`, `invoice_number`, `gross_sales`).

2. **Configuring Allowed Aggregations**:
   - In `get_allowed_aggregations(semantic_type, business_role)`:
     - Define which SQL aggregations (`COUNT`, `DISTINCT_COUNT`, `SUM`, `AVG`, `MIN`, `MAX`) are permitted.
     - Strictly forbids invalid math on identifiers (e.g. `SUM(ID)`).

---

## 9. Working with the Supervised Prediction Layer

The Prediction Layer (`backend/app/prediction/`) enables automated supervised machine learning models (Regression and Classification) trained locally using `scikit-learn`. For full details, see [docs/PREDICTION.md](docs/PREDICTION.md).

### How to Check Feasibility Programmatically
```python
from app.prediction.service import PredictionService

feasibility = PredictionService.get_feasibility(dataset_id="ds_a377a26e")
print("Prediction possible:", feasibility.prediction_possible)
print("Regression targets:", [t.name for t in feasibility.regression_targets])
print("Classification targets:", [t.name for t in feasibility.classification_targets])
```

### How to Train a Model with Cross-Validation
```python
from app.prediction.models import TrainRequest
from app.prediction.service import PredictionService

req = TrainRequest(
    dataset_id="ds_a377a26e",
    target_column="Delivery_Days",
    problem_type="regression",
    features=["Customer_Age", "City", "Product_Category", "Quantity", "Unit_Price", "Discount_Percent"],
    test_size=0.2,
    cv_folds=5,
    validation_strategy="k_fold",
    random_state=42,
)
resp = PredictionService.train_model(req)
print(f"Trained model {resp.model_id}: Best is {resp.best_model.algorithm} (CV MAE: {resp.best_model.cv_metrics.mae})")
print(f"Residual points for chart: {len(resp.actual_vs_predicted)}")
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

---

## 10. Working with the Time-Series Forecasting Intelligence Layer

The Forecasting Layer (`backend/app/forecasting/`) generates chronological temporal projections. For full details, see [docs/FORECASTING.md](docs/FORECASTING.md).

### Checking Forecasting Feasibility Programmatically
```python
from app.forecasting.service import ForecastingService

feasibility = ForecastingService.get_feasibility(dataset_id="ds_a377a26e")
print("Date columns:", feasibility.date_columns)
print("Recommended metric:", feasibility.recommended_metric_column)
print("Historical range:", feasibility.min_date, "to", feasibility.max_date)
print("Is series stale:", feasibility.is_stale)
```

### Training and Projecting Horizons
```python
from app.forecasting.models import ForecastTrainRequest
from app.forecasting.service import ForecastingService

req = ForecastTrainRequest(
    dataset_id="ds_a377a26e",
    date_column="Order_Date",
    metric_column="Sales_Amount",
    frequency="M",
    forecast_horizon=6,
    aggregation_method="SUM",
)
res = ForecastingService.train_and_project(req)
print(f"Best forecaster: {res.best_model.algorithm} (Backtest MAE: {res.best_model.metrics.mae})")
print(f"Improvement vs Naive: {res.best_model.vs_naive_pct:.1f}%")

for pt in res.forecast_points:
    print(f"{pt.date}: Predicted {pt.predicted:.1f} (95% CI: [{pt.lower_95:.1f}, {pt.upper_95:.1f}])")
```

### Candidate Forecasters Suite
- `NaiveForecaster`: Carries latest observation forward.
- `SeasonalNaiveForecaster`: Replicates previous seasonal cycle ($m=7$ for daily, $m=12$ for monthly, $m=4$ for quarterly).
- `MovingAverageForecaster`: Rolling window average ($w=3, 7$).
- `LinearTrendForecaster`: Ordinary least-squares step trend.
- `ExponentialSmoothingForecaster`: Holt's linear trend with level and trend smoothing.

---

## 11. Working with the Capability Registry & Schema Flexibility

The Capability Registry (`backend/app/capabilities/`) dynamically evaluates dataset schema readiness across diverse real-world tables.

### Assessing Dataset Capabilities Programmatically
```python
from app.capabilities.registry import assess_capabilities

assessment = assess_capabilities("ds_a377a26e")
print("Overall status:", assessment.overall_status)
print("Prediction ready:", assessment.prediction.ready)
print("Forecasting ready:", assessment.forecasting.ready)
print("Granularity:", assessment.granularity.detected_granularity)
if assessment.granularity.has_repeated_order_totals:
    print("Warning: Repeated order totals detected across line items!")
```

### How Granularity Detection Works
DuckDB checks whether distinct identifiers are less than total rows:
```sql
SELECT COUNT(DISTINCT "order_id") < COUNT(*) FROM read_parquet('data/datasets/{id}.parquet')
```
If true, summing an `order_total` column would inflate analytical figures, and the system emits a critical warning advising users to aggregate line-item quantities or use order-level grouping.

---

## 12. Adding New Forecasters or Prediction Models

### Adding a New Forecasting Candidate
1. Open [`backend/app/forecasting/trainer.py`](file:///D:/AIML/prediqo-v2/backend/app/forecasting/trainer.py).
2. Subclass `BaseForecaster`:
   ```python
   class MyCustomForecaster(BaseForecaster):
       algorithm_name = "MyCustomForecaster"
       
       def fit(self, y: np.ndarray) -> "MyCustomForecaster":
           self.history = y
           return self

       def predict(self, horizon: int) -> np.ndarray:
           # Generate horizon point forecasts
           return np.repeat(np.mean(self.history[-5:]), horizon)
   ```
3. Add `MyCustomForecaster` to `get_candidate_forecasters(series_length, frequency)`.
4. The backtesting evaluator will automatically test, score, and include it in the candidate leaderboard.

### Adding a New Regressor or Classifier
1. Open [`backend/app/prediction/trainer.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/trainer.py).
2. Instantiate your scikit-learn estimator in `_train_regression` or `_train_classification`.
3. Wrap it with `Pipeline([('prep', preprocessor), ('estimator', my_estimator)])`.
4. It will immediately inherit K-Fold cross-validation, feature importance extraction, and persistence.

---

## 13. Business-Friendly Experience Layer

Prediqo includes a presentation and usability layer tailored for business stakeholders and analysts:
- **Architecture & Workflow**: Refer to [`docs/BUSINESS_PREDICTION_GUIDE.md`](file:///D:/AIML/prediqo-v2/docs/BUSINESS_PREDICTION_GUIDE.md).
- **Core Business Components** (`frontend/src/components/business/`):
  - `DataQualityCard.tsx`: Cell completeness %, total rows/columns, missing values breakdown, and health grade.
  - `BusinessMetricsCard.tsx`: Plain-language translations of $R^2$, MAE, RMSE, MAPE, Accuracy, and F1 with baseline uplift banners.
  - `PredictionInsightCard.tsx`: Formatted point estimates with inferred units (`$`, `%`, `days`, `units`), baseline context, and class probabilities.
  - `ForecastInsightCard.tsx`: Executive forecast projection summary, average and cumulative projections, and backtest reliability.
  - `HumanReadableXAICard.tsx`: Template-based narrative of top positive and negative drivers, scale disclosures (log-odds margin vs probability vs original units), and non-causal attribution notices.
  - `DecisionChecklistCard.tsx`: 5-point operational safeguards checklist.
- **Utilities**:
  - [`frontend/src/utils/businessMetrics.ts`](file:///D:/AIML/prediqo-v2/frontend/src/utils/businessMetrics.ts): Formatting and metric business interpretation logic.
  - [`frontend/src/utils/xaiNarratives.ts`](file:///D:/AIML/prediqo-v2/frontend/src/utils/xaiNarratives.ts): Deterministic narrative generator for local, global, and time-series explanations.

---

## 14. Decision Layer MVP (Decision Center)

Prediqo includes a standalone **Decision Center** (`/decisions`) that converts validated ML predictions, forecasts, and data quality profiles into structured, explainable, and deterministic business recommendations:
- **Comprehensive Guide**: See [`docs/DECISION_LAYER_GUIDE.md`](file:///D:/AIML/prediqo-v2/docs/DECISION_LAYER_GUIDE.md).
- **Backend Architecture** (`backend/app/decisions/`):
  - `models.py`: Pydantic data contracts for rules, evaluations, recommendations, and audit logs.
  - `rules_engine.py`: Safe, deterministic rules evaluator (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `is_present`, `is_missing`) with unit compatibility checks and `NOT_EVALUABLE` status tracking.
  - `evidence_collector.py`: Collects model outputs and dataset metrics on disk with zero model retraining.
  - `store.py`: Local JSON persistence at `data/decisions/` (`rules.json`, `evaluations/`, `recommendations/`, `audit_log.json`).
  - `service.py`: Orchestrates evaluations, recommendation synthesis, approval workflows, and audit logging.
  - `routes.py`: FastAPI endpoints under `/api/decisions/*`.
- **Frontend Architecture** (`frontend/src/components/decisions/` & `frontend/src/pages/`):
  - `DecisionCenterPage.tsx`: Top-level hub with Overview, Recommendations, Business Rules, and Audit History tabs.
  - `DecisionOverview.tsx`: Executive dashboard with KPI cards and high-priority action alerts.
  - `DecisionRecommendationsList.tsx`: Filterable recommendation cards by status, priority, and scenario.
  - `DecisionRecommendationCard.tsx`: Card rendering priority badges, actions, and evidence pills.
  - `DecisionDetailModal.tsx`: Audit modal with full evidence breakdown and approval/rejection actions (rejection/dismissal requires comment).
  - `DecisionRulesPage.tsx`: Rule configuration with active/disable toggles and deletion.
  - `DecisionRuleEditor.tsx`: Rule creation modal with live specification validation.
  - `DecisionEvaluateModal.tsx`: Wizard to link existing models/forecasts and operational facts to execute evaluations.
  - `DecisionHistoryPage.tsx`: Chronological governance audit trail.
- **Testing**:
  - Run backend tests: `.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_decisions.py -o pythonpath=backend -q`
  - Run frontend unit tests: `node --experimental-strip-types --test frontend/tests/decisionRules.test.ts`
  - Build production frontend: `npm --prefix frontend run build`

