"""Job Manager: lightweight local thread-safe background job execution and tracking."""
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Optional

from ..core.config import JOBS_DIR
from .job_models import IngestionJob, JobStage, JobStatus, utc_now_iso

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ingest_worker")
_lock = threading.Lock()
_jobs: dict[str, IngestionJob] = {}


def _save_job_file(job: IngestionJob) -> None:
    try:
        path = JOBS_DIR / f"{job.job_id}.json"
        path.write_text(job.model_dump_json(indent=2))
    except Exception as e:
        logger.error("Failed to persist job %s: %s", job.job_id, e)


def _load_job_file(job_id: str) -> Optional[IngestionJob]:
    path = JOBS_DIR / f"{job_id}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return IngestionJob(**data)
        except Exception as e:
            logger.error("Failed to load job %s: %s", job_id, e)
    return None


class JobManager:
    @staticmethod
    def create_job(
        dataset_id: str,
        dataset_name: str,
        source_type: str,
        version: int = 1,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IngestionJob:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = IngestionJob(
            job_id=job_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            source_type=source_type,
            status=JobStatus.QUEUED,
            stage=JobStage.QUEUED,
            progress=0,
            started_at=utc_now_iso(),
            version=version,
            metadata=metadata or {},
        )
        with _lock:
            _jobs[job_id] = job
        _save_job_file(job)
        return job

    @staticmethod
    def get_job(job_id: str) -> Optional[IngestionJob]:
        with _lock:
            if job_id in _jobs:
                return _jobs[job_id]
        job = _load_job_file(job_id)
        if job:
            with _lock:
                _jobs[job_id] = job
        return job

    @staticmethod
    def list_jobs(limit: int = 50) -> list[IngestionJob]:
        # Scan disk to pick up persisted jobs
        for p in JOBS_DIR.glob("job_*.json"):
            jid = p.stem
            if jid not in _jobs:
                j = _load_job_file(jid)
                if j:
                    _jobs[jid] = j
        with _lock:
            jobs = list(_jobs.values())
        jobs.sort(key=lambda j: j.started_at, reverse=True)
        return jobs[:limit]

    @staticmethod
    def update_job(
        job_id: str,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        row_count: Optional[int] = None,
        processed_rows: Optional[int] = None,
        error: Optional[str] = None,
        metadata_update: Optional[dict[str, Any]] = None,
    ) -> Optional[IngestionJob]:
        with _lock:
            job = _jobs.get(job_id)
            if not job:
                job = _load_job_file(job_id)
                if job:
                    _jobs[job_id] = job
            if not job:
                return None

            if status is not None:
                job.status = status
            if stage is not None:
                job.stage = stage
            if progress is not None:
                job.progress = max(0, min(100, progress))
            if row_count is not None:
                job.row_count = row_count
            if processed_rows is not None:
                job.processed_rows = processed_rows
            if error is not None:
                job.error = error
            if metadata_update:
                job.metadata.update(metadata_update)

            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.completed_at = utc_now_iso()

            _save_job_file(job)
            return job

    @staticmethod
    def run_job_async(job_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        def _wrapper():
            try:
                fn(job_id, *args, **kwargs)
            except Exception as e:
                logger.exception("Error executing background job %s: %s", job_id, e)
                JobManager.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    stage=JobStage.FAILED,
                    error=str(e),
                )

        _executor.submit(_wrapper)
