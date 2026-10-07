"""Lightweight local query result cache backed by data/cache/query/*.json."""
import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..core.config import QUERY_CACHE_DIR

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def _canonical_json(obj: Any) -> str:
    """Stable JSON string representation for cache key hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_query_hash(dataset_id: str, version: int, query_payload: dict[str, Any]) -> str:
    """Computes a deterministic SHA256 hash incorporating dataset_id, version, and query specifics."""
    canonical_repr = _canonical_json({
        "dataset_id": dataset_id,
        "version": version,
        "query": query_payload,
    })
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


class QueryCache:
    @staticmethod
    def get(query_hash: str) -> Optional[dict[str, Any]]:
        cache_file = QUERY_CACHE_DIR / f"{query_hash}.json"
        if not cache_file.exists():
            return None
        try:
            with _lock:
                data = json.loads(cache_file.read_text())
            return data
        except Exception as e:
            logger.warning("Failed to read cache file %s: %s", query_hash, e)
            return None

    @staticmethod
    def set(
        query_hash: str,
        dataset_id: str,
        version: int,
        result: dict[str, Any],
        chart: Optional[dict[str, Any]] = None,
        insight: Optional[str] = None,
        timing: Optional[dict[str, Any]] = None,
    ) -> None:
        cache_file = QUERY_CACHE_DIR / f"{query_hash}.json"
        entry = {
            "query_hash": query_hash,
            "dataset_id": dataset_id,
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "chart": chart,
            "insight": insight,
            "timing": timing or {},
        }
        try:
            with _lock:
                cache_file.write_text(json.dumps(entry, indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to write cache entry %s: %s", query_hash, e)

    @staticmethod
    def invalidate_dataset(dataset_id: str) -> int:
        """Invalidates all cached queries for a dataset (optional manual cleanup)."""
        count = 0
        with _lock:
            for f in QUERY_CACHE_DIR.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    if data.get("dataset_id") == dataset_id:
                        f.unlink(missing_ok=True)
                        count += 1
                except Exception:
                    continue
        return count
