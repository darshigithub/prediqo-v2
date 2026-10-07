"""Ingestion payload and configuration models."""
from typing import Any, Optional
from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    source_type: str                  # csv | excel | google_sheets | postgresql
    dataset_name: Optional[str] = None
    file_path: Optional[str] = None
    source_config: dict[str, Any] = Field(default_factory=dict)


class IngestionResponse(BaseModel):
    job_id: str
    dataset_id: str
    dataset_name: str
    source_type: str
    status: str
    stage: str
    progress: int
