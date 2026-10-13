"""Persistence and retrieval for time-series forecasting models and metadata."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from ..core.config import MODELS_DIR
from .models import (
    ForecastModelListItem,
    ForecastModelMetadata,
    ForecastPoint,
)

logger = logging.getLogger(__name__)


def get_forecast_model_dir(model_id: str) -> Path:
    return MODELS_DIR / model_id


def save_forecast_model(
    model_id: str,
    metadata: ForecastModelMetadata,
    forecast_points: list[ForecastPoint],
) -> Path:
    """Persists forecasting metadata and generated projection to disk."""
    m_dir = get_forecast_model_dir(model_id)
    m_dir.mkdir(parents=True, exist_ok=True)

    meta_path = m_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata.model_dump(), indent=2))

    forecast_path = m_dir / "forecast.json"
    forecast_data = [fp.model_dump() for fp in forecast_points]
    forecast_path.write_text(json.dumps(forecast_data, indent=2))

    return m_dir


def load_forecast_model(
    model_id: str,
) -> tuple[ForecastModelMetadata, list[ForecastPoint]]:
    """Loads saved forecasting metadata and forecast points."""
    m_dir = get_forecast_model_dir(model_id)
    if not m_dir.exists():
        raise FileNotFoundError(f"Forecasting model '{model_id}' not found.")

    meta_path = m_dir / "metadata.json"
    forecast_path = m_dir / "forecast.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata missing for model '{model_id}'.")

    meta_dict = json.loads(meta_path.read_text())
    metadata = ForecastModelMetadata(**meta_dict)

    points: list[ForecastPoint] = []
    if forecast_path.exists():
        raw_pts = json.loads(forecast_path.read_text())
        points = [ForecastPoint(**p) for p in raw_pts]

    return metadata, points


def get_forecast_metadata(model_id: str) -> Optional[ForecastModelMetadata]:
    """Retrieves forecast metadata without loading full projections."""
    m_dir = get_forecast_model_dir(model_id)
    meta_path = m_dir / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text())
        # Verify it's a forecasting model
        if "frequency" in data and "horizon" in data:
            return ForecastModelMetadata(**data)
        return None
    except Exception as e:
        logger.warning("Error reading forecast metadata for %s: %s", model_id, e)
        return None


def list_forecast_models_for_dataset(
    dataset_id: str,
) -> list[ForecastModelListItem]:
    """Lists saved forecasting models for a dataset."""
    items: list[ForecastModelListItem] = []
    if not MODELS_DIR.exists():
        return items

    for m_dir in sorted(MODELS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not m_dir.is_dir():
            continue
        # Check if dir is a forecast model
        if not m_dir.name.startswith("fc_") and not m_dir.name.startswith("forecast_"):
            continue
        meta_file = m_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            m = json.loads(meta_file.read_text())
            if m.get("dataset_id") != dataset_id:
                continue
            if "frequency" not in m:
                continue

            items.append(
                ForecastModelListItem(
                    model_id=m["model_id"],
                    dataset_id=m["dataset_id"],
                    dataset_version=m.get("dataset_version", 1),
                    date_column=m["date_column"],
                    metric_column=m["metric_column"],
                    frequency=m["frequency"],
                    aggregation=m["aggregation"],
                    algorithm=m["algorithm"],
                    mae=float(m["primary_metric_value"]),
                    created_at=m["created_at"],
                )
            )
        except Exception:
            continue

    return items
