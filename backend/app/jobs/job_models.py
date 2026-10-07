"""Job models for data ingestion lifecycle."""
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field


class JobStage:
    QUEUED = "QUEUED"
    READING = "READING"
    STANDARDIZING = "STANDARDIZING"
    PROFILING = "PROFILING"
    SEMANTIC_ANALYSIS = "SEMANTIC_ANALYSIS"
    WRITING = "WRITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobStatus:
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionJob(BaseModel):
    job_id: str
    dataset_id: str
    dataset_name: str
    source_type: str
    status: str = JobStatus.QUEUED
    stage: str = JobStage.QUEUED
    progress: int = 0
    started_at: str = Field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None
    error: Optional[str] = None
    row_count: Optional[int] = None
    processed_rows: Optional[int] = None
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
