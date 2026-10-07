"""CSV connector: reads a local CSV file."""
import os
from pathlib import Path

import pandas as pd

from .base import DataConnector


class CSVConnector(DataConnector):
    name = "csv"

    def test_connection(self, config: dict) -> bool:
        path = config.get("path", "")
        return isinstance(path, str) and os.path.isfile(path)

    def list_datasets(self, config: dict) -> list[dict]:
        path = config.get("path", "")
        p = Path(path)
        if p.is_dir():
            return [{"name": f.name} for f in sorted(p.glob("*.csv"))]
        if p.is_file():
            return [{"name": p.name}]
        return []

    def get_schema(self, config: dict, dataset: str) -> list[dict]:
        df = self.fetch_data(config, dataset)
        return [
            {"name": c, "dtype": str(df[c].dtype), "sample": None if df[c].empty else str(df[c].iloc[0])}
            for c in df.columns
        ]

    def fetch_data(self, config: dict, dataset: str) -> pd.DataFrame:
        path = config.get("path", "")
        df = pd.read_csv(path)
        df.columns = [str(c).strip() for c in df.columns]
        return df
