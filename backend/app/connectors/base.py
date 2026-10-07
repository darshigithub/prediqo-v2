"""Connector interface. All connectors must implement this interface.

The rest of the application must not depend on a specific connector.
"""
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class DataConnector(ABC):
    """Common interface for every data source connector."""

    name: str = "base"

    @abstractmethod
    def test_connection(self, config: Any) -> bool:
        """Return True if the source is reachable/readable."""

    @abstractmethod
    def list_datasets(self, config: Any) -> list[dict]:
        """Return available datasets (tables/sheets/files) as dicts with at least a 'name'."""

    @abstractmethod
    def get_schema(self, config: Any, dataset: str) -> list[dict]:
        """Return column schema: [{name, dtype, sample}, ...]."""

    @abstractmethod
    def fetch_data(self, config: Any, dataset: str) -> pd.DataFrame:
        """Fetch the dataset as a plain pandas DataFrame."""

    def describe(self) -> dict:
        return {"name": self.name}
