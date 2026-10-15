# Prediqo — End-to-End Application & Scenario Guide
## Reference Dataset: `sample-ecommerce-orders` (`ds_95a4ec36`)

---

## 1. Executive Summary & Architectural Mental Model

**Prediqo** is a local-first, privacy-preserving AI data analytics, machine learning prediction, time-series forecasting, and decision intelligence platform. It runs completely locally with **zero mandatory cloud dependencies, no Docker containers, no external SQL servers, and no Celery/Redis queue daemons**.

### Core Philosophy: *"Prepare Once, Analyze Many Times"*
- **Decoupled Ingestion**: Raw data (.csv, .xlsx, Google Sheets, PostgreSQL) is read, typed, profiled, and translated into a standardized **Apache Parquet** file and a cached **JSON metadata dictionary** exactly once.
- **Direct Columnar Execution**: Downstream queries, charts, ML training, forecasting, and decision evaluations **never** re-read the original raw file or load the full dataset into in-memory pandas DataFrames. Instead, **DuckDB executes SQL directly against the on-disk Parquet file** with column pruning and filter push-down.
- **Strict Separation Between Math and Language**: All predictions, metrics, probabilities, feature attributions, and confidence intervals are computed deterministically via mathematical libraries (`scikit-learn`, `DuckDB`). The Large Language Model (LLM) is strictly a language synthesis and presentation layer governed by strict non-guarantee safety guardrails.

```text
Connect & Upload Data
        ↓  (Async ThreadPool Job)
Stage 1: Read → Stage 2: Clean → Stage 3: Profile → Stage 4: Semantic Inference → Stage 5: Parquet Write
        ↓
  [ READY Status ] (ds_95a4ec36.parquet + ds_95a4ec36.json)
        ↓
┌───────────────────────────────────────┬───────────────────────────────────────┐
│           ANALYTICAL PATH             │          INTELLIGENCE PATH            │
│  - Data Explorer (DuckDB Pagination)  │  - Supervised ML Prediction (K-Fold)  │
│  - AI Natural Language Router / Chat  │  - Time-Series Forecasting (date_trunc│
│  - DuckDB Column-Pruned Aggregation   │  - Exact Additive XAI Tree Paths      │
│  - Canonical SHA-256 Query Cache      │  - AI Business Explanations (Safety)  │
│  - Dynamic Query-Spec Dashboards      │  - Deterministic Rules & Human Review │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

---

## 2. The Reference Dataset: `sample-ecommerce-orders`

The dataset active in your system has `dataset_id = "ds_95a4ec36"`:
- **Total Records**: 50,000 rows
- **Total Columns**: 20 attributes
- **Storage**: `data/datasets/ds_95a4ec36.parquet` (~1.85 MB on disk, compressed from 6.64 MB CSV)
- **Metadata**: `data/metadata/ds_95a4ec36.json`

### Schema & Business Roles

| Column Name | Physical Dtype | Semantic Type | Business Role | Allowed Aggregations | Sample Values |
|---|---|---|---|---|---|
| `order_id` | `int64` | `ID` | `order_identifier` | `COUNT`, `DISTINCT_COUNT` | 1001, 1002 |
| `ordered_at` | `datetime64[ns]` | `DATE` | `date` | `COUNT`, `DISTINCT_COUNT`, `MIN`, `MAX` | 2024-01-15 10:24:00 |
| `customer_id` | `int64` | `MEASURE` | `customer_identifier` | `COUNT`, `DISTINCT_COUNT` | 1000, 1001 |
| `customer_email`| `object` | `TEXT` | `free_text` | `COUNT`, `DISTINCT_COUNT` | `customer1000@example.com` |
| `country` | `object` | `CATEGORY` | `geography` | `COUNT`, `DISTINCT_COUNT` | `US` (21,994), `GB`, `DE`, `CA`, `AU` |
| `channel` | `object` | `CATEGORY` | `channel` | `COUNT`, `DISTINCT_COUNT` | `Direct`, `Organic Search`, `Paid Social` |
| `device` | `object` | `CATEGORY` | `dimension` | `COUNT`, `DISTINCT_COUNT` | `Mobile`, `Desktop`, `Tablet` |
| `product_sku` | `object` | `CATEGORY` | `product_identifier` | `COUNT`, `DISTINCT_COUNT` | `SKU-8492`, `SKU-1029` |
| `product_category`| `object` | `CATEGORY`| `category` | `COUNT`, `DISTINCT_COUNT` | `Electronics`, `Apparel`, `Home` |
| `quantity` | `int64` | `MEASURE` | `quantity` | `SUM`, `AVG`, `MIN`, `MAX` | 1, 2, 4 |
| `unit_price` | `float64` | `MEASURE` | `unit_price` | `AVG`, `MIN`, `MAX` | $19.99, $149.50 |
| `discount_pct` | `float64` | `MEASURE` | `rate` | `AVG`, `MIN`, `MAX` | 0.0, 0.10, 0.25 |
| `shipping_cost` | `float64` | `MEASURE` | `cost` | `SUM`, `AVG`, `MIN`, `MAX` | $4.99, $12.50 |
| `currency` | `object` | `CATEGORY` | `dimension` | `COUNT`, `DISTINCT_COUNT` | `USD`, `EUR`, `GBP` |
| `payment_method`| `object` | `CATEGORY` | `payment_method` | `COUNT`, `DISTINCT_COUNT` | `Credit Card`, `PayPal`, `Apple Pay` |
| `status` | `object` | `CATEGORY` | `status` | `COUNT`, `DISTINCT_COUNT` | `Delivered`, `Cancelled`, `Returned`, `Pending` |
| `order_total` | `float64` | `MEASURE` | `monetary_amount` | `SUM`, `AVG`, `MIN`, `MAX` | $24.98, $349.00 |
| `is_first_order`| `int64` | `MEASURE` | `measure` | `AVG`, `SUM`, `COUNT` | 0, 1 |
| `refund_amount` | `float64` | `MEASURE` | `monetary_amount` | `SUM`, `AVG`, `MIN`, `MAX` | $0.00, $45.00 |
| `days_to_deliver`| `int64` | `MEASURE` | `duration` | `AVG`, `MIN`, `MAX` | 2, 5, 8, 14 |

---

## 3. Layer-by-Layer Architectural Overview

### Layer 1: Connectors & Ingestion Layer
- **Modules**: `backend/app/connectors/`, `backend/app/ingestion/`, `backend/app/jobs/`
- **Mechanism**:
  1. Uploads (.csv, .xlsx) or external pulls (PostgreSQL, Google Sheets) start an asynchronous background task managed by `ThreadPoolExecutor`.
  2. Sequential pipeline execution:
     - `READING` (0–20%): Reads source file chunks into streaming buffers.
     - `STANDARDIZING` (20–40%): Sanitizes column names (snake_case), parses ISO-8601 timestamps, infers physical datatypes.
     - `PROFILING` (40–60%): Measures cardinality, null percentages, min/max bounds, distribution histograms.
     - `SEMANTIC_ANALYSIS` (60–80%): Detects business roles (`order_identifier`, `monetary_amount`, `duration`) and computes allowable SQL aggregations.
     - `WRITING` (80–100%): Saves columnar Apache Parquet files (`data/datasets/ds_95a4ec36.parquet`) and stores complete JSON metadata (`data/metadata/ds_95a4ec36.json`).
  3. Status transitions to `READY`. Zero downtime on updates using version incrementing (`v1` $\rightarrow$ `v2`).

### Layer 2: Columnar Analytics & Data Exploration Layer
- **Modules**: `backend/app/query_engine/`, `backend/app/storage/dataset_store.py`, `backend/app/cache/query_cache.py`
- **Mechanism**:
  - Uses **DuckDB** in-process engine.
  - Queries execute SQL directly on Parquet: `read_parquet('data/datasets/ds_95a4ec36.parquet')`.
  - **Column Pruning**: If asking for revenue by country, only `country` and `order_total` columns are read from disk; the other 18 columns are ignored.
  - **Filter Push-Down**: `WHERE status = 'Delivered'` skips Parquet row groups whose metadata indicates no matching values.
  - **Query Caching**: Evaluates canonical SHA-256 hash `sha256(dataset_id + version + normalized_sql)`. Cached hits return in `< 8ms`.

### Layer 3: AI Natural Language Router & Analyst Layer
- **Modules**: `backend/app/ai/router.py`, `backend/app/ai/analyst.py`, `backend/app/ai/query_planner.py`
- **Mechanism**:
  - User natural language queries (e.g. *"What is the average order total by product category?"*) hit `/api/ai/route`.
  - The router determines intent:
    - **`analytics`**: Generates a structured aggregation plan (`group_by=["product_category"]`, `metric="order_total"`, `agg="avg"`).
    - **`prediction`**: Routes to Supervised ML prediction pipeline.
    - **`forecasting`**: Routes to temporal forecasting pipeline.
    - **`decision`**: Routes to decision rules evaluation.
  - **Semantic Validation**: Query planner verifies against `allowed_aggregations`. Attempting `SUM(order_id)` or `AVG(customer_email)` is rejected by the schema validator before execution.

### Layer 4: Supervised ML Prediction Center
- **Modules**: `backend/app/prediction/`
- **Mechanism**:
  - **Target Detection**: Automatic detection of regression targets (`days_to_deliver`, `order_total`, `refund_amount`) and classification targets (`status`, `payment_method`, `channel`, `is_first_order`).
  - **Feature Selector & Leakage Guard**: Automatically excludes identifier columns (`order_id`, `customer_id`, `customer_email`) and warns against target proxies (e.g. `refund_amount` when predicting `status = 'Returned'`).
  - **Model Training**: Evaluates multiple candidates (`LinearRegression`/`LogisticRegression`, `RandomForest`, `HistGradientBoosting`) using **5-Fold Cross Validation** and a 20% holdout test set.
  - **Baseline Benchmark**: Automatically benchmarks against `DummyRegressor` (mean) or `DummyClassifier` (stratified mode).

### Layer 5: Time-Series Forecasting Intelligence Center
- **Modules**: `backend/app/forecasting/`
- **Mechanism**:
  - Automatically identifies temporal columns (`ordered_at`) and continuous numeric metrics (`order_total`, `quantity`, `shipping_cost`).
  - **Temporal Aggregation**: Uses DuckDB's `date_trunc('day', ordered_at)` to aggregate transaction rows into regular daily/weekly time series.
  - **Chronological Backtesting**: Splits data chronologically without random shuffling (train on past, evaluate on subsequent $H$ periods).
  - **Candidate Forecasters**: Evaluates Naive baseline, Seasonal Naive (7-day cycles), Moving Average, Linear Trend Regression, and Simple Exponential Smoothing (SES).
  - **Uncertainty Intervals**: Calculates empirical 80% and 95% forecast intervals based on historical residual variance.

### Layer 6: Explainable AI (XAI) Mathematical Decomposition
- **Modules**: `backend/app/explainability/`
- **Mechanism**:
  - **Exact Local Additive Attribution**: Decomposes individual predictions into reference base value $Y_0$ and signed feature shifts $\Delta_j$:
    $$\hat{y}(x) = Y_0 + \sum \Delta_j(x)$$
  - **Exact Tree Path Telescoping Sums**: For Random Forest and Gradient Boosting, traces the exact decision node splits for each tree without approximation error ($< 10^{-14}$).
  - **Grouped Categorical Attribution**: Automatically rolls up one-hot encoded dummy columns (`country_US`, `country_DE`) into the single intuitive parent attribute `country`.
  - **Forecast Trajectory XAI**: Decomposes forecast series into base level, trend slope ($\beta_1$), seasonal cycle adjustments, and backtest error bounds.

### Layer 7: AI Business Explanation Layer & Safety Guardrails
- **Modules**: `backend/app/ai/explanation_service.py`, `backend/app/ai/explanation_validator.py`
- **Mechanism**:
  - Translates verified numbers into plain-English executive summaries and actionable driver bullet points.
  - **Non-Guarantee & Causal Guardrails**:
    - Rejects assertions of 100% certainty or guaranteed business results.
    - Permits valid statistical disclaimers (e.g. *"Intervals reflect past historical patterns, not guaranteed future revenue"*).
    - Prohibits ungrounded causal claims (e.g. *"Discounting directly causes higher delivery delays"*).
  - **Bounded Corrective Retries**: If the LLM generates a prohibited phrase, the validator catches it and prompts the model with corrective feedback (up to 2 retries).
  - **Deterministic Local Fallback**: If the LLM fails or is unavailable, `narrative_fallback.py` synthesizes compliant business narratives offline with 0 latency.

### Layer 8: Decision Intelligence Layer & Governance
- **Modules**: `backend/app/decisions/`
- **Mechanism**:
  - **Deterministic Rules Engine**: AST-free, zero-eval comparison rules evaluating explicit conditions (`gt`, `lt`, `eq`, `in`) over model predictions, forecasts, and dataset facts.
  - **Evidence Collector**: Extracts parameters directly from models and profiles on disk without re-running training.
  - **Human-in-the-Loop Workflow**: Recommendations require human review with statuses: `needs_review` $\rightarrow$ `pending_approval` $\rightarrow$ `approved` $\rightarrow$ `completed` (or `rejected`/`dismissed`).
  - **Mandatory Justification**: Rejection or dismissal strictly requires a human reason comment. Every transition is immutably recorded in `data/decisions/audit_log.json`.

### Layer 9: Visual Dashboards & UI Experience
- **Modules**: `frontend/src/` (React 19, TypeScript, Tailwind CSS, Recharts)
- **Mechanism**:
  - **Unified Centers**: 4-tab interface for Prediction and Forecasting (Overview, Analytics, AI Explanation, Technical Details).
  - **Dynamic Dashboards**: Pins query specifications rather than static data snapshots; charts refresh dynamically via DuckDB.
  - **Data Explorer**: High-performance paginated table powered by DuckDB server-side limits and offsets.

---

## 4. End-to-End Scenarios with `sample-ecommerce-orders`

### Scenario 1: Data Ingestion & Semantic Profiling

#### Business Context
The operations manager uploads `sample-ecommerce-orders.csv` containing 50,000 transaction records.

#### End-to-End Flow
1. **User Action**: The user selects the file on `/data-sources` and clicks "Upload & Prepare".
2. **REST API Call**: `POST /api/ingestion/jobs` (multipart form-data).
3. **Backend Execution**:
   - `JobManager` generates `job_id = "job_3f82a1"`, registers status `QUEUED`, and returns `job_id` within 10ms.
   - Background thread executes `execute_ingestion_pipeline`:
     - Reads CSV into temporary DataFrame.
     - Converts column names to snake_case (`Order ID` $\rightarrow$ `order_id`, `Days to Deliver` $\rightarrow$ `days_to_deliver`).
     - Detects `ordered_at` as ISO timestamp and converts to `datetime64[ns]`.
     - Identifies `order_id` as primary identifier (50,000 unique values across 50,000 rows).
     - Identifies `days_to_deliver` as numeric duration with allowed aggregations `AVG`, `MIN`, `MAX`.
     - Writes `data/datasets/ds_95a4ec36.parquet` using Snappy compression.
     - Writes `data/metadata/ds_95a4ec36.json` with column profiles, business roles, and semantic mappings.
   - Job stage updates: `READING` $\rightarrow$ `STANDARDIZING` $\rightarrow$ `PROFILING` $\rightarrow$ `SEMANTIC_ANALYSIS` $\rightarrow$ `WRITING` $\rightarrow$ `READY`.
4. **Frontend Experience**: The UI polls `GET /api/ingestion/jobs/job_3f82a1` every 500ms, displaying progress animated bars and stage checklists until completion.

---

### Scenario 2: Conversational Analytics & Exploratory Queries

#### Business Question
*"What is the total revenue and average delivery days across different product categories for orders shipped to the US?"*

#### End-to-End Flow
1. **User Action**: User types the question into the Prediqo AI prompt bar on `/analyst` or `/chat`.
2. **REST API Call**: `POST /api/ai/route` $\rightarrow$ routed to `POST /api/ai/analyze`.
   ```json
   {
     "dataset_id": "ds_95a4ec36",
     "question": "What is the total revenue and average delivery days across different product categories for orders shipped to the US?"
   }
   ```
3. **Backend Execution**:
   - `QueryPlanner` loads `data/metadata/ds_95a4ec36.json` (no parquet read).
   - Generates structured query plan:
     - `group_by`: `["product_category"]`
     - `metric`: `"order_total"`
     - `aggregation`: `"sum"`
     - `filters`: `[{"column": "country", "op": "eq", "value": "US"}]`
   - `QueryValidator` checks semantic rules: `order_total` has business role `monetary_amount` which allows `SUM`. `country` exists in dataset.
   - Computes canonical SHA-256 query hash. Checks `data/cache/query/`.
   - **Cache Miss**: DuckDB executes directly over Parquet:
     ```sql
     SELECT "product_category", SUM("order_total") AS "order_total"
     FROM read_parquet('data/datasets/ds_95a4ec36.parquet')
     WHERE lower("country") = 'us'
     GROUP BY "product_category"
     ORDER BY "order_total" DESC
     ```
   - Execution finishes in **18.4 ms** (reading only `product_category`, `order_total`, and `country`).
   - `ChartRecommender` inspects categorical dimension + single measure $\rightarrow$ recommends `bar` chart.
   - Persists result into `data/cache/query/{hash}.json`.
4. **Frontend Experience**: Renders an interactive Recharts Bar Chart showing revenue by category (e.g. *Electronics: $1,420,500*, *Apparel: $890,200*) along with automated bullet insights and execution pills (`DuckDB: 18ms | Cache: Miss`).
5. **Subsequent Query**: Asking the exact same question triggers a cache hit returning in **6.2 ms** (`Cache: Hit`).

---

### Scenario 3: Supervised ML Prediction — Delivery Delay Risk

#### Business Problem
Predict the delivery duration (`days_to_deliver`) for incoming orders so the logistics team can identify orders at risk of taking longer than 7 days.

#### End-to-End Flow
1. **User Action**: On `/prediction`, user selects `sample-ecommerce-orders`, chooses target `days_to_deliver` (Regression), and clicks "Train & Evaluate".
2. **REST API Calls**:
   - `GET /api/prediction/feasibility/ds_95a4ec36`:
     - Checks row count (50,000 $\ge$ 50 threshold $\rightarrow$ OK).
     - Confirms `days_to_deliver` has continuous numeric distribution ($\min=1, \max=14, \text{mean}=5.2$).
     - Returns recommended features: `country`, `channel`, `device`, `product_category`, `quantity`, `unit_price`, `shipping_cost`, `order_total`, `is_first_order`.
     - Excludes `order_id`, `customer_id`, `customer_email`.
   - `POST /api/prediction/train`:
     ```json
     {
       "dataset_id": "ds_95a4ec36",
       "target_column": "days_to_deliver",
       "problem_type": "regression",
       "feature_columns": ["country", "product_category", "quantity", "shipping_cost", "order_total", "channel", "device"]
     }
     ```
3. **Backend Execution**:
   - DuckDB extracts only the requested 8 columns: `SELECT days_to_deliver, country, ... FROM read_parquet(...)`.
   - `ColumnTransformer` pipelines:
     - Numerical (`order_total`, `shipping_cost`, `quantity`): `StandardScaler` + `SimpleImputer(strategy='median')`.
     - Categorical (`country`, `product_category`, `channel`, `device`): `OneHotEncoder(handle_unknown='ignore')`.
   - Evaluates candidate models via 5-Fold Cross Validation:
     - *Ridge Regression*: MAE = 1.84 days
     - *Random Forest Regressor*: MAE = 1.32 days
     - *Gradient Boosting Regressor*: MAE = 1.28 days (Winner)
     - *Baseline Dummy (Mean)*: MAE = 2.65 days
   - Calculates relative baseline uplift: **+51.7% accuracy improvement over baseline**.
   - Persists trained scikit-learn pipeline to `data/models/model_pred_95a4e/model.joblib`.
   - Saves model metadata JSON with feature names, CV metrics, and residual distribution.
4. **Frontend Experience**: The user views the **Prediction Center**:
   - **Overview Tab**: KPI cards showing Winning Algorithm (*Gradient Boosting*), Test MAE (*1.28 days*), Baseline Uplift (*+51.7%*).
   - **Analytics Tab**: Interactive *Actual vs Predicted Scatter Plot* and *Residual Error Distribution Histogram*.
   - **Technical Details Tab**: Full leaderboard comparing Ridge, Random Forest, and Gradient Boosting.

---

### Scenario 4: Live Single-Record Inference with Exact XAI

#### Business Problem
An order arrives from `country = 'AU'`, `product_category = 'Electronics'`, `shipping_cost = $4.99`, `order_total = $340.00`. The merchant wants to know the predicted delivery time and the exact reasons behind the estimate.

#### End-to-End Flow
1. **User Action**: In the "Test Prediction" drawer on `/prediction`, the user inputs:
   `country: AU`, `product_category: Electronics`, `shipping_cost: 4.99`, `order_total: 340.00`, `quantity: 2`, `channel: Direct`, `device: Mobile`.
2. **REST API Call**: `POST /api/prediction/predict`:
   ```json
   {
     "model_id": "model_pred_95a4e",
     "features": {
       "country": "AU",
       "product_category": "Electronics",
       "shipping_cost": 4.99,
       "order_total": 340.00,
       "quantity": 2,
       "channel": "Direct",
       "device": "Mobile"
     }
   }
   ```
3. **Backend Execution**:
   - `PredictionService` loads `model.joblib`.
   - Runs pipeline transform and model predict: $\hat{y} = 8.42\text{ days}$.
   - Triggers `LocalExplainer` (`backend/app/explainability/local_explainer.py`):
     - Calculates base reference value $Y_0 = 5.20\text{ days}$ (global mean).
     - Traces decision tree paths for each decision tree in the ensemble:
       - `country = 'AU'` $\rightarrow$ $+2.15\text{ days}$ (major shipping distance to Australia).
       - `shipping_cost = 4.99` (standard/economy) $\rightarrow$ $+1.10\text{ days}$ (economy tier adds transit time).
       - `product_category = 'Electronics'` $\rightarrow$ $-0.35\text{ days}$ (regional warehouse priority).
       - `order_total = 340.00` $\rightarrow$ $+0.32\text{ days}$ (customs check threshold).
     - Total exact decomposition:
       $$\hat{y} = 5.20 + 2.15 + 1.10 - 0.35 + 0.32 = 8.42\text{ days}$$
     - Machine reconstruction error: $0.00000000000000\text{ days}$.
4. **Frontend Experience**: The user sees:
   - Prediction badge: **8.4 Days (High Delay Risk)**
   - Waterfall chart illustrating how base reference (5.2 days) increases to 8.4 days, highlighting `country: AU (+2.15 days)` and `shipping_cost: $4.99 (+1.10 days)` in red.

---

### Scenario 5: Time-Series Forecasting — 30-Day Revenue Outlook

#### Business Problem
The finance team needs a 30-day forecast of daily revenue (`order_total`) along with risk intervals to allocate inventory and customer support capacity.

#### End-to-End Flow
1. **User Action**: On `/forecasting`, user selects `ordered_at` as the Date Column, `order_total` as the Metric, aggregation `SUM`, frequency `Daily`, horizon `30`, and clicks "Generate Forecast".
2. **REST API Calls**:
   - `GET /api/forecast/feasibility/ds_95a4ec36`:
     - Discovers date bounds (`2024-01-01` to `2024-12-31`, 365 daily periods).
     - Checks period count ($365 \ge 14$ required threshold $\rightarrow$ OK).
   - `POST /api/forecast/train`:
     ```json
     {
       "dataset_id": "ds_95a4ec36",
       "date_column": "ordered_at",
       "metric_column": "order_total",
       "frequency": "daily",
       "aggregation": "SUM",
       "horizon": 30
     }
     ```
3. **Backend Execution**:
   - DuckDB aggregates 50,000 transaction rows directly from Parquet:
     ```sql
     SELECT CAST(date_trunc('day', CAST("ordered_at" AS TIMESTAMP)) AS DATE) AS ds,
            SUM(CAST("order_total" AS DOUBLE)) AS y
     FROM read_parquet('data/datasets/ds_95a4ec36.parquet')
     WHERE "ordered_at" IS NOT NULL AND "order_total" IS NOT NULL
     GROUP BY ds ORDER BY ds ASC
     ```
   - Chronological split: First 335 days for training; last 30 days for holdout evaluation.
   - Evaluates candidate algorithms on the 30-day holdout:
     - *Naive Benchmark*: WAPE = 18.4%
     - *Moving Average (7-day)*: WAPE = 14.2%
     - *Seasonal Naive (7-day weekly)*: WAPE = 9.8% (Winner)
     - *Linear Trend Regression*: WAPE = 16.5%
     - *Exponential Smoothing (SES)*: WAPE = 12.1%
   - Selects **Seasonal Naive** (+46.7% accuracy improvement over baseline Naive).
   - Projects 30 future days with empirical standard error bounds:
     - 80% interval: $\hat{y} \pm 1.28 \cdot \sigma$
     - 95% interval: $\hat{y} \pm 1.96 \cdot \sigma$
   - Persists forecast model and projection points to `data/models/forecast_fc_95a4e/`.
4. **Frontend Experience**: The user views the **Forecasting Center**:
   - **Timeline Chart**: Seamless Recharts visual showing 365 days of solid historical revenue, joined smoothly to 30 days of projected values surrounded by shaded 80% and 95% uncertainty interval bands.
   - **Metric Cards**: WAPE (9.8%), MAE ($1,240), Baseline Uplift (+46.7%).

---

### Scenario 6: AI Business Explanation Generation with Safety Guardrails

#### Business Context
The executive team needs a summary of the 30-day forecast to present to stakeholders.

#### End-to-End Flow
1. **User Action**: User clicks the "AI Explanation" tab in the Forecasting Center.
2. **REST API Call**: `POST /api/ai/explain/forecast`:
   ```json
   {
     "model_id": "fc_95a4e",
     "dataset_id": "ds_95a4ec36"
   }
   ```
3. **Backend Execution**:
   - `ExplanationService` checks `data/cache/explanations/` via SHA-256 fingerprint.
   - On cache miss: Constructs a strictly grounded prompt containing exact mathematical facts:
     - Metric: Daily Revenue (`order_total`)
     - Model: Seasonal Naive (7-day weekly pattern)
     - Accuracy: WAPE 9.8% (outperformed Naive by 46.7%)
     - Projection Average: $14,250/day
     - 95% Interval: [$11,800, $16,700]
     - Strict Instruction: *"Never state that outcomes are guaranteed. Use probabilistic language."*
   - LLM generates response:
     > *"Based on historical 7-day cyclical patterns, revenue is projected to average approximately $14,250 per day over the next 30 days. These statistical bounds indicate expected revenue between $11,800 and $16,700 under normal market conditions, though these intervals represent statistical likelihood rather than a guaranteed outcome."*
   - `ExplanationValidator` inspects the text:
     - Checks for prohibited positive assertions: No matches found.
     - Detects negative disclaimer (*"represent statistical likelihood rather than a guaranteed outcome"*): Validated and approved.
     - Caches narrative to disk.
4. **Frontend Experience**: The user reads the narrative with verified KPI badges, Driver Highlights, and an "Enterprise Safety Checklist" verifying all claims are grounded in mathematical evidence.

---

### Scenario 7: Decision Layer — Autonomous Recommendation & Human Approval

#### Business Problem
Automate policy interventions when forecasted demand drops or delivery delay risks surge.

#### End-to-End Flow
1. **Initial Setup (Rules Engine)**:
   A business rule exists in `data/decisions/rules.json`:
   - **Rule ID**: `rule_shipping_delay_warning`
   - **Condition**: `days_to_deliver.predicted_value > 7.0` AND `country == 'AU'`
   - **Action**: *"Reroute Australian orders over $300 to Express Air Courier to meet 5-day SLA."*
   - **Priority**: `HIGH`
2. **Evaluation Trigger**:
   - `POST /api/decisions/evaluate`:
     ```json
     {
       "scenario": "logistics_sla_protection",
       "prediction_model_id": "model_pred_95a4e",
       "dataset_id": "ds_95a4ec36",
       "inputs": {"country": "AU", "order_total": 340.0}
     }
     ```
   - Rules Engine runs deterministic evaluation:
     - Input facts: `predicted_value = 8.42`, `country = 'AU'`.
     - Condition `8.42 > 7.0` is `True`. Condition `'AU' == 'AU'` is `True`.
     - Rule Status: **`TRIGGERED`**.
   - Generates recommendation `rec_8f39b1` with status `needs_review`.
3. **Human Governance Workflow**:
   - Logistics manager visits `/decisions/recommendations`.
   - Clicks recommendation `rec_8f39b1` to review evidence (predicted transit time 8.42 days, delay driver: Australian customs and economy shipping).
   - Manager updates status:
     - **Option A (Approval)**: Clicks "Approve". Status transitions to `approved`.
     - **Option B (Rejection)**: Clicks "Reject". The modal requires a mandatory comment. The manager enters: *"Customs fast-track already active for AU Q4."* Status transitions to `rejected`.
   - Every action logs an immutable event in `data/decisions/audit_log.json`:
     ```json
     {
       "timestamp": "2026-10-15T11:20:00Z",
       "recommendation_id": "rec_8f39b1",
       "previous_status": "needs_review",
       "new_status": "rejected",
       "user": "logistics_manager",
       "comment": "Customs fast-track already active for AU Q4."
     }
     ```
4. **Frontend Experience**: Decision Center displays live counters (*Active Recommendations: 1, Needs Review: 0, Rejected: 1*), along with a searchable compliance audit drawer.

---

### Scenario 8: Dynamic Dashboard Monitoring & Chart Pinning

#### Business Context
Create an Executive Operations Dashboard monitoring revenue, channels, and shipping performance.

#### End-to-End Flow
1. **User Action**: In the Chart Builder (`/chart-builder`), user configures:
   - Chart 1: Bar Chart of `order_total` (SUM) by `channel`.
   - Chart 2: Line Chart of `order_total` (SUM) by `ordered_at` (Monthly).
   - Chart 3: Pie Chart of `order_id` (COUNT) by `status`.
2. **Pinning to Dashboard**:
   - User clicks "Pin to Dashboard".
   - `POST /api/dashboards/default/charts` persists the **Query Specification** (not static rows):
     ```json
     {
       "title": "Revenue by Channel",
       "chart_type": "bar",
       "dataset_id": "ds_95a4ec36",
       "query_spec": {
         "group_by": ["channel"],
         "metric": "order_total",
         "aggregation": "sum"
       }
     }
     ```
3. **Viewing the Dashboard**:
   - When the user visits `/dashboards`, the dashboard fetches the query specifications.
   - The backend checks `QueryCache` or executes DuckDB Parquet queries in parallel.
   - All charts render in `< 30ms` total screen load time.
4. **Zero-Downtime Dataset Refresh**:
   - When new transaction rows arrive, `POST /api/datasets/ds_95a4ec36/refresh` runs in the background.
   - The dataset version increments from `v1` $\rightarrow$ `v2`.
   - The old query cache keys for `v1` expire automatically.
   - The next dashboard visit re-executes the query specs over the updated `v2` Parquet file, refreshing all metrics.

---

## 5. Troubleshooting & Operational Guide

| Symptom / Error | Root Cause | Solution |
|---|---|---|
| `OSError: Invalid argument: .../*.parquet` | Code passed unexpanded wildcard pattern to `pd.read_parquet()`. | Use `ParquetPath` and `pd.read_parquet(glob.glob(...))` as implemented in `dataset_store.py`. |
| `[WinError 123] The filename syntax is incorrect` | Called `path.unlink()` on wildcard pattern `*.parquet` during dataset deletion. | Use `ParquetPath.unlink(missing_ok=True)` which unlinks matching files and cleans up directories. |
| Query returns HTTP 400: *"Cannot SUM column order_id"* | Semantic guardrail violation. `order_id` has business role `order_identifier`. | Use `COUNT` or `DISTINCT_COUNT` for identifiers. |
| Prediction feasibility warning: *"High Cardinality Categorical"* | A categorical column (like `customer_email` or `product_sku`) has thousands of unique strings. | Exclude high-cardinality IDs from feature selection; retain category groupings (e.g. `product_category`). |
| Forecasting MAPE displays as `undefined` | The series contains zero values (e.g. days with zero returns). | Prediqo suppresses division-by-zero distortion; use WAPE or MAE instead. |
| AI explanation shows *"Deterministic Fallback Narrative"* | Local Ollama is offline or Cloud API key is unset. | Normal behavior. Prediqo safely falls back to local deterministic templates without failing. |
| Recommendation status change rejected | Attempted to reject or dismiss a recommendation without a comment. | Provide a justification comment in the review modal as required by governance rules. |

---

## 6. Summary Checklist

- [x] **Reference Dataset**: `sample-ecommerce-orders` (`ds_95a4ec36`), 50,000 rows, 20 columns.
- [x] **Ingestion Decoupled**: Single preparation step, background ThreadPool, zero-downtime refresh.
- [x] **Analytics**: DuckDB queries Parquet directly with column pruning and SHA-256 query caching.
- [x] **Prediction**: Supervised ML with K-Fold CV, leakage detection, and baseline comparisons.
- [x] **Forecasting**: Temporal DuckDB aggregation, chronological backtesting, Naive benchmark, 80%/95% intervals.
- [x] **Explainability**: Exact additive tree paths and grouped categorical attribution.
- [x] **Safety**: Non-guarantee policy validation, negation disclaimer detection, bounded retries.
- [x] **Governance**: Deterministic rules engine, human review states, mandatory comments, and audit trail.
- [x] **Unified UI**: 4-tab Prediction & Forecasting Centers, Data Explorer, Dynamic Dashboards.
