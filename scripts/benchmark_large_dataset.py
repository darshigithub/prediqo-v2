"""Benchmark script for Phase 2.5 large dataset performance testing.
Generates synthetic ecommerce datasets (100k and 1M rows) and measures:
1. Ingestion time (reading, standardizing, profiling, semantic analysis, parquet write)
2. Parquet file size
3. Profile time
4. Semantic analysis time
5. Simple aggregation query time (DuckDB over Parquet)
6. Filtered aggregation query time (DuckDB over Parquet)
7. Top-N ranking query time (DuckDB over Parquet)
8. Repeated query time with cache
9. Preview request time (DuckDB paginated over Parquet)
"""
import json
import os
import sys
import time
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

import numpy as np
import pandas as pd
from app.cache.query_cache import QueryCache, compute_query_hash
from app.core.config import DATASETS_DIR, UPLOADS_DIR
from app.ingestion.pipeline import execute_ingestion_pipeline
from app.models.schemas import AggregationQuery
from app.query_engine.executor import execute_query


def generate_synthetic_dataset(row_count: int, file_path: Path) -> None:
    print(f"\n--- Generating {row_count:,} synthetic rows at {file_path.name} ---")
    t0 = time.perf_counter()
    np.random.seed(42)

    cities = np.array(["Bengaluru", "Mumbai", "Delhi", "Chennai", "Hyderabad", "Pune", "Kolkata", "Ahmedabad"])
    categories = np.array(["Electronics", "Fashion", "Home & Kitchen", "Books", "Beauty", "Sports"])
    statuses = np.array(["Completed", "Pending", "Cancelled", "Processing"])
    dates = pd.date_range("2024-01-01", "2025-06-30", freq="h").strftime("%Y-%m-%d").values

    chunk_size = min(row_count, 100000)
    written = 0

    if file_path.exists():
        file_path.unlink()

    first_chunk = True
    while written < row_count:
        cur_chunk = min(chunk_size, row_count - written)
        order_ids = [f"ORD_{written + i:08d}" for i in range(cur_chunk)]
        df_chunk = pd.DataFrame({
            "Order_ID": order_ids,
            "Customer_ID": np.random.randint(10000, 99999, size=cur_chunk),
            "City": np.random.choice(cities, size=cur_chunk),
            "Product_Category": np.random.choice(categories, size=cur_chunk),
            "Total_Amount": np.round(np.random.uniform(10.0, 5000.0, size=cur_chunk), 2),
            "Quantity": np.random.randint(1, 10, size=cur_chunk),
            "Order_Status": np.random.choice(statuses, size=cur_chunk, p=[0.70, 0.15, 0.10, 0.05]),
            "Order_Date": np.random.choice(dates, size=cur_chunk),
            "Customer_Rating": np.random.choice([1, 2, 3, 4, 5], size=cur_chunk, p=[0.05, 0.05, 0.15, 0.45, 0.30]),
        })
        df_chunk.to_csv(file_path, mode="a" if not first_chunk else "w", header=first_chunk, index=False)
        first_chunk = False
        written += cur_chunk
        print(f"  Generated {written:,} / {row_count:,} rows...", end="\r")

    gen_time = time.perf_counter() - t0
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    print(f"\nGenerated {row_count:,} rows in {gen_time:.2f}s ({file_size_mb:.2f} MB CSV)")


def run_benchmark_for_size(row_count: int) -> dict:
    csv_file = UPLOADS_DIR / f"synthetic_bench_{row_count}.csv"
    if not csv_file.exists():
        generate_synthetic_dataset(row_count, csv_file)
    else:
        print(f"\nReusing existing synthetic CSV: {csv_file.name} ({csv_file.stat().st_size / (1024*1024):.2f} MB)")

    dataset_id = f"ds_bench_{row_count}"
    source_config = {"path": str(csv_file)}

    print(f"\n>>> Running Ingestion Pipeline for {row_count:,} rows...")
    t_ingest_start = time.perf_counter()
    meta = execute_ingestion_pipeline(
        dataset_id=dataset_id,
        dataset_name=f"bench_{row_count}",
        source_type="csv",
        source_config=source_config,
        version=1,
    )
    ingestion_duration_s = time.perf_counter() - t_ingest_start

    parquet_file = DATASETS_DIR / f"{dataset_id}.parquet"
    if not parquet_file.exists() and (DATASETS_DIR / dataset_id).exists():
        # Partitioned directory
        parquet_size_bytes = sum(f.stat().st_size for f in (DATASETS_DIR / dataset_id).glob("*.parquet"))
    else:
        parquet_size_bytes = parquet_file.stat().st_size

    parquet_size_mb = parquet_size_bytes / (1024 * 1024)
    timings = meta.get("timing", {})

    print(f"Ingestion Finished in {ingestion_duration_s:.2f}s")
    print(f"  Parquet Size: {parquet_size_mb:.2f} MB")
    print(f"  Reading: {timings.get('reading_ms', 0)} ms")
    print(f"  Standardization: {timings.get('standardization_ms', 0)} ms")
    print(f"  Profiling: {timings.get('profiling_ms', 0)} ms")
    print(f"  Semantic Analysis: {timings.get('semantic_ms', 0)} ms")
    print(f"  Writing Parquet: {timings.get('writing_ms', 0)} ms")

    # Benchmarking Queries directly on Parquet via DuckDB
    parquet_source = meta["file"]

    # 1. Simple Aggregation: Revenue by City
    q_simple = AggregationQuery(
        dataset_id=dataset_id,
        group_by=["City"],
        metric="Total_Amount",
        aggregation="sum",
    )
    t0 = time.perf_counter()
    res_simple = execute_query(parquet_source, q_simple)
    t_simple_ms = (time.perf_counter() - t0) * 1000

    # 2. Filtered Aggregation: Completed orders revenue by City
    q_filtered = AggregationQuery(
        dataset_id=dataset_id,
        group_by=["City"],
        metric="Total_Amount",
        aggregation="sum",
        filters=[{"column": "Order_Status", "op": "eq", "value": "Completed"}],
    )
    t0 = time.perf_counter()
    res_filtered = execute_query(parquet_source, q_filtered)
    t_filtered_ms = (time.perf_counter() - t0) * 1000

    # 3. Top-N Ranking: Top 5 categories by total revenue
    q_top = AggregationQuery(
        dataset_id=dataset_id,
        group_by=["Product_Category"],
        metric="Total_Amount",
        aggregation="sum",
        top_n=5,
    )
    t0 = time.perf_counter()
    res_top = execute_query(parquet_source, q_top)
    t_top_ms = (time.perf_counter() - t0) * 1000

    # 4. Cache Test: Hash and cache the filtered query
    q_hash = compute_query_hash(dataset_id, 1, q_filtered.model_dump())
    QueryCache.set(q_hash, dataset_id, 1, res_filtered)

    t0 = time.perf_counter()
    cached_entry = QueryCache.get(q_hash)
    t_cache_ms = (time.perf_counter() - t0) * 1000

    # 5. Preview request time (Page 1 of 50 rows)
    import duckdb
    con = duckdb.connect()
    t0 = time.perf_counter()
    p_str = str(parquet_source).replace("\\", "/")
    con.execute(f"CREATE VIEW t_preview AS SELECT * FROM read_parquet('{p_str}')")
    preview_df = con.query("SELECT * FROM t_preview LIMIT 50 OFFSET 0").df()
    t_preview_ms = (time.perf_counter() - t0) * 1000
    con.close()

    return {
        "row_count": row_count,
        "csv_size_mb": round(csv_file.stat().st_size / (1024 * 1024), 2),
        "parquet_size_mb": round(parquet_size_mb, 2),
        "ingestion_total_s": round(ingestion_duration_s, 2),
        "reading_ms": timings.get("reading_ms", 0),
        "standardization_ms": timings.get("standardization_ms", 0),
        "profiling_ms": timings.get("profiling_ms", 0),
        "semantic_ms": timings.get("semantic_ms", 0),
        "parquet_write_ms": timings.get("writing_ms", 0),
        "simple_aggregation_ms": round(t_simple_ms, 2),
        "filtered_aggregation_ms": round(t_filtered_ms, 2),
        "top_n_ranking_ms": round(t_top_ms, 2),
        "cache_hit_ms": round(t_cache_ms, 2),
        "preview_duckdb_ms": round(t_preview_ms, 2),
    }


def main():
    print("=========================================================")
    print("PREDIQO PHASE 2.5 — LARGE DATASET PERFORMANCE BENCHMARK")
    print("=========================================================")

    # Benchmark 100k rows
    results_100k = run_benchmark_for_size(100_000)

    # Benchmark 1M rows
    results_1m = run_benchmark_for_size(1_000_000)

    print("\n" + "=" * 65)
    print("FINAL MEASURED BENCHMARK RESULTS")
    print("=" * 65)
    print(f"{'Metric':<35} | {'100,000 Rows':<12} | {'1,000,000 Rows':<12}")
    print("-" * 65)
    print(f"{'Source CSV Size':<35} | {results_100k['csv_size_mb']} MB{'':<6} | {results_1m['csv_size_mb']} MB")
    print(f"{'Parquet Storage Size':<35} | {results_100k['parquet_size_mb']} MB{'':<6} | {results_1m['parquet_size_mb']} MB")
    print(f"{'Total Ingestion Time':<35} | {results_100k['ingestion_total_s']} s{'':<7} | {results_1m['ingestion_total_s']} s")
    print(f"{'  - Source Reading':<35} | {results_100k['reading_ms']} ms{'':<6} | {results_1m['reading_ms']} ms")
    print(f"{'  - Standardization':<35} | {results_100k['standardization_ms']} ms{'':<6} | {results_1m['standardization_ms']} ms")
    print(f"{'  - Data Profiling':<35} | {results_100k['profiling_ms']} ms{'':<6} | {results_1m['profiling_ms']} ms")
    print(f"{'  - Semantic Analysis':<35} | {results_100k['semantic_ms']} ms{'':<6} | {results_1m['semantic_ms']} ms")
    print(f"{'  - Analytical Parquet Write':<35} | {results_100k['parquet_write_ms']} ms{'':<6} | {results_1m['parquet_write_ms']} ms")
    print("-" * 65)
    print(f"{'Simple Aggregation (DuckDB)':<35} | {results_100k['simple_aggregation_ms']} ms{'':<6} | {results_1m['simple_aggregation_ms']} ms")
    print(f"{'Filtered Aggregation (DuckDB)':<35} | {results_100k['filtered_aggregation_ms']} ms{'':<6} | {results_1m['filtered_aggregation_ms']} ms")
    print(f"{'Top-N Ranking Query (DuckDB)':<35} | {results_100k['top_n_ranking_ms']} ms{'':<6} | {results_1m['top_n_ranking_ms']} ms")
    print(f"{'Repeated Query (Cache Hit)':<35} | {results_100k['cache_hit_ms']} ms{'':<6} | {results_1m['cache_hit_ms']} ms")
    print(f"{'Paginated Preview (DuckDB)':<35} | {results_100k['preview_duckdb_ms']} ms{'':<6} | {results_1m['preview_duckdb_ms']} ms")
    print("=" * 65)

    # Save results as JSON
    bench_out = Path(__file__).resolve().parent / "benchmark_results.json"
    bench_out.write_text(json.dumps({"100k": results_100k, "1m": results_1m}, indent=2))
    print(f"\nDetailed metrics saved to {bench_out}")


if __name__ == "__main__":
    main()
