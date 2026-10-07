# Prediqo — AI Data Analytics Platform

A local-first AI data analytics platform inspired by Julius AI and Databricks.

Prediqo provides an end-to-end analytics workflow:

```text
Connect Data → Prepare Once (Async Job) → Explore Data (DuckDB Paginated)
             → Ask Questions (AI / NLP) → Analyze Parquet (DuckDB)
             → Interactive Charts → Dynamic Dashboards
```

**Core Philosophy (Phase 2.5)**:
> **"Prepare the data once, analyze it many times."**
> Ingestion is completely decoupled from the query path. Asking questions or browsing data never re-reads source files, re-profiles columns, or instantiates raw DataFrames into memory.

No Docker, no external database, no Celery/Redis, no authentication — everything runs locally with local-file storage and high-speed in-process analytics.

---

## Documentation & Living Context

- **[CONTEXT.md](CONTEXT.md)** — Living context document covering mental model, component responsibilities, API reference, and known quirks.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Architectural blueprint covering modular monolith design, background ingestion jobs, DuckDB direct Parquet execution, query caching, and benchmarks.
- **[docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)** — Development guide for adding connectors, charts, multi-provider LLMs, and running benchmarks.
- **[docs/PREDICTION.md](docs/PREDICTION.md)** — Complete machine learning prediction guide covering target detection, candidate algorithms, evaluation, persistence, and live inference.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, TypeScript, Vite 8, Tailwind CSS, Recharts 3 |
| **Backend** | Python 3.13, FastAPI, DuckDB, PyArrow, Pandas |
| **Job Engine** | In-process `ThreadPoolExecutor` with persistent JSON job tracking |
| **Cache Engine** | File-based Canonical SHA-256 Query Cache (`data/cache/query/`) |
| **Analytics Engine**| DuckDB executing directly over Parquet files with column pruning and filter push-down |
| **Storage** | Local filesystem (`data/uploads`, `data/datasets`, `data/metadata`, `data/jobs`, `data/cache`) |

---

## Project Structure

```text
prediqo-v1/
├── CONTEXT.md                       # Living context document
├── README.md                        # Project overview and quickstart
├── docs/
│   ├── ARCHITECTURE.md              # In-depth architectural blueprint
│   └── DEVELOPMENT_GUIDE.md         # Developer guide and extension recipes
├── scripts/
│   ├── generate_sample_data.py      # Generates sample e-commerce CSV
│   ├── benchmark_large_dataset.py   # Benchmark script for 100k and 1M rows
│   ├── benchmark_results.json       # Persisted benchmark metrics
│   └── verify_acceptance_workflow.py# 10-step Section 35 acceptance workflow verification
├── backend/
│   ├── tests/
│   │   ├── test_core.py             # Core parser and standardization tests
│   │   ├── test_ai_analyst.py       # AI analyst & LLM provider tests
│   │   ├── test_semantic_intelligence.py # Semantic intelligence & aggregation policy tests
│   │   └── test_phase25_architecture.py # Ingestion jobs, cache, versioning, DuckDB tests
│   ├── requirements.txt             # Pinned requirements
│   ├── requirements-flex.txt        # Recommended flexible requirements
│   └── app/
│       ├── main.py                  # FastAPI entrypoint & CORS
│       ├── api/routes.py            # REST API endpoints
│       ├── core/config.py           # Directory configurations
│       ├── models/                  # DatasetStatus, DatasetMetadata, schemas
│       ├── jobs/                    # Asynchronous ingestion job subsystem
│       │   ├── job_models.py        # IngestionJob, JobStage, JobStatus
│       │   ├── job_manager.py       # Thread-safe executor & JSON persistence
│       │   └── ingestion_job.py     # Background worker logic
│       ├── ingestion/               # Decoupled data preparation pipeline
│       │   ├── pipeline.py          # Read, standardize, profile, semantic, store
│       │   └── service.py           # High-level ingestion and refresh triggers
│       ├── storage/                 # Parquet dataset & query-spec dashboard stores
│       ├── cache/                   # Canonical SHA-256 query cache
│       ├── query_engine/            # DuckDB direct Parquet analytics & NL parser
│       ├── standardization/         # Cleaning, profiling, and semantic intelligence
│       ├── connectors/              # CSV, Excel, Google Sheets, Postgres
│       └── ai/                      # AI analyst, query planner, validator, prompts
├── frontend/
│   ├── src/
│   │   ├── pages/                   # Data Sources, Datasets, Explorer, Analyst, Dashboards
│   │   ├── components/              # Layout, ChartCard, DatasetPicker
│   │   ├── charts/                  # Recharts visualizer (Bar, Line, Area, Pie, KPI)
│   │   ├── services/api.ts          # Backend API client with job monitoring
│   │   └── types/                   # TypeScript interfaces
│   ├── package.json
│   └── vite.config.ts
└── data/
    ├── uploads/                     # Original raw uploaded files
    ├── datasets/                    # Analytical Parquet storage (`ds_<id>.parquet`)
    ├── metadata/                    # Schema, profile, semantic model, dashboards
    ├── jobs/                        # Persisted background job JSON records
    └── cache/query/                 # Cached query result JSON files
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

### 3. Sample Data

An e-commerce dataset (`data/uploads/ecommerce_sales.csv`, 50 rows × 18 columns) is included.
Regenerate it anytime with:

```powershell
python scripts/generate_sample_data.py
```

---

## Key Architecture & Features

### 1. Decoupled Ingestion Pipeline & Job System
- File uploads and source imports return immediately with an `IngestionJob` (`QUEUED`).
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

### 5. Semantic Intelligence & AI Analyst
- **Deterministic Rules by Default**: Works 100% offline without API keys.
- **Multi-Provider LLM Support**: Optional OpenAI, Groq, Gemini, Anthropic, or custom endpoints.
- **Aggregation Policy Protection**: Prevents illogical mathematical queries (e.g. rejects `SUM(ID)` or `AVG(ID)`).
- **Metric Discovery**: Discovers business metrics (`Total Orders`, `Average Order Value`, `Units Sold`).

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
GET    /api/datasets/{id}/preview              # DuckDB server-side paginated preview (?page&page_size&sort_col&search)
GET    /api/datasets/{id}/semantic-model       # Persisted business roles & allowed aggregations
DELETE /api/datasets/{id}

# Prediction Layer (Supervised ML)
GET    /api/prediction/feasibility/{id}        # Check ML feasibility, regression/classification targets
POST   /api/prediction/train                   # Train candidate models (Linear, RF, GB) & select best
GET    /api/prediction/models/{id}             # List models for dataset or retrieve model details
POST   /api/prediction/predict                 # Single-record inference with probabilities & explanation

# Analytics & AI
POST   /api/query                              # Structured query or NL question
POST   /api/chart                              # Manual ChartSpec execution
GET    /api/ai/providers                       # List configured LLM providers
POST   /api/ai/analyze                         # AI analyst (checks cache, queries DuckDB, returns timings)
GET    /api/ai/suggestions/{id}                # Schema-aware suggested questions

# Dashboards
GET    /api/dashboards
GET    /api/default-dashboard                  # Auto-resolves chart query specs via DuckDB / cache
GET    /api/dashboards/{id}
POST   /api/dashboards/{id}/charts             # Stores query spec instead of static row array
DELETE /api/dashboards/{id}/charts/{chart_id}
POST   /api/dashboards/{id}/charts/{chart_id}/move
```

---

## Testing & Verification

### Run Automated Backend Tests (66 tests)
```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

### Run 10-Step Acceptance Workflow
```powershell
.\backend\.venv\Scripts\python.exe scripts\verify_acceptance_workflow.py
```
Verifies job creation, stage progression, metadata direct load, server-side preview pagination, DuckDB Parquet execution, query cache hit, dashboard query specs, and zero-downtime refresh with cache invalidation.

### Run Large Dataset Benchmarks
```powershell
.\backend\.venv\Scripts\python.exe scripts\benchmark_large_dataset.py
```

**Benchmark Results Summary ([`scripts/benchmark_results.json`](file:///D:/AIML/prediqo-v1/scripts/benchmark_results.json))**:
- **100,000 Rows**: 6.64 MB CSV $\rightarrow$ 2.01 MB Parquet. DuckDB aggregation in **23–49 ms**. Cache hit in **7.19 ms**.
- **1,000,000 Rows**: 66.37 MB CSV $\rightarrow$ 18.12 MB Parquet (3.66x compression). DuckDB aggregation in **37–47 ms**. Cache hit in **7.40 ms**. Preview in **10.65 ms**.
