"""Core data models for the prototype."""
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


@dataclass
class ColumnMeta:
    name: str
    dtype: str
    semantic_type: str            # ID | DIMENSION | MEASURE | DATE | CATEGORY | TEXT
    unique_count: int
    null_count: int
    # Profile stats
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    top_values: Optional[list] = None  # [{value, count}, ...] for categorical
    # Phase 2 Semantic Intelligence
    business_role: str = "unknown"
    display_name: str = ""
    allowed_aggregations: list[str] = field(default_factory=list)


@dataclass
class DatasetProfile:
    rows: int
    columns: int
    missing_values: int
    duplicate_rows: int
    numeric_columns: list[str]
    categorical_columns: list[str]
    date_columns: list[str]
    column_stats: dict[str, dict] = field(default_factory=dict)


class DatasetStatus:
    CREATING = "CREATING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    STALE = "STALE"


@dataclass
class StandardDataset:
    dataset_id: str
    dataset_name: str
    source_type: str
    dataframe: pd.DataFrame
    columns: list[ColumnMeta]
    profile: DatasetProfile
    created_at: Optional[str] = None
    version: int = 1
    status: str = DatasetStatus.READY
    error: Optional[str] = None

