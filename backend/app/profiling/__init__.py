"""Data profiling package.

When a dataset is connected, the system automatically computes:
rows, columns, missing values, duplicate rows, numeric/categorical/date
columns, per-measure min/max/avg, and top values for categoricals.
"""
from .profiler import build_profile, profile_dataframe, profile_summary  # noqa: F401
