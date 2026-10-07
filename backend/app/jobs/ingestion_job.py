"""Worker orchestrating ingestion pipeline within an IngestionJob."""
import json
import logging
from typing import Any

from ..core.config import METADATA_DIR
from ..ingestion.pipeline import execute_ingestion_pipeline
from ..models.dataset import DatasetStatus
from .job_manager import JobManager
from .job_models import JobStage, JobStatus

logger = logging.getLogger(__name__)


def run_ingestion_task(
    job_id: str,
    dataset_id: str,
    dataset_name: str,
    source_type: str,
    source_config: dict[str, Any],
    version: int = 1,
    is_refresh: bool = False,
) -> None:
    """Executes ingestion pipeline asynchronously and reports progress to JobManager."""
    JobManager.update_job(job_id, status=JobStatus.PROCESSING, stage=JobStage.READING, progress=10)

    def progress_callback(stage: str, progress: int, rows: int | None = None):
        JobManager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            stage=stage,
            progress=progress,
            row_count=rows,
            processed_rows=rows,
        )

    try:
        meta = execute_ingestion_pipeline(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            source_type=source_type,
            source_config=source_config,
            version=version,
            progress_callback=progress_callback,
        )

        row_count = meta.get("profile", {}).get("rows", 0)
        JobManager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            stage="READY",
            progress=100,
            row_count=row_count,
            processed_rows=row_count,
            metadata_update={"dataset_id": dataset_id, "version": version},
        )
        logger.info("Ingestion job %s completed successfully for %s", job_id, dataset_id)

    except Exception as e:
        logger.exception("Ingestion job %s failed: %s", job_id, e)
        JobManager.update_job(
            job_id,
            status=JobStatus.FAILED,
            stage=JobStage.FAILED,
            error=str(e),
        )

        # If it wasn't a refresh (new dataset), record the failure in dataset metadata
        if not is_refresh:
            meta_path = METADATA_DIR / f"{dataset_id}.json"
            if not meta_path.exists():
                failed_meta = {
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_name,
                    "source_type": source_type,
                    "source_config": source_config,
                    "version": version,
                    "status": DatasetStatus.FAILED,
                    "error": str(e),
                    "created_at": None,
                    "columns": [],
                    "profile": {"rows": 0, "columns": 0},
                }
                meta_path.write_text(json.dumps(failed_meta, indent=2))
