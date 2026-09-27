"""Row-level quality gates. Failed rows are quarantined, not silently dropped."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ciri.config import QUARANTINE_DIR
from ciri.errors import DataValidationError
from ciri.logging_utils import get_logger

logger = get_logger(__name__)

RULES: dict[str, list[tuple[str, str]]] = {
    "Dim_Asset": [
        ("age_years >= 0", "age_years must be non-negative"),
        ("capacity_mw > 0", "capacity_mw must be positive"),
    ],
    "Dim_Location": [
        ("latitude >= -90 and latitude <= 90", "latitude out of range"),
        ("longitude >= -180 and longitude <= 180", "longitude out of range"),
    ],
    "Dim_Weather": [
        ("severity_score >= 0 and severity_score <= 100", "severity_score out of range"),
        ("precipitation_mm >= 0", "precipitation cannot be negative"),
    ],
    "Fact_Outages": [
        ("duration_hours >= 0", "duration_hours cannot be negative"),
        ("customers_affected >= 0", "customers_affected cannot be negative"),
    ],
    "Fact_EnergyDemand": [
        ("demand_mwh >= 0", "demand_mwh cannot be negative"),
        ("peak_mw >= 0", "peak_mw cannot be negative"),
    ],
    "Fact_Maintenance": [
        ("cost_usd >= 0", "cost_usd cannot be negative"),
        ("duration_hours >= 0", "duration_hours cannot be negative"),
    ],
    "Fact_Incidents": [
        ("resolution_hours >= 0", "resolution_hours cannot be negative"),
    ],
}


def validate_frame(name: str, frame: pd.DataFrame, quarantine_dir: Path | None = None) -> pd.DataFrame:
    """Return the rows that pass every rule. Quarantine the rest.

    A table that loses more than 5 percent of its rows fails the load.
    """
    rules = RULES.get(name, [])
    if frame.empty or not rules:
        return frame
    keep = pd.Series(True, index=frame.index)
    reasons = pd.Series("", index=frame.index)
    for expression, reason in rules:
        passed = frame.eval(expression)
        reasons = reasons.where(passed, reasons + reason + "; ")
        keep = keep & passed
    rejected = frame.loc[~keep].copy()
    if not rejected.empty:
        rejected["reject_reason"] = reasons.loc[~keep]
        target = quarantine_dir or QUARANTINE_DIR
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{name}.csv"
        rejected.to_csv(path, index=False)
        logger.warning("quarantine %s rows=%s path=%s", name, len(rejected), path)
    if len(rejected) / len(frame) > 0.05:
        raise DataValidationError(f"{name} failed quality gate: {len(rejected)} of {len(frame)} rows rejected")
    return frame.loc[keep].reset_index(drop=True)


def assert_foreign_keys(frames: dict[str, pd.DataFrame]) -> None:
    """Refuse to load facts that point at missing dimensions."""
    checks = [
        ("Fact_Outages", "asset_id", "Dim_Asset", "asset_id"),
        ("Fact_Outages", "location_id", "Dim_Location", "location_id"),
        ("Fact_Outages", "date_key", "Dim_Date", "date_key"),
        ("Fact_Incidents", "asset_id", "Dim_Asset", "asset_id"),
        ("Fact_EnergyDemand", "location_id", "Dim_Location", "location_id"),
        ("Fact_Maintenance", "asset_id", "Dim_Asset", "asset_id"),
        ("Dim_Asset", "location_id", "Dim_Location", "location_id"),
        ("Dim_Weather", "location_id", "Dim_Location", "location_id"),
    ]
    problems: list[str] = []
    for fact, fact_col, dim, dim_col in checks:
        if fact not in frames or dim not in frames:
            continue
        missing = set(frames[fact][fact_col]) - set(frames[dim][dim_col])
        if missing:
            problems.append(f"{fact}.{fact_col} missing {len(missing)} keys in {dim}")
    if problems:
        raise DataValidationError("; ".join(problems))
