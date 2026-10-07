"""Connector registry.

The app resolves connectors ONLY through this registry (never imports a
concrete connector elsewhere), keeping the app connector-agnostic so new
sources (MySQL, REST API, MongoDB, ...) can be added by implementing the
DataConnector interface and registering here.
"""
from typing import Any

import pandas as pd

from .base import DataConnector
from .csv_connector import CSVConnector
from .excel_connector import ExcelConnector
from .google_sheets_connector import GoogleSheetsConnector
from .postgres_connector import PostgresConnector

_REGISTRY: dict[str, DataConnector] = {
    CSVConnector.name: CSVConnector(),
    ExcelConnector.name: ExcelConnector(),
    GoogleSheetsConnector.name: GoogleSheetsConnector(),
    PostgresConnector.name: PostgresConnector(),
}


def get_connector(name: str) -> DataConnector:
    conn = _REGISTRY.get(name)
    if conn is None:
        raise KeyError(f"Unknown connector: {name}")
    return conn


def available_connectors() -> list[dict]:
    """Cards shown on the Data Sources page."""
    return [
        {"id": "csv", "label": "CSV", "description": "Upload CSV"},
        {"id": "excel", "label": "Excel", "description": "Upload Excel"},
        {"id": "google_sheets", "label": "Google Sheets", "description": "Connect Sheet"},
        {"id": "postgresql", "label": "PostgreSQL", "description": "Connect DB"},
    ]


def fetch_via_connector(connector_name: str, config: Any, dataset: str) -> pd.DataFrame:
    """Single entry point the rest of the app uses — connector-agnostic."""
    connector = get_connector(connector_name)
    if not connector.test_connection(config):
        raise ConnectionError(f"Cannot connect to source via connector '{connector_name}'")
    return connector.fetch_data(config, dataset)
