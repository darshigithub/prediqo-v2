"""Profiling implementation: dataset-level and column-level statistics."""
import pandas as pd

from ..models.dataset import ColumnMeta, DatasetProfile


def build_profile(df: pd.DataFrame, columns: list[ColumnMeta]) -> DatasetProfile:
    """Aggregate dataset-level stats from the standardized columns."""
    numeric = [c.name for c in columns if c.semantic_type == "MEASURE"]
    categorical = [c.name for c in columns if c.semantic_type == "CATEGORY"]
    date_cols = [c.name for c in columns if c.semantic_type == "DATE"]
    return DatasetProfile(
        rows=len(df),
        columns=len(df.columns),
        missing_values=int(df.isna().sum().sum()),
        duplicate_rows=int(df.duplicated().sum()),
        numeric_columns=numeric,
        categorical_columns=categorical,
        date_columns=date_cols,
        column_stats={
            c.name: {
                "dtype": c.dtype,
                "semantic_type": c.semantic_type,
                "unique_count": c.unique_count,
                "null_count": c.null_count,
                "min": c.min,
                "max": c.max,
                "avg": c.avg,
                "top_values": c.top_values,
                "business_role": getattr(c, "business_role", "unknown"),
                "display_name": getattr(c, "display_name", c.name),
                "allowed_aggregations": getattr(c, "allowed_aggregations", []),
            }
            for c in columns
        },
    )


def profile_summary(profile: DatasetProfile) -> dict:
    return {
        "rows": profile.rows,
        "columns": profile.columns,
        "missing_values": profile.missing_values,
        "duplicate_rows": profile.duplicate_rows,
        "numeric_columns": profile.numeric_columns,
        "categorical_columns": profile.categorical_columns,
        "date_columns": profile.date_columns,
    }


def profile_dataframe(df: pd.DataFrame) -> DatasetProfile:
    """Profile a standardized DataFrame end to end (standalone helper)."""
    columns = [
        ColumnMeta(
            name=str(col),
            dtype=str(df[col].dtype),
            semantic_type="MEASURE",  # refined when standardizer builds ColumnMeta
            unique_count=int(df[col].nunique(dropna=True)),
            null_count=int(df[col].isna().sum()),
        )
        for col in df.columns
    ]
    return build_profile(df, columns)
