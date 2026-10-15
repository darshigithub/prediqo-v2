"""Dataset store: local files only (parquet data + JSON metadata).

Keeps an optional process-level in-memory cache for backwards compatibility;
parquet + metadata JSON make datasets survive restarts.
Separates metadata access from DataFrame loading so analysis doesn't load full data unnecessarily.
"""
import glob
import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from ..core.config import DATASETS_DIR, DATASETS_INDEX, METADATA_DIR
from ..models.dataset import ColumnMeta, DatasetProfile, DatasetStatus, StandardDataset
from ..standardization.semantics import get_semantic_model
from ..standardization.standardizer import build_standard_dataset

_lock = threading.Lock()
_cache: dict[str, StandardDataset] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_dataset(source_type: str, dataset_name: str, df: pd.DataFrame,
                   source_config: Optional[dict] = None) -> StandardDataset:
    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"
    ds = build_standard_dataset(dataset_id, dataset_name, source_type, df)

    parquet_path = DATASETS_DIR / f"{dataset_id}.parquet"
    ds.dataframe.to_parquet(parquet_path, index=False)

    sem_model = get_semantic_model(ds)

    meta = {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "source_type": source_type,
        "source_config": source_config or {},
        "version": 1,
        "status": DatasetStatus.READY,
        "error": None,
        "created_at": ds.created_at,
        "updated_at": ds.created_at,
        "file": str(parquet_path),
        "columns": [
            {
                "name": c.name, "dtype": c.dtype, "semantic_type": c.semantic_type,
                "business_role": getattr(c, "business_role", "unknown"),
                "display_name": getattr(c, "display_name", c.name),
                "allowed_aggregations": getattr(c, "allowed_aggregations", []),
                "unique_count": c.unique_count, "null_count": c.null_count,
                "min": c.min, "max": c.max, "avg": c.avg, "top_values": c.top_values,
            }
            for c in ds.columns
        ],
        "profile": {
            "rows": ds.profile.rows,
            "columns": ds.profile.columns,
            "missing_values": ds.profile.missing_values,
            "duplicate_rows": ds.profile.duplicate_rows,
            "numeric_columns": ds.profile.numeric_columns,
            "categorical_columns": ds.profile.categorical_columns,
            "date_columns": ds.profile.date_columns,
            "column_stats": ds.profile.column_stats,
        },
        "semantic_model": sem_model,
    }
    (METADATA_DIR / f"{dataset_id}.json").write_text(json.dumps(meta, indent=2, default=str))

    with _lock:
        _cache[dataset_id] = ds
    _rebuild_index()
    return ds


def _rebuild_index() -> None:
    entries = []
    for f in sorted(METADATA_DIR.glob("ds_*.json")):
        try:
            m = json.loads(f.read_text())
            entries.append({
                "dataset_id": m["dataset_id"],
                "dataset_name": m["dataset_name"],
                "source_type": m["source_type"],
                "version": m.get("version", 1),
                "status": m.get("status", DatasetStatus.READY),
                "error": m.get("error"),
                "created_at": m.get("created_at"),
                "updated_at": m.get("updated_at"),
                "rows": m.get("profile", {}).get("rows"),
                "columns": m.get("profile", {}).get("columns"),
            })
        except Exception:
            continue
    DATASETS_INDEX.write_text(json.dumps(entries, indent=2))


def list_datasets() -> list[dict]:
    if DATASETS_INDEX.exists():
        try:
            return json.loads(DATASETS_INDEX.read_text())
        except Exception:
            pass
    _rebuild_index()
    if DATASETS_INDEX.exists():
        return json.loads(DATASETS_INDEX.read_text())
    return []


class ParquetPath(type(Path())):
    """Path subclass that supports wildcard/partitioned parquet path existence checks."""

    def exists(self) -> bool:
        path_str = str(self)
        if "*" in path_str:
            return bool(glob.glob(path_str))
        try:
            if super().is_dir():
                return bool(list(super().glob("*.parquet")))
            return super().exists()
        except OSError:
            return False

    def unlink(self, missing_ok: bool = False) -> None:
        path_str = str(self)
        if "*" in path_str:
            matched = glob.glob(path_str)
            if not matched and not missing_ok:
                raise FileNotFoundError(f"No files matching {path_str}")
            for f in matched:
                try:
                    Path(f).unlink(missing_ok=missing_ok)
                except OSError:
                    pass
            parent_dir = self.parent
            if parent_dir.is_dir():
                try:
                    shutil.rmtree(parent_dir, ignore_errors=missing_ok)
                except OSError:
                    pass
            return
        if super().is_dir():
            shutil.rmtree(self, ignore_errors=missing_ok)
            return
        super().unlink(missing_ok=missing_ok)


def parquet_exists(path: Optional[Union[str, Path]]) -> bool:
    """Helper to check if a single file, directory, or wildcard parquet path exists."""
    if not path:
        return False
    path_str = str(path)
    if "*" in path_str:
        return bool(glob.glob(path_str))
    p = Path(path)
    try:
        if p.is_dir():
            return bool(list(p.glob("*.parquet")))
        return p.exists()
    except OSError:
        return False


def _resolve_file_path(meta: dict, dataset_id: str) -> ParquetPath:
    raw = meta.get("file")
    if raw:
        p = ParquetPath(raw)
        if p.exists():
            return p
        candidate_dir = DATASETS_DIR / dataset_id
        if candidate_dir.is_dir() and any(candidate_dir.glob("*.parquet")):
            return ParquetPath(candidate_dir / "*.parquet")
        candidate = DATASETS_DIR / p.name
        if candidate.exists():
            return ParquetPath(candidate)
    candidate_dir = DATASETS_DIR / dataset_id
    if candidate_dir.is_dir() and any(candidate_dir.glob("*.parquet")):
        return ParquetPath(candidate_dir / "*.parquet")
    return ParquetPath(DATASETS_DIR / f"{dataset_id}.parquet")


def get_parquet_path(dataset_id: str) -> Optional[ParquetPath]:
    """Returns the parquet path (single file or wildcard) without loading DataFrame."""
    meta = get_metadata(dataset_id)
    if not meta:
        return None
    return _resolve_file_path(meta, dataset_id)


def get_metadata(dataset_id: str) -> Optional[dict]:
    f = METADATA_DIR / f"{dataset_id}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return None
    return None


def get_dataset(dataset_id: str) -> Optional[StandardDataset]:
    """Loads StandardDataset. On cache miss, reconstructs from persisted metadata without re-profiling."""
    with _lock:
        if dataset_id in _cache:
            return _cache[dataset_id]

    meta = get_metadata(dataset_id)
    if not meta:
        return None

    file_path = _resolve_file_path(meta, dataset_id)
    if not file_path.exists():
        return None

    path_str = str(file_path)
    if "*" in path_str:
        matched = glob.glob(path_str)
        if not matched:
            return None
        df = pd.read_parquet(matched)
    elif file_path.is_dir():
        df = pd.read_parquet(file_path)
    else:
        df = pd.read_parquet(file_path)

    # Reconstruct ColumnMeta from stored metadata (NO re-profiling, NO re-inference!)
    columns = [
        ColumnMeta(
            name=c["name"],
            dtype=c["dtype"],
            semantic_type=c["semantic_type"],
            unique_count=c.get("unique_count", 0),
            null_count=c.get("null_count", 0),
            min=c.get("min"),
            max=c.get("max"),
            avg=c.get("avg"),
            top_values=c.get("top_values"),
            business_role=c.get("business_role", "unknown"),
            display_name=c.get("display_name", c["name"]),
            allowed_aggregations=c.get("allowed_aggregations", []),
        )
        for c in meta.get("columns", [])
    ]

    p_dict = meta.get("profile", {})
    profile = DatasetProfile(
        rows=p_dict.get("rows", len(df)),
        columns=p_dict.get("columns", len(df.columns)),
        missing_values=p_dict.get("missing_values", 0),
        duplicate_rows=p_dict.get("duplicate_rows", 0),
        numeric_columns=p_dict.get("numeric_columns", []),
        categorical_columns=p_dict.get("categorical_columns", []),
        date_columns=p_dict.get("date_columns", []),
        column_stats=p_dict.get("column_stats", {}),
    )

    ds = StandardDataset(
        dataset_id=dataset_id,
        dataset_name=meta["dataset_name"],
        source_type=meta["source_type"],
        dataframe=df,
        columns=columns,
        profile=profile,
        created_at=meta.get("created_at"),
        version=meta.get("version", 1),
        status=meta.get("status", DatasetStatus.READY),
        error=meta.get("error"),
    )

    with _lock:
        _cache[dataset_id] = ds
    return ds


def delete_dataset(dataset_id: str) -> bool:
    meta = get_metadata(dataset_id)
    if not meta:
        return False
    file_path = _resolve_file_path(meta, dataset_id)
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass

    # Ensure partitioned dataset directory is also removed if it exists
    parts_dir = DATASETS_DIR / dataset_id
    if parts_dir.is_dir():
        shutil.rmtree(parts_dir, ignore_errors=True)

    (METADATA_DIR / f"{dataset_id}.json").unlink(missing_ok=True)
    with _lock:
        _cache.pop(dataset_id, None)
    _rebuild_index()
    return True
