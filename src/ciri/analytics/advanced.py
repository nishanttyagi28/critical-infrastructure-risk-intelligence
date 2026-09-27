"""Time-series context, correlation, root cause, and scenario shocks."""

from __future__ import annotations

import pandas as pd

from ciri.analytics.queries import correlation_frame, quarterly_demand, root_causes
from ciri.risk.scoring import simulate_scenario
from ciri.warehouse.store import Warehouse


def scenario_summary(warehouse: Warehouse, weather_delta: float, load_factor: float) -> dict[str, object]:
    """Count how the risk bands move under a weather or load shock."""
    current = warehouse.read("Mart_AssetRisk")
    shocked = simulate_scenario(current, weather_delta=weather_delta, load_factor=load_factor)
    def _counts(frame: pd.DataFrame) -> dict[str, int]:
        return {label: int((frame["risk_label"] == label).sum()) for label in ("Low", "Medium", "High", "Critical")}
    return {
        "weather_delta": weather_delta,
        "load_factor": load_factor,
        "before": _counts(current),
        "after": _counts(shocked),
        "assets_now_critical": int(
            ((current["risk_label"] != "Critical") & (shocked["risk_label"] == "Critical")).sum()
        ),
    }


def analysis_bundle(warehouse: Warehouse) -> dict[str, object]:
    """Everything the analyst and the risk page need in one read."""
    causes = root_causes(warehouse, trailing_days=30)
    return {
        "correlation": correlation_frame(warehouse),
        "root_cause_incidents": causes["incidents"],
        "root_cause_outages": causes["outages"],
        "quarter": quarterly_demand(warehouse),
    }
