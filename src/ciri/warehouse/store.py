"""SQL warehouse used by the API, the models, and Streamlit."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

import pandas as pd

from ciri.config import SQL_DIR, database_url
from ciri.errors import WarehouseError
from ciri.logging_utils import get_logger

logger = get_logger(__name__)

STAR_TABLES = [
    "Dim_Date",
    "Dim_Location",
    "Dim_Asset",
    "Dim_Weather",
    "Dim_RiskLevel",
    "Fact_Outages",
    "Fact_Incidents",
    "Fact_EnergyDemand",
    "Fact_Maintenance",
    "Ops_SensorReading",
    "Fs_AssetMonth",
    "Mart_AssetRisk",
    "Ml_OutageScore",
    "Ml_FailureScore",
    "Ml_HealthScore",
    "Ml_DemandForecast",
    "Ml_Anomaly",
]


class Warehouse:
    """Thin wrapper around the star schema and the model marts."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or database_url()
        self.engine: Engine = create_engine(self.url)

    def backend_name(self) -> str:
        if self.url.startswith("sqlite"):
            return "sqlite"
        if self.url.startswith("postgres"):
            return "postgresql"
        return self.engine.dialect.name

    def execute_script(self, sql: str) -> None:
        """Run a script of semicolon-separated statements."""
        with self.engine.begin() as conn:
            for statement in _statements(sql):
                conn.execute(text(statement))

    def apply_sql_file(self, name: str) -> None:
        path = SQL_DIR / name
        if not path.exists():
            raise WarehouseError(f"missing SQL file {path}")
        logger.info("apply sql file=%s", name)
        self.execute_script(path.read_text(encoding="utf-8"))

    def replace(self, frame: pd.DataFrame, table: str) -> int:
        """Replace a table's rows. The table must already exist."""
        with self.engine.begin() as conn:
            conn.execute(text(f'DELETE FROM "{table}"'))
            frame.to_sql(table, conn, if_exists="append", index=False)
        logger.info("loaded %s rows=%s", table, len(frame))
        return int(len(frame))

    def read(self, table: str) -> pd.DataFrame:
        try:
            return pd.read_sql(text(f'SELECT * FROM "{table}"'), self.engine)
        except Exception as exc:
            raise WarehouseError(f"could not read {table}: {exc}") from exc

    def ready(self) -> bool:
        try:
            frame = self.read("Dim_Asset")
        except WarehouseError:
            return False
        return not frame.empty


def _statements(sql: str) -> Iterator[str]:
    cleaned: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        cleaned.append(line)
    blob = "\n".join(cleaned)
    for part in blob.split(";"):
        statement = part.strip()
        if statement:
            yield statement
