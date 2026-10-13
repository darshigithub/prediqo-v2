"""Data preparation, column projection via DuckDB, date extraction, and preprocessing pipelines."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import duckdb
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

logger = logging.getLogger(__name__)


class DateFeatureExtractor(BaseEstimator, TransformerMixin):
    """Custom transformer to decompose date/timestamp strings or datetimes into numeric calendar features."""

    def __init__(self, date_columns: Optional[list[str]] = None):
        self.date_columns = date_columns

    def fit(self, X: pd.DataFrame, y=None):
        return self

    def transform(self, X: Any) -> pd.DataFrame:
        if not isinstance(X, pd.DataFrame):
            X_df = pd.DataFrame(X)
        else:
            X_df = X.copy()

        cols = self.date_columns or []
        for col in cols:
            if col in X_df.columns:
                dt_series = pd.to_datetime(X_df[col], errors="coerce")
                X_df[f"{col}_year"] = dt_series.dt.year.fillna(2000).astype(int)
                X_df[f"{col}_month"] = dt_series.dt.month.fillna(1).astype(int)
                X_df[f"{col}_day"] = dt_series.dt.day.fillna(1).astype(int)
                X_df[f"{col}_dayofweek"] = dt_series.dt.dayofweek.fillna(0).astype(int)
                X_df[f"{col}_quarter"] = dt_series.dt.quarter.fillna(1).astype(int)
                X_df = X_df.drop(columns=[col])

        return X_df


def load_selected_columns_from_parquet(
    parquet_path: Path, target_col: str, feature_cols: list[str], max_sample_rows: int = 50000
) -> tuple[pd.DataFrame, list[str]]:
    """Uses DuckDB to extract only the requested target and feature columns directly from Parquet."""
    needed = [target_col] + [f for f in feature_cols if f != target_col]
    quoted = ", ".join('"' + c.replace('"', '""') + '"' for c in needed)
    p_str = str(parquet_path).replace("\\", "/")

    con = duckdb.connect()
    sql = f"SELECT {quoted} FROM read_parquet('{p_str}')"
    df = con.execute(sql).df()

    warnings: list[str] = []
    if len(df) > max_sample_rows:
        warnings.append(
            f"Dataset contains {len(df)} rows. Downsampled to {max_sample_rows} rows for responsive local model training."
        )
        df = df.sample(n=max_sample_rows, random_state=42).reset_index(drop=True)

    return df, warnings


def classify_feature_types(
    df: pd.DataFrame, feature_cols: list[str], columns_meta: list[dict]
) -> tuple[list[str], list[str], list[str]]:
    """Partitions feature columns into date, numeric, and categorical lists."""
    meta_map = {c.get("name"): c for c in columns_meta}

    date_cols: list[str] = []
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []

    for f in feature_cols:
        m = meta_map.get(f, {})
        sem_type = str(m.get("semantic_type", "")).upper()
        dtype_str = str(m.get("dtype", "")).lower()

        if sem_type == "DATE" or "date" in dtype_str or "time" in dtype_str:
            date_cols.append(f)
        elif pd.api.types.is_numeric_dtype(df[f]) and sem_type != "CATEGORY":
            numeric_cols.append(f)
        else:
            categorical_cols.append(f)

    return date_cols, numeric_cols, categorical_cols


def build_full_preprocessing_pipeline(
    date_cols: list[str],
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> tuple[Pipeline, list[str], str]:
    """Constructs a composite sklearn Pipeline that extracts dates and transforms numeric & categorical columns."""
    expanded_numeric = list(numeric_cols)
    for dc in date_cols:
        expanded_numeric.extend([
            f"{dc}_year", f"{dc}_month", f"{dc}_day", f"{dc}_dayofweek", f"{dc}_quarter"
        ])

    transformers = []
    if expanded_numeric:
        num_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])
        transformers.append(("num", num_pipe, expanded_numeric))

    if categorical_cols:
        cat_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])
        transformers.append(("cat", cat_pipe, categorical_cols))

    col_transformer = ColumnTransformer(transformers=transformers, remainder="drop")

    full_preprocessor = Pipeline([
        ("date_extractor", DateFeatureExtractor(date_columns=date_cols)),
        ("column_transform", col_transformer),
    ])

    desc = (
        f"Dates expanded: {len(date_cols)}; "
        f"Numeric features ({len(expanded_numeric)}) median-imputed and standard-scaled; "
        f"Categorical features ({len(categorical_cols)}) most-frequent imputed and one-hot encoded."
    )

    return full_preprocessor, expanded_numeric, desc


def split_data(
    X: pd.DataFrame,
    y: pd.Series,
    problem_type: str,
    test_size: float = 0.2,
    random_state: int = 42,
    validation_strategy: Optional[str] = None,
    groups: Optional[pd.Series] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Splits data into train and test sets, respecting group-awareness, temporal order, or stratification."""
    if groups is not None and len(groups.unique()) >= 3:
        from sklearn.model_selection import GroupShuffleSplit
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
        train_idx, test_idx = next(gss.split(X, y, groups))
        return X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx]

    if validation_strategy == "time_aware":
        split_idx = max(1, int(len(X) * (1 - test_size)))
        return X.iloc[:split_idx], X.iloc[split_idx:], y.iloc[:split_idx], y.iloc[split_idx:]

    stratify = None
    if problem_type.lower() == "classification":
        val_counts = y.value_counts()
        if (val_counts >= 2).all() and len(y) >= 10:
            stratify = y

    return train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=stratify
    )

