"""Google Sheets connector.

Reads a public (or anyone-with-link) Google Sheet via the CSV export endpoint.
No API credentials required for the prototype.
"""
import io
import re

import pandas as pd
import requests

from .base import DataConnector

EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{suffix}"


def _extract_sheet_id(source: str) -> str:
    """Accept a full Sheets URL or a raw sheet ID."""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", source or "")
    if m:
        return m.group(1)
    return (source or "").strip()


class GoogleSheetsConnector(DataConnector):
    name = "google_sheets"

    def test_connection(self, config: dict) -> bool:
        try:
            df = self._fetch_csv(config)
            return df is not None and df.shape[1] > 0
        except Exception:
            return False

    def list_datasets(self, config: dict) -> list[dict]:
        """Tabs require the Sheets API; the prototype treats the first tab as the dataset."""
        sheet_id = _extract_sheet_id(config.get("sheet_id", ""))
        if not sheet_id:
            return []
        return [{"name": sheet_id[:8] + "..."}]

    def get_schema(self, config: dict, dataset: str) -> list[dict]:
        df = self.fetch_data(config, dataset)
        return [
            {"name": c, "dtype": str(df[c].dtype), "sample": None if df[c].empty else str(df[c].iloc[0])}
            for c in df.columns
        ]

    def fetch_data(self, config: dict, dataset: str = "") -> pd.DataFrame:
        return self._fetch_csv(config)

    def _fetch_csv(self, config: dict) -> pd.DataFrame:
        sheet_id = _extract_sheet_id(config.get("sheet_id", ""))
        if not sheet_id:
            raise ValueError("sheet_id is required")
        gid = config.get("gid")
        suffix = f"&gid={gid}" if gid is not None else ""
        url = EXPORT_URL.format(sheet_id=sheet_id, suffix=suffix)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        text = resp.text
        if text.lstrip().lower().startswith("<!doctype html"):
            raise ConnectionError("Sheet is not publicly readable (got HTML sign-in page)")
        df = pd.read_csv(io.StringIO(text))
        df.columns = [str(c).strip() for c in df.columns]
        return df
