"""Load raw CSV extracts into the star schema.

Stages: read, validate, referential check, processed extract, SQL load.
A stage that raises is logged with the stack and stops the run. Quarantine
files are written by the validator before that decision.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ciri.config import POWERBI_DIR, PROCESSED_DIR, RAW_DIR
from ciri.data.validate import assert_foreign_keys, validate_frame
from ciri.errors import CiriError
from ciri.logging_utils import get_logger, log_stage
from ciri.risk.scoring import score_assets
from ciri.warehouse.store import Warehouse

logger = get_logger(__name__)

LOAD_ORDER = [
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
]


def run_etl(
    raw_dir: Path | None = None,
    warehouse: Warehouse | None = None,
    processed_dir: Path | None = None,
) -> Warehouse:
    """Validate raw files and load the warehouse, including the risk mart."""
    source = raw_dir or RAW_DIR
    wh = warehouse or Warehouse()
    output = processed_dir or PROCESSED_DIR
    output.mkdir(parents=True, exist_ok=True)
    try:
        frames = _read_raw(source)
        clean = {name: validate_frame(name, frame) for name, frame in frames.items()}
        assert_foreign_keys(clean)
        for name, frame in clean.items():
            frame.to_csv(output / f"{name}.csv", index=False)
        wh.apply_sql_file("001_star_schema.sql")
        for name in LOAD_ORDER:
            wh.replace(clean[name], name)
            log_stage(logger, "load", table=name, rows=len(clean[name]))
        risk = score_assets(
            clean["Dim_Asset"],
            clean["Dim_Location"],
            clean["Fact_Outages"],
            clean["Fact_Incidents"],
            clean["Dim_Weather"],
            clean["Fact_Maintenance"],
            clean["Fact_EnergyDemand"],
            clean["Dim_Date"],
        )
        wh.replace(risk, "Mart_AssetRisk")
        risk.to_csv(output / "Mart_AssetRisk.csv", index=False)
        wh.apply_sql_file("002_kpi_views.sql")
        _export_powerbi(clean, risk)
        log_stage(logger, "etl_complete", assets=len(clean["Dim_Asset"]), risk_rows=len(risk))
    except CiriError:
        logger.exception("etl failed")
        raise
    except Exception as exc:
        logger.exception("etl failed with an unexpected error")
        raise CiriError(str(exc)) from exc
    return wh


def _read_raw(raw_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for name in LOAD_ORDER:
        path = raw_dir / f"{name}.csv"
        if not path.exists():
            raise CiriError(f"raw extract missing: {path}")
        frames[name] = pd.read_csv(path)
        log_stage(logger, "read", table=name, rows=len(frames[name]))
    return frames


def _export_powerbi(frames: dict[str, pd.DataFrame], risk: pd.DataFrame) -> None:
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        if name.startswith("Dim_") or name.startswith("Fact_"):
            frame.to_csv(POWERBI_DIR / f"{name}.csv", index=False)
    risk.to_csv(POWERBI_DIR / "Mart_AssetRisk.csv", index=False)
    logger.info("power bi extracts written to %s", POWERBI_DIR)
