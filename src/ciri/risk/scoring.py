"""Explainable composite risk.

The score is a weighted sum of five operating signals. It is not the
machine-learning failure probability. Both are shown, and they answer
different questions: the score is the current condition of the asset, the
model is the chance of an equipment failure or outage in the latest month.

Bands
    0–24   Low
    25–49  Medium
    50–74  High
    75–100 Critical
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "age": 25.0,
    "failures": 25.0,
    "weather": 20.0,
    "maintenance": 15.0,
    "load": 15.0,
}


def risk_label(score: float) -> str:
    """Map a 0–100 score to an operating band."""
    if score < 25:
        return "Low"
    if score < 50:
        return "Medium"
    if score < 75:
        return "High"
    return "Critical"


def component_scores(
    age_years: float,
    failures_365d: float,
    weather_severity: float,
    maintenance_365d: float,
    load_index: float,
) -> dict[str, float]:
    """Return each component and the total, all on a 0–100 scale."""
    age = min(max(age_years, 0.0) / 35.0, 1.0) * WEIGHTS["age"]
    failures = min(max(failures_365d, 0.0) / 5.0, 1.0) * WEIGHTS["failures"]
    weather = min(max(weather_severity, 0.0) / 100.0, 1.0) * WEIGHTS["weather"]
    # Assets that were not maintained carry the full maintenance penalty.
    maintenance = (1.0 - min(max(maintenance_365d, 0.0) / 4.0, 1.0)) * WEIGHTS["maintenance"]
    load = min(max(load_index, 0.0) / 1.2, 1.0) * WEIGHTS["load"]
    total = age + failures + weather + maintenance + load
    return {
        "age_component": round(age, 2),
        "failure_component": round(failures, 2),
        "weather_component": round(weather, 2),
        "maintenance_component": round(maintenance, 2),
        "load_component": round(load, 2),
        "risk_score": round(total, 2),
    }


def score_assets(
    assets: pd.DataFrame,
    locations: pd.DataFrame,
    outages: pd.DataFrame,
    incidents: pd.DataFrame,
    weather: pd.DataFrame,
    maintenance: pd.DataFrame,
    demand: pd.DataFrame,
    dates: pd.DataFrame,
) -> pd.DataFrame:
    """Score every in-service asset from the latest year of history."""
    as_of = int(dates["date_key"].max())
    as_of_date = pd.to_datetime(str(as_of), format="%Y%m%d")
    window_start = int((as_of_date - pd.Timedelta(days=365)).strftime("%Y%m%d"))
    weather_start = int((as_of_date - pd.Timedelta(days=30)).strftime("%Y%m%d"))
    demand_start = weather_start

    failure_events = incidents.loc[incidents["category"] == "equipment_failure"]
    recent_failures = failure_events.loc[failure_events["date_key"] >= window_start]
    failure_counts = recent_failures.groupby("asset_id").size().rename("failure_events_365d")

    recent_outages = outages.loc[outages["date_key"] >= window_start]
    outage_counts = recent_outages.groupby("asset_id").size().rename("outages_365d")

    recent_maint = maintenance.loc[maintenance["date_key"] >= window_start]
    maint_counts = recent_maint.groupby("asset_id").size().rename("maintenance_365d")

    recent_weather = weather.loc[weather["date_key"] >= weather_start]
    weather_mean = recent_weather.groupby("location_id")["severity_score"].mean().rename("weather_severity_30d")

    # Load is recent demand divided by that location's own median day, so a
    # hot or cold week scores above 1 and a mild week scores below 1.
    recent_demand = demand.loc[demand["date_key"] >= demand_start]
    demand_mean = recent_demand.groupby("location_id")["demand_mwh"].mean()
    demand_median = demand.groupby("location_id")["demand_mwh"].median()
    load = (demand_mean / demand_median).rename("load_index")

    frame = assets.merge(locations[["location_id", "region", "city", "latitude", "longitude"]], on="location_id", how="left")
    frame = frame.merge(failure_counts, on="asset_id", how="left")
    frame = frame.merge(outage_counts, on="asset_id", how="left")
    frame = frame.merge(maint_counts, on="asset_id", how="left")
    frame = frame.merge(weather_mean, on="location_id", how="left")
    frame = frame.merge(load, on="location_id", how="left")
    for column, default in (
        ("failure_events_365d", 0),
        ("outages_365d", 0),
        ("maintenance_365d", 0),
        ("weather_severity_30d", 0),
        ("load_index", 0),
    ):
        frame[column] = frame[column].fillna(default)
    frame["failures_365d"] = frame["failure_events_365d"] + frame["outages_365d"]

    parts = frame.apply(
        lambda row: component_scores(
            float(row.age_years),
            float(row.failures_365d),
            float(row.weather_severity_30d),
            float(row.maintenance_365d),
            float(row.load_index),
        ),
        axis=1,
        result_type="expand",
    )
    scored = pd.concat([frame.reset_index(drop=True), parts.reset_index(drop=True)], axis=1)
    scored["risk_label"] = scored["risk_score"].map(risk_label)
    columns = [
        "asset_id",
        "asset_name",
        "asset_type",
        "location_id",
        "region",
        "city",
        "latitude",
        "longitude",
        "age_years",
        "failures_365d",
        "weather_severity_30d",
        "maintenance_365d",
        "load_index",
        "risk_score",
        "risk_label",
    ]
    scored["failures_365d"] = scored["failures_365d"].astype(int)
    scored["maintenance_365d"] = scored["maintenance_365d"].astype(int)
    return scored[columns].sort_values("asset_id").reset_index(drop=True)


def simulate_scenario(risk: pd.DataFrame, weather_delta: float = 0.0, load_factor: float = 1.0) -> pd.DataFrame:
    """Recompute labels after a weather or load shock. Scores stay in 0–100."""
    adjusted = risk.copy()
    rows = []
    for row in adjusted.itertuples(index=False):
        parts = component_scores(
            float(row.age_years),
            float(row.failures_365d),
            float(row.weather_severity_30d) + weather_delta,
            float(row.maintenance_365d),
            float(row.load_index) * load_factor,
        )
        rows.append(parts["risk_score"])
    adjusted["risk_score"] = rows
    adjusted["risk_label"] = adjusted["risk_score"].map(lambda value: risk_label(float(value)))
    return adjusted
