"""PostgreSQL connector using DuckDB's postgres scanner (lazy import; optional)."""
import pandas as pd

from .base import DataConnector


class PostgresConnector(DataConnector):
    name = "postgresql"

    def _conn_string(self, config: dict) -> str:
        return (
            f"host={config.get('host', 'localhost')} port={config.get('port', 5432)} "
            f"user={config.get('user', '')} password={config.get('password', '')} "
            f"dbname={config.get('database', '')} connect_timeout=10"
        )

    def _read(self, config: dict, dataset: str):
        import duckdb
        try:
            duckdb.execute("LOAD postgres;")
        except Exception:
            duckdb.execute("INSTALL postgres; LOAD postgres;")
        conn = duckdb.connect()
        try:
            conn.execute(f"ATTACH '{self._conn_string(config)}' AS pg (TYPE postgres);")
            rel = conn.query(f"SELECT * FROM pg.{config.get('schema', 'public')}.{dataset}")
            return rel.df()
        finally:
            conn.close()

    def test_connection(self, config: dict) -> bool:
        try:
            import duckdb
            try:
                duckdb.execute("LOAD postgres;")
            except Exception:
                duckdb.execute("INSTALL postgres; LOAD postgres;")
            conn = duckdb.connect()
            try:
                conn.execute(f"ATTACH '{self._conn_string(config)}' AS pg (TYPE postgres);")
                conn.query("SELECT 1")
            finally:
                conn.close()
            return True
        except Exception:
            return False

    def list_datasets(self, config: dict) -> list[dict]:
        try:
            import duckdb
            try:
                duckdb.execute("LOAD postgres;")
            except Exception:
                duckdb.execute("INSTALL postgres; LOAD postgres;")
            conn = duckdb.connect()
            try:
                conn.execute(f"ATTACH '{self._conn_string(config)}' AS pg (TYPE postgres);")
                rows = conn.query(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = ? ORDER BY table_name",
                    [config.get("schema", "public")],
                ).fetchall()
            finally:
                conn.close()
            return [{"name": r[0]} for r in rows]
        except Exception:
            return []

    def get_schema(self, config: dict, dataset: str) -> list[dict]:
        df = self._read(config, dataset)
        return [
            {"name": c, "dtype": str(df[c].dtype), "sample": None if df[c].empty else str(df[c].iloc[0])}
            for c in df.columns
        ]

    def fetch_data(self, config: dict, dataset: str) -> pd.DataFrame:
        return self._read(config, dataset)
