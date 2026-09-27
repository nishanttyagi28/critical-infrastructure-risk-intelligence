"""Explain a stored prediction without refitting the model."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from ciri.config import MODEL_DIR
from ciri.errors import ModelError
from ciri.warehouse.store import Warehouse


def explain_asset(asset_id: int, warehouse: Warehouse | None = None, model_dir: Path | None = None) -> dict[str, object]:
    """Compare one asset with the fleet and state why its scores look like this."""
    wh = warehouse or Warehouse()
    directory = model_dir or MODEL_DIR
    artifact_path = directory / "outage_model.joblib"
    if not artifact_path.exists():
        raise ModelError("outage model has not been trained")
    artifact = joblib.load(artifact_path)
    months = wh.read("Fs_AssetMonth")
    asset_rows = months.loc[months["asset_id"] == asset_id]
    if asset_rows.empty:
        raise ModelError(f"no feature history for asset_id={asset_id}")
    latest = asset_rows.sort_values("month").tail(1)
    fleet = months.loc[months["month"] == latest["month"].iloc[0]]
    outage = wh.read("Ml_OutageScore")
    failure = wh.read("Ml_FailureScore")
    health = wh.read("Ml_HealthScore")
    risk = wh.read("Mart_AssetRisk")

    def _value(frame: pd.DataFrame, column: str) -> float | None:
        match = frame.loc[frame["asset_id"] == asset_id]
        if match.empty:
            return None
        return float(match.iloc[0][column])

    comparisons = []
    for column in ("age_years", "severity_score", "prior_failures", "maintenance_count", "load_index"):
        asset_value = float(latest.iloc[0][column])
        fleet_value = float(fleet[column].median())
        comparisons.append(
            {
                "feature": column,
                "asset": round(asset_value, 2),
                "fleet_median": round(fleet_value, 2),
                "above_fleet": asset_value > fleet_value,
            }
        )
    drivers = [row["feature"] for row in comparisons if row["above_fleet"] and row["feature"] != "maintenance_count"]
    if float(latest.iloc[0]["maintenance_count"]) < float(fleet["maintenance_count"].median()):
        drivers.append("maintenance_count")
    return {
        "asset_id": asset_id,
        "month": str(latest.iloc[0]["month"]),
        "outage_probability": _value(outage, "outage_probability"),
        "failure_probability": _value(failure, "failure_probability"),
        "health_score": _value(health, "health_score"),
        "risk_label": None if risk.loc[risk["asset_id"] == asset_id].empty else str(risk.loc[risk["asset_id"] == asset_id].iloc[0]["risk_label"]),
        "drivers": drivers,
        "comparisons": comparisons,
        "model_features": artifact["columns"],
    }
