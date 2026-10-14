# Prediqo Architecture Guide

This document explains the internal subsystems of Prediqo, their interaction models, architectural boundaries, and performance designs.

---

## 1. High-Level Target Architecture

Prediqo follows a **Modular Monolith** pattern within a single FastAPI application (`backend/app/`). Responsibilities are strictly partitioned between the **Ingestion Path** (prepare once) and the **Query / Serving Path** (analyze, predict, forecast, explain, and decide many times):

```text
                                  FRONTEND (React 19 + Vite 8)
                                             |
                                             v
                                  FASTAPI REST API (routes.py)
                                             |
                   +-------------------------+-------------------------+
                   |                                                   |
                   v                                                   v
           INGESTION PATH (Prepare Once)                       QUERY & SERVING PATH (Run Many Times)
                   |                                                   |
           [ Ingestion Jobs ]                                   [ Prediqo AI Router / Analyst ]
        (app/jobs/job_manager.py)                           (app/ai/ & app/query_engine/)
                   |                                                   |
        +----------+----------+                                        v
        |                     |                                 [ Semantic Model ]
        v                     v                                (Persisted JSON metadata)
 [ Connectors ]     [ Ingestion Pipeline ]                             |
 (CSV/Excel/Sheets) (app/ingestion/pipeline.py)                        v
        |                     |                                 [ Query Plan / Intent ]
        |       Stage 1: READING                               (Pydantic AIQueryPlan)
        |       Stage 2: STANDARDIZING                                 |
        |       Stage 3: PROFILING                                     v
        |       Stage 4: SEMANTIC_ANALYSIS                      [ Query Validator ]
        |       Stage 5: WRITING (Parquet)                             |
        |       Stage 6: METADATA (JSON)                               v
        +----------+----------+                               [ Query Cache Check ]
                   |                                          (app/cache/query_cache.py)
                   |                                                   |
                   |                                        +----------+----------+
                   |                                        | Miss                | Hit (<10ms)
                   v                                        v                     v
          [ Analytical Storage ]                    [ DuckDB Executor ]      [ Cached Result ]
        data/datasets/{id}.parquet             (read_parquet + prune/filter)      |
                   +                                        |                     |
          [ Dataset Metadata ]                              +----------+----------+
         data/metadata/{id}.json                                       |
                   |                                                   v
                   |                                        [ Charts / Dashboards ]
                   v
        +---------------------------------------------------------------------------------+
        |                                                                                 |
        v                                                 v                               v
[ Supervised ML Prediction ]                    [ Time-Series Forecasting ]     [ Decision Rules Engine ]
 (Linear, RF, Gradient Boosting)               (Naive, SNaive, MA, Trend, SES)   (Deterministic operators)
        |                                                 |                               |
        v                                                 v                               v
[ Exact Tree & Additive XAI ]                   [ Forecast Trajectory XAI ]      [ Evidence Collector ]
(Machine zero < 10^-14 error)                   (Trend, seasonality, coverage)            |
        |                                                 |                               v
        +------------------------+------------------------+                     [ Human Approval Store ]
                                 |                                              (data/decisions/*.json)
                                 v
                     [ AI Explanation Layer ]
                 (Clause validation, retries,
                  deterministic offline fallback)
```

---

## 2. Ingestion Subsystem & Pipeline (`app/ingestion/`)

The ingestion pipeline transforms raw input into structured analytical Parquet files and comprehensive JSON metadata. It runs strictly on upload, import, or explicit refresh:

```mermaid
flowchart LR
    A["Raw Connector"] --> B["1. READING"]
    B --> C["2. STANDARDIZING"]
    C --> D["3. PROFILING"]
    D --> E["4. SEMANTIC_ANALYSIS"]
    E --> F["5. WRITING"]
    F --> G["6. READY"]
```

### Ingestion Stages
1. **`READING`**: Reads raw data using chunking or buffered reading where applicable.
2. **`STANDARDIZING`**: Cleans headers, removes invalid characters, casts numeric/currency columns, and parses UTC datetimes.
3. **`PROFILING`**: Computes statistical summaries, missingness counts, cardinality, and distribution bounds.
4. **`SEMANTIC_ANALYSIS`**: Infers semantic types (`ID`, `DIMENSION`, `MEASURE`, `DATE`, `CATEGORY`, `TEXT`), business roles, and allowed aggregation policies.
5. **`WRITING`**: Serializes to Snappy-compressed Parquet (`data/datasets/{dataset_id}.parquet`). For large datasets ($\ge 500\text{k}$ rows), outputs partitioned files: `data/datasets/{dataset_id}/part-000.parquet`.
6. **`METADATA`**: Writes `data/metadata/{dataset_id}.json` containing full schema, profile, semantic model, version number, and lifecycle status (`READY`).

### Performance Instrumentation
Each stage records execution duration in milliseconds:
`timings: {reading_ms, standardization_ms, profiling_ms, semantic_ms, parquet_write_ms, metadata_ms, total_time_s}`.

---

## 3. Asynchronous Job System (`app/jobs/`)

Prediqo uses an in-process, non-blocking job execution system designed for zero infrastructure overhead:

- **Executor ([`job_manager.py`](file:///D:/AIML/prediqo-v2/backend/app/jobs/job_manager.py))**: Backed by a thread-safe `ThreadPoolExecutor(max_workers=4)`.
- **State Model ([`job_models.py`](file:///D:/AIML/prediqo-v2/backend/app/jobs/job_models.py))**:
  - `JobStage`: `QUEUED`, `READING`, `STANDARDIZING`, `PROFILING`, `SEMANTIC_ANALYSIS`, `WRITING`, `COMPLETED`, `FAILED`.
  - `JobStatus`: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`.
- **Persistence**: Every job state change is synchronously saved to `data/jobs/{job_id}.json`, ensuring full job inspection and debugging.
- **API Contract**:
  - `POST /api/ingestion/jobs`: Immediately returns HTTP 200 with `job_id`, `dataset_id`, and `status: QUEUED`.
  - `GET /api/ingestion/jobs/{job_id}`: Polled by the frontend to display the interactive stage checklist and progress bar (0–100%).

---

## 4. Dataset Lifecycle & Zero-Downtime Refresh

### Lifecycle States (`app/models/dataset.py`)
- **`CREATING`**: Job registered.
- **`PROCESSING`**: Ingestion underway. API blocks analytical queries with HTTP 400.
- **`READY`**: Data and metadata prepared; dataset queryable.
- **`FAILED`**: Ingestion terminated with error.
- **`STALE`**: Underlying source has been modified.

### Versioning & Zero-Downtime Refresh (`app/ingestion/service.py`)
1. Every dataset begins at `version = 1`.
2. When `POST /api/datasets/{dataset_id}/refresh` is triggered:
   - A refresh job starts targeting `version = current_version + 1`.
   - The job writes to a temporary staged Parquet file: `data/datasets/{dataset_id}_v{new_version}.parquet`.
   - **Zero Downtime**: While the refresh executes, queries continue to read the existing `v1` Parquet file and metadata without interruption.
   - Upon completion, the staged file atomically replaces the active Parquet file, the metadata version bumps to `2`, and status remains `READY`.
   - If refresh fails, the existing `v1` file remains untouched and fully functional.

---

## 5. DuckDB Analytical Query Engine (`app/query_engine/`)

The query engine operates directly on Parquet storage without loading full DataFrames into Pandas:

```python
con = duckdb.connect()
# Register Parquet view directly
con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{parquet_path}')")
rel = con.execute(sql)
out_df = rel.df()
```

### Architectural Optimizations
1. **Column Pruning**: Aggregation queries project only the requested dimensions and metric calculations:
   ```sql
   SELECT "City", SUM("Total_Amount") AS "Total_Amount"
   FROM t
   GROUP BY "City"
   ORDER BY "Total_Amount" DESC
   LIMIT 50
   ```
   DuckDB and Parquet scan only the bytes corresponding to `"City"` and `"Total_Amount"`, bypassing all other columns.
2. **Filter Push-Down**: Plan filters (e.g. `Region = 'North'`) are translated directly into the SQL `WHERE` clause, allowing DuckDB to skip irrelevant Parquet row groups based on file metadata.
3. **Hard Limit Safeguards**: Exploratory and filter queries automatically enforce `LIMIT 500` or `LIMIT 50` to safeguard frontend memory.
4. **Server-Side Data Explorer Pagination**: Data preview executes `SELECT * FROM t LIMIT {page_size} OFFSET {offset}` and `SELECT COUNT(*) FROM t` directly in DuckDB over Parquet.

---

## 6. Query Caching Subsystem (`app/cache/query_cache.py`)

To eliminate duplicate execution of identical queries, Prediqo implements a deterministic file-based query cache:

1. **Deterministic Hashing**:
   - Query inputs (dimensions, metrics, filters, sort, limits) are normalized and sorted into a canonical dictionary.
   - A SHA-256 hash is computed over `(dataset_id, version, canonical_query)`.
2. **Cache Lookup**:
   - Checks `data/cache/query/{hash}.json`.
   - On a **Cache Hit**, DuckDB execution and LLM inference are completely bypassed, returning results in under **8 ms** with `cache_hit: true`.
3. **Automatic Cache Invalidation**:
   - Because the hash key incorporates the dataset's `version` integer, refreshing a dataset automatically invalidates all previous cache entries without requiring manual file deletions.

---

## 7. Natural Language & AI Query Execution (`app/ai/`)

Prediqo supports two parsing paths, both strictly guarded by semantic validation:

### Path A: Deterministic Rule-Based Parser (Default & Offline)
- Inspects token n-grams in the user's question without network calls.
- Translates identifier aggregations into `COUNT(col)` based on the persisted semantic model.
- Generates a structured query executed directly by DuckDB.

### Path B: Multi-Provider LLM Query Planner (Optional)
- Reads the dataset schema, semantic types, business roles, and allowed aggregations directly from `data/metadata/{dataset_id}.json` without loading DataFrames.
- Generates an `AIQueryPlan` validated by [`query_validator.py`](file:///D:/AIML/prediqo-v2/backend/app/ai/query_validator.py).
- Enforces semantic aggregation rules (rejects `SUM(ID)` or `AVG(ID)`).
- Falls back to the deterministic parser if the LLM provider fails or is unconfigured.

---

## 8. Dashboard Query Performance (`app/storage/dashboard_store.py`)

Dashboards avoid storing large static result snapshots:
- Dashboards store the **Query Specification** (`chart_spec`: dimension, metric, aggregation, filters).
- When a dashboard is opened, [`populate_dashboard_charts`](file:///D:/AIML/prediqo-v2/backend/app/storage/dashboard_store.py) resolves each chart dynamically:
  1. Checks `QueryCache` for pre-calculated results.
  2. If missing, executes the query spec directly in DuckDB over Parquet.
  3. Caches the result for instant subsequent reloads.

---

## 9. Performance Benchmark Profile

Tested on local disk with 100k and 1M row transactional datasets ([`scripts/benchmark_results.json`](file:///D:/AIML/prediqo-v2/scripts/benchmark_results.json)):

| Operation | 100,000 Rows | 1,000,000 Rows | Architecture Advantage |
|---|---|---|---|
| **Storage Compression** | 6.64 MB $\rightarrow$ 2.01 MB | 66.37 MB $\rightarrow$ 18.12 MB | 3.66x binary Parquet compression |
| **Ingestion Duration** | 4.04 s | 39.46 s | One-time preparation; background job |
| **DuckDB Simple Aggregation** | **49.8 ms** | **47.1 ms** | Column pruning scans only needed columns |
| **DuckDB Filtered Aggregation** | **23.3 ms** | **39.3 ms** | Filter push-down skips Parquet row groups |
| **DuckDB Top-N Ranking** | **21.7 ms** | **37.0 ms** | Direct vectorized SQL execution |
| **Data Explorer Preview (100 rows)**| **13.1 ms** | **10.6 ms** | Server-side `LIMIT / OFFSET` over Parquet |
| **Query Cache Hit** | **7.19 ms** | **7.40 ms** | Instant JSON cache response |

---

## 10. Supervised Machine Learning Prediction Architecture

Prediqo incorporates a dedicated supervised machine learning prediction layer (`backend/app/prediction/`) alongside DuckDB analytics:

```text
                    PREDIQO PLATFORM
                           |
        +------------------+------------------+
        |                                     |
        v                                     v
    ANALYTICS (DuckDB)               PREDICTION (ML Engine)
   "What happened?"                  "What will happen?"
   Parquet Aggregations              Supervised Regression / Classification
        |                                     |
        +------------------+------------------+
                           |
                           v
                    AI EXPLANATION
```

### Modular Components
- **`FeasibilityAnalyzer` ([`feasibility.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/feasibility.py))**: Checks row counts, missing values, and identifies viable targets.
- **`TargetDetector` ([`target_detector.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/target_detector.py))**: Classifies targets into regression (continuous numeric measures) vs classification (categories/discrete status), strictly excluding identifiers.
- **`FeatureSelector` ([`feature_selector.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/feature_selector.py))**: Recommends predictors, excludes IDs and high-cardinality text, and applies heuristics to flag data leakage.
- **`DataPreparation` ([`data_preparation.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/data_preparation.py))**: Extracts required columns from Parquet via DuckDB, expands date components into numeric features, and bundles preprocessing into an atomic scikit-learn `ColumnTransformer`.
- **`ModelTrainer` ([`trainer.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/trainer.py))**: Fits three candidate models per problem type:
  - Regression: `LinearRegression`, `RandomForestRegressor`, `GradientBoostingRegressor`.
  - Classification: `LogisticRegression`, `RandomForestClassifier`, `GradientBoostingClassifier`.
- **`ModelEvaluator` ([`evaluator.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/evaluator.py))**: Evaluates candidate models using K-fold Cross-Validation and holdout test set (MAE/RMSE/R² for regression; Accuracy/Precision/Recall/F1 for classification), calculates actual-vs-predicted residual points, and selects best model using lowest CV MAE.
- **`FeatureImportance` ([`feature_importance.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/feature_importance.py))**: Extracts tree importances or linear coefficients and maps one-hot encoded features back to root column names.
- **`ModelStore` ([`model_store.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/model_store.py))**: Persists model pipelines, schemas, and metrics in `data/models/{model_id}/` with strict dataset version matching.
- **`Predictor` ([`predictor.py`](file:///D:/AIML/prediqo-v2/backend/app/prediction/predictor.py))**: Executes single-record inference and returns predictions, class probabilities, and human-readable explanations.

---

## 11. Time-Series Forecasting Intelligence Architecture

Prediqo provides a dedicated time-series forecasting engine (`backend/app/forecasting/`) that operates on chronological series:

```text
       [ Parquet Analytical Storage ]
                     |
         (DuckDB date_trunc Query)
                     v
       [ Aggregated Calendar Series ]
                     |
         (Continuous Reindexing & Imputation)
                     v
       [ Backtesting Split (N - H vs H) ]
                     |
         +-----------+-----------+
         |                       |
         v                       v
 [ Candidate Forecasters ] [ Chronological Backtest ]
 (Naive, SNaive, MA, ES)   (MAE, RMSE, WAPE, zero-safe MAPE)
         |                       |
         +-----------+-----------+
                     |
                     v
             [ Best Forecaster ]
                     |
        (Project H Steps + Uncertainty Intervals)
                     v
   [ Stored Model & Future Projections (80% / 95%) ]
```

### Key Subsystems
- **Feasibility & Date Extraction ([`feasibility.py`](file:///D:/AIML/prediqo-v2/backend/app/forecasting/feasibility.py))**: Validates candidate date columns and numeric metrics, falling back to DuckDB `MIN`/`MAX` Parquet expressions, and detects historical staleness (>60 days).
- **Parquet-Native Aggregation ([`data_preparation.py`](file:///D:/AIML/prediqo-v2/backend/app/forecasting/data_preparation.py))**: Directly executes DuckDB aggregation over Parquet with zero row materialization, followed by strict calendar continuity reindexing and policy-driven imputation.
- **Candidate Models ([`trainer.py`](file:///D:/AIML/prediqo-v2/backend/app/forecasting/trainer.py))**: Trains `NaiveForecaster`, `SeasonalNaiveForecaster` (seasonal periods 7, 12, 4), `MovingAverageForecaster` (windows 3, 7), `LinearTrendForecaster`, and `ExponentialSmoothingForecaster`.
- **Chronological Evaluation ([`evaluator.py`](file:///D:/AIML/prediqo-v2/backend/app/forecasting/evaluator.py))**: Enforces chronological backtesting without random shuffle, computing MAE, RMSE, WAPE, and relative error vs Naive baseline (`vs_naive_pct`).
- **Projection Engine ([`forecaster.py`](file:///D:/AIML/prediqo-v2/backend/app/forecasting/forecaster.py))**: Generates projected future timestamps strictly following historical boundaries, calculating 80% and 95% uncertainty bands scaling with $\sqrt{h}$.

---

## 12. Dataset Flexibility & Capability Registry

Prediqo dynamically analyzes diverse tabular schemas without rigid naming requirements (`backend/app/capabilities/`):

- **Synonym Intelligence ([`semantics.py`](file:///D:/AIML/prediqo-v2/backend/app/standardization/semantics.py))**: Recognizes alternative column headers (e.g. `purchased_on`, `invoice_number`, `net_sales`, `daily_revenue`, `gross_sales`).
- **Granularity Detection ([`registry.py`](file:///D:/AIML/prediqo-v2/backend/app/capabilities/registry.py))**: Identifies transaction vs line-item duplication via DuckDB distinct count comparisons (`COUNT(DISTINCT id) < COUNT(*)`), preventing repeated order total inflation.
- **Capability Assessment**: Dynamically determines dataset suitability for regression prediction, classification prediction, time-series forecasting, or both, with clear degradation explanations.
- **Manual Mapping Overrides**: Supports user corrections to auto-detected field roles via REST API.

---

## 13. Explainability Architecture (XAI Layer)

Located in `backend/app/explainability/`, this layer provides local and global interpretability grounded directly in mathematical estimators:

### Exact Additive Tree Path Decomposition (`local_explainer.py`)
For ensemble tree models (`RandomForestRegressor`, `RandomForestClassifier`, `GradientBoostingRegressor`, `GradientBoostingClassifier`), the local explainer evaluates the root-to-leaf decision paths:
$$\Delta_j^{tree}(x) = \sum_{k \in P : \text{split}(v_{k-1}) = j} (v_k - v_{k-1})$$
- Traces telescoping sums across every node transition.
- Guarantees exact mathematical identity:
  $$Y_0 + \sum_{j=1}^{p} \Delta_j(x) = \hat{y}(x)$$
  with numerical reconstruction error $< 10^{-14}$.

### Grouped Categorical Attribution (`feature_metadata.py`)
- Standard one-hot encoders produce sparse binary indicators (e.g. `City_Bangalore`, `City_Mumbai`).
- The feature metadata inspector groups these indicator columns back to the root attribute (`City`) at the individual record level before calculating global statistics.

### Classification Spaces
- **`RandomForestClassifier`**: Decomposed in `PROBABILITY_SPACE` ($P = \text{ref} + \sum \Delta$), where leaf voting shares telescope additively to class probabilities.
- **`GradientBoostingClassifier` & `LogisticRegression`**: Decomposed in `LOG_ODDS_MARGIN` space ($z = \text{ref} + \sum \Delta$), with explicit disclosures that non-linear sigmoid/softmax projections alter point-wise percentage interpretations.

### Forecast Trajectory Decompositions (`forecasting_explainer.py`)
- Analyzes trend slope ($\beta_1$), historical level baseline ($\alpha$), cyclic seasonal components, and empirical backtest coverage (percentage of holdout observations within nominal 80% and 95% intervals).

---

## 14. AI Business Explanation Layer & Non-Guarantee Safety Guardrails

Located in `backend/app/ai/explanation_service.py`, this layer translates verified mathematical outputs into structured, executive-ready narratives without hallucination:

### Core Safeguards
1. **Strict Evidence Boundary**: LLMs receive validated metrics and feature attributions in a canonical JSON format and are constrained to translate—never compute or invent—values.
2. **Clause-Level Syntactic Validation (`explanation_validator.py`)**:
   - Analyzes sentences at the sub-clause level.
   - Permits negative disclaimers (e.g., *"Forecast intervals represent statistical bounds, not a guaranteed outcome"*).
   - Rejects un-negated positive assertions of certainty (e.g., *"guaranteed outcome"*, *"100% certainty"*) and unverified causal claims (*"directly causes"*).
3. **Bounded Corrective Retries**:
   - If validation fails, up to 2 retries (3 total attempts) are performed.
   - Injects the specific validation error message into the subsequent prompt so the LLM explicitly corrects the policy violation.
4. **Deterministic Fallback Engine (`narrative_fallback.py`)**:
   - If the provider is offline, unreachable, or exhausts retries, a local deterministic engine synthesizes executive narratives using verified templates.
   - Sets `is_fallback: true` so the UI presents the narrative seamlessly without leaking technical error traces.
5. **SHA-256 Fingerprint Caching (`explanation_cache.py`)**:
   - Hashes canonical evidence JSON. Returns cached explanations in $< 5\text{ms}$.

---

## 15. Decision Intelligence Layer & Governance

Located in `backend/app/decisions/`, this layer translates ML predictions and forecasts into deterministic operational recommendations:

### Deterministic Rules Engine (`rules_engine.py`)
- Evaluates explicit conditions using comparison operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `is_present`, `is_missing`).
- Supports static thresholds (e.g. `available_inventory < 100`) and dynamic field comparisons (`forecast_peak > available_capacity`).
- Three-state evaluation: `TRIGGERED`, `NOT_TRIGGERED`, and `NOT_EVALUABLE` (missing fields or conflicting units).

### Zero-Retraining Evidence Collection (`evidence_collector.py`)
- Collects facts directly from model artifacts, forecasts, and dataset profiles on disk with zero retraining.

### Human-in-the-Loop Governance (`service.py`)
- Lifecycle: `needs_review` $\rightarrow$ `pending_approval` $\rightarrow$ `approved` $\rightarrow$ `completed`, or `rejected` / `dismissed`.
- **Mandatory Justification**: Rejections and dismissals strictly enforce a justification comment.
- **Audit Logging**: Every status transition is immutably logged with timestamp, user, previous status, new status, and comment in `data/decisions/audit_log.json`.

---

## 16. Prediqo AI Unified Question Router & Conversational Workspace

Located in `backend/app/ai/router.py` and `frontend/src/pages/PrediqoAIPage.tsx`:

- **Unified Entry Point**: A single chat interface accepting natural language business inquiries.
- **Intent Classifier**: Categorizes user requests into:
  - **`analytics`**: Directs to DuckDB direct Parquet execution.
  - **`prediction`**: Recommends supervised target modeling and single-record inference.
  - **`forecasting`**: Guides user toward temporal date/metric aggregation and future intervals.
  - **`decision`**: Recommends evaluating active operational business rules.
  - **`ambiguous`**: Solicits clarifying constraints with guided suggestion pills.

---

## 17. Unified 4-Tab Center UI Architecture

The frontend provides two unified enterprise centers with a consistent 4-tab layout:
1. **Prediction Center (`frontend/src/pages/PredictionPage.tsx`)**
2. **Forecasting Center (`frontend/src/pages/ForecastingPage.tsx`)**

### 4-Tab Invariants:
1. **`Overview`**: High-level KPIs, target definition, data health card, executive summary, and plain-English metric explanations.
2. **`Analytics`**: Interactive visual charts (Holdout Actual vs Predicted, Residuals, Confusion Matrix, Timeline Chart with historical actuals vs future projection).
3. **`AI Explanation`**: Business narratives, local feature driver cards, risk callouts, verification checklists, and audit drawer.
4. **`Technical Details`**: Candidate algorithm comparison leaderboards, CV metrics, training times, baseline uplifts, full projection tables, and exact XAI reconstruction logs.

### State Preservation:
Switching between tabs preserves all active models, evaluation metrics, and user configuration without re-fetching or resetting component state.
