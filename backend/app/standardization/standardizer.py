"""Standardization: turn any raw DataFrame into the common internal representation.

Regardless of source (CSV, Excel, Google Sheets, PostgreSQL), every dataset
goes through this module before the rest of the app sees it.
"""
from datetime import datetime, timezone

import pandas as pd

from ..models.dataset import ColumnMeta, StandardDataset
from ..profiling.profiler import build_profile
from .semantics import get_allowed_aggregations, get_display_name, infer_business_role


def _infer_semantic_type(series: pd.Series, dtype: str, unique_count: int, rows: int) -> str:
    """Infer a simple semantic type for a column."""
    name = str(series.name).lower()
    non_null = series.dropna()
    is_str = pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)

    # DATE: datetime dtype or date-like column
    if pd.api.types.is_datetime64_any_dtype(series):
        return "DATE"
    if is_str and len(non_null) > 0:
        sample = non_null.iloc[0]
        if isinstance(sample, str):
            parsed = pd.to_datetime(non_null.head(20), errors="coerce", format="mixed")
            if parsed.notna().mean() >= 0.8:
                return "DATE"

    # ID: identifier-looking name, or high-cardinality string/int
    if any(k in name for k in ("id", "uuid", "code")) and unique_count > rows * 0.5:
        return "ID"
    if is_str and unique_count >= rows * 0.9:
        return "ID"

    # MEASURE: numeric non-identifier
    if pd.api.types.is_numeric_dtype(series):
        return "MEASURE"

    # CATEGORY vs TEXT for strings
    if is_str:
        if unique_count <= max(25, rows * 0.2):
            return "CATEGORY"
        return "TEXT"

    if pd.api.types.is_bool_dtype(series):
        return "CATEGORY"

    return "DIMENSION"


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Basic hygiene: strip column names, drop all-empty columns, normalize dates/numbers."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Drop fully empty unnamed columns (common in Excel exports)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    df = df.dropna(axis=1, how="all")

    for col in df.columns:
        s = df[col]
        if pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s):
            cleaned = s.astype(str).str.strip().replace({"": None, "nan": None, "None": None, "NaT": None})
            # Try date conversion
            parsed = pd.to_datetime(cleaned, errors="coerce", format="mixed")
            if parsed.notna().mean() >= 0.8 and parsed.notna().sum() > 0:
                df[col] = parsed
                continue
            # Try numeric conversion (handles '1,234.5' / '₹1,234' style values)
            numeric = pd.to_numeric(cleaned.str.replace(r"[,₹$\s]", "", regex=True), errors="coerce")
            if numeric.notna().mean() >= 0.8 and numeric.notna().sum() > 0:
                df[col] = numeric
            else:
                df[col] = cleaned
    return df


def build_standard_dataset(
    dataset_id: str,
    dataset_name: str,
    source_type: str,
    df: pd.DataFrame,
) -> StandardDataset:
    """Create the StandardDataset: DataFrame + column metadata + profile."""
    df = standardize_columns(df)
    if df.empty:
        raise ValueError("Dataset is empty after standardization")

    rows = len(df)
    columns: list[ColumnMeta] = []
    for col in df.columns:
        s = df[col]
        dtype = str(s.dtype)
        null_count = int(s.isna().sum())
        unique_count = int(s.nunique(dropna=True))
        semantic = _infer_semantic_type(s, dtype, unique_count, rows)
        role = infer_business_role(str(col), s, dtype, semantic, unique_count, rows)
        disp_name = get_display_name(str(col), role)
        allowed_aggs = get_allowed_aggregations(semantic, role, dtype)

        cm = ColumnMeta(
            name=str(col),
            dtype=dtype,
            semantic_type=semantic,
            unique_count=unique_count,
            null_count=null_count,
            business_role=role,
            display_name=disp_name,
            allowed_aggregations=allowed_aggs,
        )

        if semantic == "MEASURE":
            cm.min = float(s.min())
            cm.max = float(s.max())
            cm.avg = float(s.mean())
        if semantic in ("CATEGORY", "TEXT", "DIMENSION"):
            top = s.value_counts().head(5)
            cm.top_values = [{"value": str(k), "count": int(v)} for k, v in top.items()]

        columns.append(cm)

    profile = build_profile(df, columns)
    return StandardDataset(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        source_type=source_type,
        dataframe=df,
        columns=columns,
        profile=profile,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
