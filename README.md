# Prediqo — AI Data Analytics & Decision Intelligence Platform

A local-first AI data analytics, machine learning prediction, time-series forecasting, and decision intelligence platform inspired by Julius AI, Tellius, and Databricks.

Prediqo provides an end-to-end analytics workflow:

```text
Connect Data → Prepare Once (Async Job) → Explore Data (DuckDB Paginated)
             → Ask Questions (Prediqo AI Router / NLP) → Analyze Parquet (DuckDB)
             → Predict & Forecast (Supervised ML & Time Series)
             → Explain Results (Exact XAI & AI Narratives)
             → Decide & Govern (Deterministic Rules & Approvals)
```

**Core Philosophy**:
> **"Prepare the data once, analyze it many times."**  
> Ingestion is completely decoupled from the query and modeling paths. Asking questions, running predictions, generating forecasts, or evaluating decision rules never re-reads raw source files, re-profiles columns, or instantiates raw DataFrames into memory.

No Docker, no external database, no Celery/Redis, no mandatory cloud API keys — everything runs locally with local-file storage, in-process DuckDB columnar querying, and deterministic fallback engines.

---

## Documentation & Living Context

- **[CONTEXT.md](CONTEXT.md)** — Living context document covering mental model, component responsibilities, API contracts, and troubleshooting guide.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Architectural blueprint covering modular monolith design, background ingestion jobs, DuckDB direct Parquet execution, query caching, ML/forecasting pipelines, and benchmarks.
- **[docs/ANALYTICS.md](docs/ANALYTICS.md)** — Analytical engine architecture covering DuckDB direct Parquet execution, query caching, semantic guardrails, and dynamic dashboards.
- **[docs/PREDICTION.md](docs/PREDICTION.md)** — Supervised machine learning prediction guide covering target detection, candidate algorithms, cross-validation, holdout evaluation, residuals, and live inference.
- **[docs/FORECASTING.md](docs/FORECASTING.md)** — Time-series forecasting intelligence guide covering DuckDB temporal aggregation, candidate forecasters, chronological backtesting, and uncertainty intervals.
- **[docs/DECISION_LAYER_GUIDE.md](docs/DECISION_LAYER_GUIDE.md)** — Decision Layer architectural guide covering deterministic rules engine, evidence collection, recommendation store, and human-in-the-loop approvals.
- **[docs/AI_EXPLANATIONS.md](docs/AI_EXPLANATIONS.md)** — AI business explanation guide covering multi-provider LLMs, local Ollama, non-guarantee safety guardrails, corrective retries, and deterministic offline fallbacks.
- **[docs/EXPLAINABILITY.md](docs/EXPLAINABILITY.md)** — Explainable AI (XAI) guide covering exact tree path decomposition, grouped one-hot categoricals, and forecast trajectory decompositions.
- **[docs/BUSINESS_PREDICTION_GUIDE.md](docs/BUSINESS_PREDICTION_GUIDE.md)** — Plain-English operational guide for business users, managers, and analysts.
- **[docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)** — Engineering guide for setup, running tests, adding connectors, candidate models, decision rules, and benchmarks.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, TypeScript, Vite 8, Tailwind CSS, Recharts 3, Lucide Icons |
| **Backend** | Python 3.13, FastAPI, Uvicorn |
| **Analytics Engine**| DuckDB executing directly over Parquet files with column pruning and filter push-down |
| **Job Engine** | In-process `ThreadPoolExecutor` with persistent JSON job tracking (`data/jobs/`) |
| **Cache Engine** | File-based Canonical SHA-256 Query Cache (`data/cache/query/`) and In-Memory XAI/AI Cache |
| **Prediction Engine**| `scikit-learn` (Linear Regression, Logistic Regression, Random Forest, Gradient Boosting) |
| **Forecasting Engine**| DuckDB `date_trunc`, Naive, Seasonal Naive, Moving Average, Linear Trend, Exponential Smoothing |
| **Explainable AI (XAI)**| Exact decision tree path telescoping sums, linear coefficient attributions, forecast decompositions |
| **AI Explanation Layer**| Multi-provider LLMs (Ollama, OpenAI, Groq, Gemini, Anthropic) + Deterministic Fallback Engine |
| **Decision Layer**| Deterministic AST-free rules engine, evidence collector, human review & approval workflow |
| **Storage** | Local filesystem (`data/uploads`, `data/datasets`, `data/metadata`, `data/models`, `data/decisions`, `data/cache`) |

---

## Project Structure

```text
prediqo-v2/
├── CONTEXT.md                       # Living context document
├── README.md                        # Project overview and quickstart
├── docs/                            # In-depth architectural & operational guides
│   ├── ARCHITECTURE.md              # In-depth architectural blueprint
│   ├── ANALYTICS.md                 # DuckDB analytics engine & semantic guardrails
│   ├── PREDICTION.md                # Supervised ML prediction layer
│   ├── FORECASTING.md               # Time-series forecasting intelligence layer
│   ├── DECISION_LAYER_GUIDE.md      # Deterministic decision rules & human governance
│   ├── AI_EXPLANATIONS.md           # Business explanation layer & non-guarantee safety
│   ├── EXPLAINABILITY.md            # Exact additive XAI decompositions & tree paths
│   ├── BUSINESS_PREDICTION_GUIDE.md # Plain-English user guide
│   └── DEVELOPMENT_GUIDE.md         # Developer guide and extension recipes
├── scripts/
│   ├── generate_sample_data.py      # Generates sample e-commerce CSV
│   ├── benchmark_large_dataset.py   # Benchmark script for 100k and 1M rows
│   ├── benchmark_results.json       # Persisted benchmark metrics
│   └── verify_acceptance_workflow.py# 10-step Section 35 acceptance workflow verification
├── backend/
│   ├── requirements.txt             # Pinned requirements
│   ├── requirements-flex.txt        # Recommended flexible requirements
│   ├── tests/                       # 156 automated test cases (all passing)
│   └── app/
│       ├── main.py                  # FastAPI entrypoint, middleware & CORS
│       ├── api/routes.py            # Core REST API endpoints
│       ├── core/config.py           # Directory configurations
│       ├── models/                  # DatasetStatus, DatasetMetadata, schemas
│       ├── jobs/                    # Asynchronous ingestion job subsystem
│       ├── ingestion/               # Decoupled data preparation pipeline
│       ├── storage/                 # Parquet dataset & query-spec dashboard stores
│       ├── cache/                   # Canonical SHA-256 query cache
│       ├── query_engine/            # DuckDB direct Parquet analytics & NL parser
│       ├── standardization/         # Cleaning, profiling, and semantic intelligence
│       ├── capabilities/            # Centralized schema flexibility & capability registry
│       ├── prediction/              # Supervised ML prediction layer
│       ├── forecasting/             # Time-series forecasting intelligence layer
│       ├── explainability/          # Exact additive XAI decompositions
│       ├── decisions/               # Deterministic Decision Layer & Rules Engine
│       ├── connectors/              # CSV, Excel, Google Sheets, Postgres
│       └── ai/                      # AI analyst, question router, explanation service
└── frontend/
    ├── package.json                 # React dependencies & scripts
    ├── vite.config.ts               # Vite configuration with /api reverse proxy
    ├── tests/                       # 29 frontend business & unit test cases (all passing)
    └── src/
        ├── pages/                   # Unified Prediction & Forecasting Centers, Decision Center, AI Chat
        ├── components/              # 4-tab components, visual cards, charts, and modals
        ├── services/                # Axios API clients
        ├── types/                   # TypeScript schemas
        └── charts/                  # Recharts visualizer
```

---

## Running Locally

### 1. Backend (port 8000)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-flex.txt
pip install pytest httpx
uvicorn app.main:app --reload --port 8000
```

- Interactive API documentation (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 2. Frontend (port 5173)

```powershell
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) — Vite proxies `/api/*` to the FastAPI backend.

### 3. Optional: Local Ollama (Zero API Keys)

To run business explanations locally without cloud API keys:
```powershell
ollama serve
ollama run llama3.2
```
When Ollama is offline or unconfigured, Prediqo automatically uses its built-in deterministic fallback engine with zero downtime or error leaks.

### 4. Sample Data

An e-commerce dataset (`data/uploads/ecommerce_sales.csv`, 50 rows × 18 columns) is included. Regenerate it anytime with:

```powershell
python scripts/generate_sample_data.py
```

---

## Key Architecture & Features

### 1. Decoupled Ingestion Pipeline & Job System
- File uploads return immediately with an `IngestionJob` (`QUEUED`).
- Background worker processes data through sequential stages:
  `READING` $\rightarrow$ `STANDARDIZING` $\rightarrow$ `PROFILING` $\rightarrow$ `SEMANTIC_ANALYSIS` $\rightarrow$ `WRITING` $\rightarrow$ `READY`.
- The frontend monitors the job in real time with an interactive visual checklist and progress bar.

### 2. Dataset Lifecycle & Zero-Downtime Refresh
- Dataset states: `CREATING`, `PROCESSING`, `READY`, `FAILED`, `STALE`.
- Version counter begins at `v1`. Triggering `POST /api/datasets/{id}/refresh` prepares `v2` in the background using a staged file.
- The existing `v1` dataset remains queryable with **zero downtime** while the refresh runs.

### 3. Direct DuckDB Parquet Analytics
- DuckDB executes SQL queries directly on Parquet files (`CREATE VIEW t AS SELECT * FROM read_parquet(...)`).
- **Column Pruning**: Queries scan only needed dimensions and aggregated metrics.
- **Filter Push-Down**: SQL `WHERE` clauses skip irrelevant Parquet row groups.
- **Server-Side Pagination**: Data Explorer fetches only requested page rows (`LIMIT {page_size} OFFSET {offset}`) via DuckDB.

### 4. Deterministic Query Cache
- Normalizes and hashes `(dataset_id, version, canonical_query)` via SHA-256.
- Cached queries return sub-10ms results with `cache_hit: true`.
- Dataset version bumps automatically invalidate stale caches.

### 5. Unified Prediction Center & Forecasting Center UI
- Consistent 4-tab enterprise architecture across both centers:
  - **Overview**: High-level KPIs, target definitions, data health cards, and plain-English summaries.
  - **Analytics**: Holdout Actual vs Predicted charts, residuals scatter, confusion matrix, timeline charts (historical actuals vs projected future).
  - **AI Explanation**: Executive narratives, local driver attributions, risk callouts, verification checklists, and audit drawer.
  - **Technical Details**: Algorithm leaderboard, cross-validation metrics, baseline uplifts, full projection schedules, and exact XAI reconstruction logs.

### 6. Explainable AI (XAI) Layer
- **Exact Additive Tree Path Decomposition**: Exact telescoping sums for Decision Trees, Random Forests, and Gradient Boosting with numerical reconstruction error $< 10^{-14}$.
- **Grouped Categorical Attribution**: Inverse maps one-hot encoded indicators back to root categorical features at the record level.
- **Scale Safety**: Clearly labels probability shifts vs log-odds decision margins.

### 7. AI Business Explanation Layer & Non-Guarantee Safety Guardrails
- **Clause-Level Validation**: Distinguishes valid disclaimers (e.g. *"Forecast intervals represent statistical bounds, not a guaranteed outcome"*) from certainty promises (*"guaranteed return"*).
- **Corrective Retries**: Up to 2 retries (3 attempts total) injecting validation errors into the re-prompt.
- **Deterministic Local Fallback**: Safe mathematical templates when LLMs are offline or fail validation.
- **SHA-256 Evidence Caching**: Sub-5ms cached responses for identical evidence payloads.

### 8. Decision Intelligence Layer & Human Governance
- **Deterministic Rules Engine**: Safe comparison operators (`gt`, `gte`, `lt`, `lte`, `eq`, `neq`, `is_present`, `is_missing`).
- **Zero Retraining Required**: Evaluates existing model artifacts and dataset profiles directly on disk.
- **Human-in-the-Loop Governance**: Approval workflow (`needs_review`, `pending_approval`, `approved`, `rejected`, `dismissed`, `completed`) with mandatory comments on rejection and dismissal.

### 9. Prediqo AI Unified Question Router
- Unified conversational entry point.
- Automatically routes questions between Analytics (DuckDB), Prediction (ML), Forecasting (Time Series), and Decisions (Rules Engine).

---

## API Summary

```text
GET    /api/health
GET    /api/connectors

# Ingestion Jobs
POST   /api/ingestion/jobs                     # Async upload -> returns job_id & dataset_id
GET    /api/ingestion/jobs/{id}                # Poll stage progress (0-100%)
GET    /api/ingestion/jobs                     # List recent jobs

# Datasets
GET    /api/datasets                           # List datasets (version, status, row_count)
GET    /api/datasets/{id}                      # Load metadata without re-profiling
POST   /api/datasets/{id}/refresh              # Trigger zero-downtime background refresh
GET    /api/datasets/{id}/preview              # DuckDB server-side paginated preview
GET    /api/datasets/{id}/semantic-model       # Persisted business roles & allowed aggregations
DELETE /api/datasets/{id}

# Prediction Layer (Supervised ML)
GET    /api/prediction/feasibility/{id}        # Check ML feasibility, regression/classification targets
POST   /api/prediction/train                   # Train candidate models (Linear, RF, GB) with K-Fold CV
GET    /api/prediction/models/{id}             # List models for dataset or retrieve model details
POST   /api/prediction/predict                 # Single-record inference with probabilities & explanation

# Forecasting Layer (Time-Series Intelligence)
GET    /api/forecast/feasibility/{id}          # Check forecasting feasibility, dates, metrics, staleness
POST   /api/forecast/train                     # Aggregate DuckDB Parquet, backtest candidates, project intervals
GET    /api/forecast/models/{id}               # List trained forecast models for dataset
GET    /api/forecast/models/{id}/details       # Retrieve saved forecast model metadata and projection
POST   /api/forecast/predict                   # Project future periods for saved model with custom horizon

# Explainable AI (XAI)
GET    /api/explainability/feasibility/{id}    # Check XAI capabilities and exact decomposition
POST   /api/explainability/local               # Exact additive feature contributions for prediction
GET    /api/explainability/global/{id}         # Grouped feature importance with collinearity warnings
GET    /api/explainability/forecast/{id}       # Forecast trend, level state, seasonal cycles

# AI Business Explanations
GET    /api/ai/explain/status (or /v1/)        # Check provider availability, model defaults, cache count
POST   /api/ai/explain/prediction (or /v1/)    # Generate validated narrative for ML prediction
POST   /api/ai/explain/forecast (or /v1/)      # Generate validated narrative for forecast

# Decision Intelligence Layer
GET    /api/decisions/overview                 # Executive KPI counts, active rules, recent actions
GET    /api/decisions/scenarios                # List configured business scenarios
GET    /api/decisions/rules                    # List business rules
POST   /api/decisions/rules                    # Create business rule
POST   /api/decisions/rules/validate           # Validate rule specification
POST   /api/decisions/evaluate                 # Evaluate active rules against inputs
GET    /api/decisions/recommendations          # List recommendations
POST   /api/decisions/recommendations/{id}/status # Update recommendation status (approved, rejected, etc.)
GET    /api/decisions/audit                    # Chronological governance audit log

# Analytics, Question Router & Dashboards
POST   /api/query                              # Structured query or NL question
POST   /api/chart                              # Manual ChartSpec execution
POST   /api/ai/route                           # Intent question router (Analytics/Prediction/Forecast/Decision)
POST   /api/ai/chat                            # Conversational chat endpoint
GET    /api/dashboards                         # List saved dashboards
GET    /api/default-dashboard                  # Default dashboard with dynamic query specs
POST   /api/dashboards/{id}/charts             # Pin chart with stored query spec
```

---

## Testing & Verification

### Run Automated Backend Tests (156 tests — 100% passing)
```powershell
$env:PYTHONPATH="backend"
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

### Run Frontend Business & Unit Tests (29 tests — 100% passing)
```powershell
npx tsx --test frontend/tests/businessMetrics.test.ts frontend/tests/xaiNarratives.test.ts frontend/tests/decisionRules.test.ts frontend/tests/aiExplanation.test.ts frontend/tests/unifiedCenters.test.ts
```

### Build & Validate Frontend (Clean production bundle)
```powershell
npm --prefix frontend run build
```

### Run 10-Step Acceptance Workflow
```powershell
.\backend\.venv\Scripts\python.exe scripts\verify_acceptance_workflow.py
```

### Run Large Dataset Benchmarks
```powershell
.\backend\.venv\Scripts\python.exe scripts\benchmark_large_dataset.py
```

**Benchmark Results Summary ([`scripts/benchmark_results.json`](scripts/benchmark_results.json))**:
- **100,000 Rows**: 6.64 MB CSV $\rightarrow$ 2.01 MB Parquet. DuckDB aggregation in **23–49 ms**. Cache hit in **7.19 ms**.
- **1,000,000 Rows**: 66.37 MB CSV $\rightarrow$ 18.12 MB Parquet (3.66x compression). DuckDB aggregation in **37–47 ms**. Cache hit in **7.40 ms**. Preview in **10.65 ms**.
