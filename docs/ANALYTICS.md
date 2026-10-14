# Prediqo — Analytics Engine & Data Intelligence Architecture

## 1. Architecture Overview

Prediqo's **Analytics Engine** delivers descriptive ("What happened?") and diagnostic ("Why did it happen?") insights over tabular datasets without requiring external data warehouses, server clusters, or background database daemons.

It implements a local-first, column-pruned architecture using **DuckDB**, Snappy-compressed **Apache Parquet**, and rich **JSON Semantic Metadata**:

```text
                                  FRONTEND (React 19 + Recharts)
                                                |
                                                v
                                     FASTAPI REST API (routes.py)
                                                |
                      +-------------------------+-------------------------+
                      |                                                   |
                      v                                                   v
              INGESTION PATH (Prepare Once)                       QUERY PATH (Analyze Many Times)
                      |                                                   |
              [ Ingestion Jobs ]                                   [ AI Analyst / NLP ]
           (app/jobs/job_manager.py)                           (app/ai/ & app/query_engine/)
                      |                                                   |
           +----------+----------+                                        v
           |                     |                                 [ Semantic Model ]
           v                     v                                (Persisted JSON metadata)
    [ Connectors ]     [ Ingestion Pipeline ]                             |
    (CSV/Excel/Sheets) (app/ingestion/pipeline.py)                        v
           |                     |                                 [ Query Plan ]
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
                      +---------------------------------------> [ Charts / Insights / Dashboards ]
```

---

## 2. Ingestion Subsystem & Pipeline (`backend/app/ingestion/`)

The ingestion pipeline transforms raw uploaded data (CSV, Excel) into standardized, column-indexed Parquet files accompanied by comprehensive metadata. It runs strictly on upload or explicit refresh:

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
1. **`READING`**: Reads raw data using chunked, buffered readers to prevent out-of-memory spikes on multi-megabyte uploads.
2. **`STANDARDIZING`**: Cleans headers (snake_case conversion, alphanumeric normalization), trims whitespace, strips currency symbols (`$`, `€`, `₹`), parses numeric types, and standardizes datetimes into ISO-8601 UTC format.
3. **`PROFILING`**: Calculates statistical distributions (min, max, mean, median, quartiles), missingness percentages, cardinality counts, and uniqueness ratios.
4. **`SEMANTIC_ANALYSIS`**: Infers semantic types (`ID`, `DIMENSION`, `MEASURE`, `DATE`, `CATEGORY`, `TEXT`), business roles (`revenue`, `duration`, `status`, etc.), and aggregation permissions.
5. **`WRITING`**: Serializes records to Snappy-compressed columnar Parquet files (`data/datasets/{dataset_id}.parquet`).
6. **`METADATA`**: Persists `data/metadata/{dataset_id}.json` with full schema, semantic dictionary, profile metrics, version integer, and dataset lifecycle state (`READY`).

---

## 3. Dataset Lifecycle & Zero-Downtime Refresh

### State Machine (`backend/app/models/dataset.py`)
- **`CREATING`**: Ingestion job initialized and queued.
- **`PROCESSING`**: Pipeline executing. Analytical queries are blocked with HTTP 400 until processing finishes.
- **`READY`**: Data and metadata verified; dataset fully queryable.
- **`FAILED`**: Ingestion halted with an explicit error trace.
- **`STALE`**: Underlying file changed or model version out-of-sync.

### Zero-Downtime Dataset Refresh
When `POST /api/datasets/{dataset_id}/refresh` is triggered:
1. The background job sets target version to `version = current_version + 1`.
2. Ingestion writes to a staging file: `data/datasets/{dataset_id}_v{new_version}.parquet`.
3. **Zero Interruption**: While the refresh executes, ongoing analytical queries and dashboards continue reading the existing active `v1` Parquet file and metadata without locking or downtime.
4. Upon successful validation, the staging file atomically replaces the active Parquet file, the version counter increments to `2`, and status remains `READY`.
5. If the refresh job fails, the existing `v1` dataset remains untouched and fully operational.

---

## 4. DuckDB Analytical Query Engine (`backend/app/query_engine/`)

Prediqo bypasses heavy in-memory Pandas materialization by running vectorized SQL queries directly over Parquet storage using DuckDB:

```python
con = duckdb.connect()
con.execute(f"CREATE VIEW dataset AS SELECT * FROM read_parquet('{parquet_path}')")
result_df = con.execute(sql).df()
```

### Performance Optimizations
1. **Column Pruning**:
   Queries project only the dimensions and metrics referenced in the query spec:
   ```sql
   SELECT "City", SUM("Sales_Amount") AS "Sales_Amount"
   FROM dataset
   GROUP BY "City"
   ORDER BY "Sales_Amount" DESC
   LIMIT 50;
   ```
   DuckDB and Parquet scan only the bytes corresponding to `"City"` and `"Sales_Amount"`, completely bypassing all other columns in the dataset.
2. **Filter Push-Down**:
   Filters (e.g. `Region = 'North' AND Sales_Amount > 100`) are translated into DuckDB `WHERE` clauses, allowing DuckDB to inspect Parquet metadata statistics and skip irrelevant row groups without reading raw bytes.
3. **Server-Side Data Explorer Pagination**:
   The interactive Data Explorer previews rows via `SELECT * FROM dataset LIMIT {page_size} OFFSET {offset}` and `SELECT COUNT(*) FROM dataset` directly in DuckDB over Parquet.

---

## 5. Semantic Intelligence & Aggregation Guardrails

The Semantic Intelligence layer (`backend/app/standardization/semantics.py`) prevents erroneous analytics calculations:

### Semantic Types & Rules
| Semantic Type | Allowed Aggregations | Forbidden Aggregations | Examples |
|---|---|---|---|
| `MEASURE` | `SUM`, `AVG`, `MIN`, `MAX`, `MEDIAN`, `COUNT` | None | `Sales_Amount`, `Unit_Price`, `Profit`, `Duration` |
| `DIMENSION` | `COUNT`, `DISTINCT_COUNT` | `SUM`, `AVG`, `MIN`, `MAX` | `Customer_Segment`, `Region`, `Country` |
| `CATEGORY` | `COUNT`, `DISTINCT_COUNT` | `SUM`, `AVG`, `MIN`, `MAX` | `Order_Status`, `Payment_Method` |
| `DATE` | `MIN`, `MAX`, `COUNT`, `DISTINCT_COUNT` | `SUM`, `AVG` | `Order_Date`, `Ship_Date`, `Created_At` |
| `ID` | `COUNT`, `DISTINCT_COUNT` | `SUM`, `AVG`, `MIN`, `MAX` | `Order_ID`, `Customer_ID`, `Transaction_Number` |

### Guardrails
- Queries attempting to execute mathematical operations like `SUM(Order_ID)` or `AVG(Customer_ID)` are blocked and rejected by [`query_validator.py`](file:///D:/AIML/prediqo-v2/backend/app/ai/query_validator.py).
- Requests attempting identifier aggregation automatically convert to `COUNT(Order_ID)` or `DISTINCT_COUNT(Customer_ID)`.

---

## 6. Deterministic Query Caching Subsystem (`backend/app/cache/query_cache.py`)

To eliminate duplicate execution of identical queries, Prediqo implements a deterministic file-based query cache:

1. **Deterministic Normalization**:
   - Query inputs (dimensions, metrics, filters, sorts, limits) are sorted into a canonical JSON representation.
   - A SHA-256 hash is computed over `(dataset_id, dataset_version, canonical_query)`.
2. **Cache Lookup**:
   - Checks `data/cache/query/{hash}.json`.
   - On a **Cache Hit**, DuckDB execution and LLM inference are completely bypassed, returning results in under **8 ms** with `cache_hit: true`.
3. **Automatic Version-Aware Invalidation**:
   - Because the hash key incorporates the dataset's `version` integer, refreshing a dataset automatically invalidates all previous cache entries without requiring manual file deletions.

---

## 7. Interactive Dashboards & Chart Specification

Dashboards in Prediqo store **Query Specifications**, not static result snapshots:
- Stored specification: `{ chart_id, title, chart_type, dimension, metric, aggregation, filters }`.
- When a dashboard opens, [`populate_dashboard_charts`](file:///D:/AIML/prediqo-v2/backend/app/storage/dashboard_store.py) dynamically resolves each chart:
  1. Checks `QueryCache` for pre-calculated results.
  2. If missing, executes the query spec directly in DuckDB over Parquet.
  3. Caches the result for instant subsequent reloads.

---

## 8. Capability Registry & Schema Flexibility (`backend/app/capabilities/`)

Prediqo dynamically analyzes diverse tabular schemas without rigid column naming requirements:

- **Column Synonym Detection**: Extended `semantics.py` recognizes non-standard headers (e.g. `purchased_on`, `invoice_number`, `net_sales`, `daily_revenue`, `gross_sales`).
- **Granularity & Duplication Detection**: Detects order-item level tables where order totals or prices are repeated across multiple rows per order ID via DuckDB `COUNT(DISTINCT id) < COUNT(*)`, warning users against summing duplicated totals.
- **Capability Degradation**: Dynamically evaluates whether a dataset is suitable for:
  - Descriptive Analytics (always supported for valid tables)
  - Supervised Prediction (requires candidate targets with non-zero variance)
  - Time-Series Forecasting (requires date columns, metrics, and $\ge 10$ periods)
- **Manual Overrides**: Users can override detected semantic roles via `POST /api/capabilities/{id}`.

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
| **Data Explorer Preview (100 rows)** | **13.1 ms** | **10.6 ms** | Server-side `LIMIT / OFFSET` over Parquet |
| **Query Cache Hit** | **7.19 ms** | **7.40 ms** | Instant JSON cache response |

---

---

## 10. Prediqo AI Conversational Routing & Question Answering

The Analytics engine connects directly to the **Prediqo AI Question Router** (`backend/app/ai/router.py`) and unified chat interface:

- **Descriptive Intent Detection**: The router detects questions seeking historical totals, category rankings, or aggregations (e.g. *"What is the total revenue by category?"*, *"Which city had the highest order count?"*) and routes them immediately to the DuckDB analytics path.
- **Query Validation & Planning**: The AI query planner verifies dimensions and metrics against the dataset's persisted semantic model, rejecting invalid aggregations (`SUM(ID)`) and pushing column-pruned SQL plans to DuckDB.
- **Cache Acceleration**: Repeated or identical analytical questions resolve from `QueryCache` in $< 10\text{ms}$.
- **Faithful Insights**: Insights generated from analytical queries are derived strictly from actual returned rows without hallucinated numbers.

---

## 11. Roadmap for Further Analytics Development

1. **Window Functions & Cohort Analysis**:
   - Retention curves, rolling cohort active user calculations, and customer lifetime value (LTV) cohorts.
2. **Custom Calculated Measures**:
   - User-defined metric expressions (e.g. `Profit_Margin = (Profit / Revenue) * 100`) resolved directly in DuckDB SQL views.
3. **Multi-Table Relational Analytics**:
   - Foreign-key relationship discovery and automated star-schema joins over multiple Parquet files.
4. **Automated Anomaly Detection**:
   - Unsupervised z-score and IQR anomaly detection flagging abnormal transaction spikes or drops directly inside analytical queries.

