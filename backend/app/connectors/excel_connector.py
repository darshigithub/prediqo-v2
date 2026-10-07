"""Excel connector: reads local .xlsx / .xls files."""
import os
from pathlib import Path

import pandas as pd

from .base import DataConnector


class ExcelConnector(DataConnector):
    name = "excel"

    def test_connection(self, config: dict) -> bool:
        path = config.get("path", "")
        if not isinstance(path, str) or not os.path.isfile(path):
            return False
        return Path(path).suffix.lower() in (".xlsx", ".xls")

    def list_datasets(self, config: dict) -> list[dict]:
        """Each Excel sheet is a dataset."""
        path = config.get("path", "")
        try:
            xl = pd.ExcelFile(path)
            return [{"name": s} for s in xl.sheet_names]
        except Exception:
            return []

    def get_schema(self, config: dict, dataset: str) -> list[dict]:
        df = self.fetch_data(config, dataset)
        return [
            {"name": c, "dtype": str(df[c].dtype), "sample": None if df[c].empty else str(df[c].iloc[0])}
            for c in df.columns
        ]

    def fetch_data(self, config: dict, dataset: str) -> pd.DataFrame:
        path = config.get("path", "")
        sheet = dataset or 0
        df = pd.read_excel(path, sheet_name=sheet)
        df.columns = [str(c).strip() for c in df.columns]
        return df
