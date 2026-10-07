"""Model persistence and dataset version safety using joblib and local filesystem."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional
import joblib
from sklearn.pipeline import Pipeline

from ..core.config import MODELS_DIR
from .models import ModelListItem, ModelMetadata

logger = logging.getLogger(__name__)


def get_model_dir(model_id: str) -> Path:
    return MODELS_DIR / model_id


def save_model(
    model_id: str,
    pipeline: Pipeline,
    metadata: ModelMetadata,
    feature_schema: dict[str, Any],
) -> Path:
    """Persists model pipeline, metadata, metrics, and feature schema to disk."""
    m_dir = get_model_dir(model_id)
    m_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save pipeline
    model_path = m_dir / "model.joblib"
    joblib.dump(pipeline, model_path)

    # 2. Save metadata
    meta_path = m_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata.model_dump(), indent=2))

    # 3. Save metrics
    metrics_path = m_dir / "metrics.json"
    metrics_data = {
        "best_algorithm": metadata.algorithm,
        "primary_metric": metadata.primary_metric,
        "primary_metric_value": metadata.primary_metric_value,
        "metrics": metadata.metrics,
        "candidate_models": [c.model_dump() for c in metadata.candidate_models],
    }
    metrics_path.write_text(json.dumps(metrics_data, indent=2))

    # 4. Save feature schema
    schema_path = m_dir / "feature_schema.json"
    schema_path.write_text(json.dumps(feature_schema, indent=2))

    return m_dir


def load_model(model_id: str) -> tuple[Pipeline, ModelMetadata, dict[str, Any]]:
    """Loads a persisted model pipeline, metadata, and feature schema."""
    m_dir = get_model_dir(model_id)
    if not m_dir.exists():
        raise FileNotFoundError(f"Model '{model_id}' not found.")

    model_path = m_dir / "model.joblib"
    meta_path = m_dir / "metadata.json"
    schema_path = m_dir / "feature_schema.json"

    if not model_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"Model artifacts corrupted or missing for '{model_id}'.")

    pipeline: Pipeline = joblib.load(model_path)
    meta_dict = json.loads(meta_path.read_text())
    metadata = ModelMetadata(**meta_dict)

    feature_schema = json.loads(schema_path.read_text()) if schema_path.exists() else {}

    return pipeline, metadata, feature_schema


def get_model_metadata(model_id: str) -> Optional[ModelMetadata]:
    """Retrieves metadata for a model without unpickling the binary model."""
    meta_path = get_model_dir(model_id) / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text())
        return ModelMetadata(**data)
    except Exception as e:
        logger.warning("Error reading metadata for model %s: %s", model_id, e)
        return None


def list_models_for_dataset(
    dataset_id: str, current_version: Optional[int] = None
) -> list[ModelListItem]:
    """Lists trained models for a dataset, optionally filtered by current version."""
    items: list[ModelListItem] = []
    if not MODELS_DIR.exists():
        return items

    for m_dir in sorted(MODELS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not m_dir.is_dir():
            continue
        meta_file = m_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            m = json.loads(meta_file.read_text())
            if m.get("dataset_id") != dataset_id:
                continue

            # Optional filter by version
            if current_version is not None and m.get("dataset_version") != current_version:
                continue

            items.append(
                ModelListItem(
                    model_id=m["model_id"],
                    dataset_id=m["dataset_id"],
                    dataset_version=m.get("dataset_version", 1),
                    target_column=m["target_column"],
                    problem_type=m["problem_type"],
                    algorithm=m["algorithm"],
                    primary_metric=m["primary_metric"],
                    primary_metric_value=m["primary_metric_value"],
                    created_at=m["created_at"],
                )
            )
        except Exception:
            continue

    return items


def validate_model_version(metadata: ModelMetadata, current_dataset_version: int) -> tuple[bool, str]:
    """Verifies that the model's dataset version matches the current active dataset version."""
    if metadata.dataset_version != current_dataset_version:
        return False, (
            f"Dataset version mismatch: Model '{metadata.model_id}' was trained on version {metadata.dataset_version}, "
            f"but dataset '{metadata.dataset_id}' is now on version {current_dataset_version}. "
            "Please retrain the model on the updated dataset version."
        )
    return True, ""
