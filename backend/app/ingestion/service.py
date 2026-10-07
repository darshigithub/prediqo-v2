"""Ingestion Service: high level interface for starting and managing ingestion jobs."""
import json
import uuid
from typing import Any, Optional

from ..core.config import METADATA_DIR
from ..jobs.job_manager import JobManager
from ..jobs.job_models import IngestionJob
from ..jobs.ingestion_job import run_ingestion_task


def start_ingestion_job(
    source_type: str,
    dataset_name: Optional[str] = None,
    source_config: Optional[dict[str, Any]] = None,
    dataset_id: Optional[str] = None,
) -> IngestionJob:
    """Creates and starts an asynchronous ingestion job."""
    ds_id = dataset_id or f"ds_{uuid.uuid4().hex[:8]}"
    ds_name = dataset_name or f"dataset_{ds_id[-4:]}"
    cfg = source_config or {}

    job = JobManager.create_job(
        dataset_id=ds_id,
        dataset_name=ds_name,
        source_type=source_type,
        version=1,
        metadata={"source_config": cfg},
    )

    JobManager.run_job_async(
        job.job_id,
        run_ingestion_task,
        ds_id,
        ds_name,
        source_type,
        cfg,
        version=1,
        is_refresh=False,
    )
    return job


def refresh_dataset(dataset_id: str) -> IngestionJob:
    """Initiates a dataset refresh into version N+1 while keeping current version accessible."""
    meta_path = METADATA_DIR / f"{dataset_id}.json"
    if not meta_path.exists():
        raise KeyError(f"Dataset not found: {dataset_id}")

    meta = json.loads(meta_path.read_text())
    curr_version = meta.get("version", 1)
    new_version = curr_version + 1
    ds_name = meta.get("dataset_name", dataset_id)
    source_type = meta.get("source_type", "csv")
    source_config = meta.get("source_config", {})

    job = JobManager.create_job(
        dataset_id=dataset_id,
        dataset_name=ds_name,
        source_type=source_type,
        version=new_version,
        metadata={"source_config": source_config, "is_refresh": True},
    )

    JobManager.run_job_async(
        job.job_id,
        run_ingestion_task,
        dataset_id,
        ds_name,
        source_type,
        source_config,
        version=new_version,
        is_refresh=True,
    )
    return job
