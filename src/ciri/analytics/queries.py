"""Curated questions over the star schema and the model marts."""

from __future__ import annotations

import pandas as pd

from ciri.warehouse.store import Warehouse


def _with_dates(frame: pd.DataFrame, dates: pd.DataFrame) -> pd.DataFrame:
    return frame.merge(dates[["date_key", "full_date", "year", "month", "month_name"]], on="date_key", how="left")


def executive_kpis(warehouse: Warehouse) -> dict[str, float]:
    """Headline numbers for the executive page."""
    assets = warehouse.read("Dim_Asset")
    incidents = warehouse.read("Fact_Incidents")
    risk = warehouse.read("Mart_AssetRisk")
    failure = warehouse.read("Ml_FailureScore")
    outage_scores = warehouse.read("Ml_OutageScore")
    demand = warehouse.read("Fact_EnergyDemand")
    dates = warehouse.read("Dim_Date")
    demand = _with_dates(demand, dates)
    demand["full_date"] = pd.to_datetime(demand["full_date"])
    latest = demand["full_date"].max()
    last_30 = demand.loc[demand["full_date"] > latest - pd.Timedelta(days=30), "demand_mwh"].sum()
    prior_30 = demand.loc[
        (demand["full_date"] <= latest - pd.Timedelta(days=30))
        & (demand["full_date"] > latest - pd.Timedelta(days=60)),
        "demand_mwh",
    ].sum()
    return {
        "total_assets": float(len(assets)),
        "active_incidents": float((incidents["status"] == "open").sum()),
        "critical_risks": float((risk["risk_label"] == "Critical").sum()),
        "high_risks": float((risk["risk_label"] == "High").sum()),
        "predicted_failures": float((failure["failure_probability"] >= 0.50).sum()),
        "predicted_outages": float((outage_scores["outage_probability"] >= 0.50).sum()),
        "demand_last_30d_mwh": float(last_30),
        "demand_prior_30d_mwh": float(prior_30),
    }


def demand_trend(warehouse: Warehouse) -> pd.DataFrame:
    demand = warehouse.read("Fact_EnergyDemand")
    dates = warehouse.read("Dim_Date")
    locations = warehouse.read("Dim_Location")
    frame = _with_dates(demand, dates).merge(locations[["location_id", "region"]], on="location_id")
    grouped = (
        frame.groupby(["year", "month", "month_name", "region"], as_index=False)["demand_mwh"].sum()
    )
    grouped["period"] = pd.to_datetime(
        grouped["year"].astype(str) + "-" + grouped["month"].astype(str) + "-01"
    )
    return grouped.sort_values("period")


def outage_trend(warehouse: Warehouse) -> pd.DataFrame:
    outages = warehouse.read("Fact_Outages")
    dates = warehouse.read("Dim_Date")
    locations = warehouse.read("Dim_Location")
    frame = _with_dates(outages, dates).merge(locations[["location_id", "region"]], on="location_id")
    grouped = frame.groupby(["year", "month", "month_name", "region"], as_index=False).agg(
        outages=("outage_id", "count"),
        customers=("customers_affected", "sum"),
        avg_hours=("duration_hours", "mean"),
    )
    grouped["period"] = pd.to_datetime(grouped["year"].astype(str) + "-" + grouped["month"].astype(str) + "-01")
    return grouped.sort_values("period")


def region_risk(warehouse: Warehouse) -> pd.DataFrame:
    risk = warehouse.read("Mart_AssetRisk")
    summary = risk.groupby("region", as_index=False).agg(
        assets=("asset_id", "count"),
        avg_risk=("risk_score", "mean"),
        critical=("risk_label", lambda s: int((s == "Critical").sum())),
        high=("risk_label", lambda s: int((s == "High").sum())),
    )
    return summary.sort_values("avg_risk", ascending=False)


def root_causes(warehouse: Warehouse, trailing_days: int = 30) -> dict[str, pd.DataFrame]:
    """Failure categories and outage causes over the trailing window."""
    dates = warehouse.read("Dim_Date")
    as_of = pd.to_datetime(dates["full_date"]).max()
    start_key = int((as_of - pd.Timedelta(days=trailing_days)).strftime("%Y%m%d"))
    incidents = warehouse.read("Fact_Incidents")
    outages = warehouse.read("Fact_Outages")
    recent_incidents = incidents.loc[incidents["date_key"] >= start_key]
    recent_outages = outages.loc[outages["date_key"] >= start_key]
    by_category = (
        recent_incidents.groupby("category", as_index=False).size().rename(columns={"size": "incidents"})
        if not recent_incidents.empty
        else pd.DataFrame(columns=["category", "incidents"])
    )
    by_cause = (
        recent_outages.groupby("cause", as_index=False).agg(
            outages=("outage_id", "count"),
            customers=("customers_affected", "sum"),
        )
        if not recent_outages.empty
        else pd.DataFrame(columns=["cause", "outages", "customers"])
    )
    return {
        "incidents": by_category.sort_values("incidents", ascending=False) if not by_category.empty else by_category,
        "outages": by_cause.sort_values("outages", ascending=False) if not by_cause.empty else by_cause,
    }


def correlation_frame(warehouse: Warehouse) -> pd.DataFrame:
    risk = warehouse.read("Mart_AssetRisk")
    columns = ["age_years", "failures_365d", "weather_severity_30d", "maintenance_365d", "load_index", "risk_score"]
    return risk[columns].corr(numeric_only=True)


def maintenance_backlog(warehouse: Warehouse, limit: int = 15) -> pd.DataFrame:
    """High-risk assets with little maintenance in the last year."""
    risk = warehouse.read("Mart_AssetRisk")
    backlog = risk.loc[risk["maintenance_365d"] <= 1].sort_values(
        ["risk_score", "failures_365d"], ascending=False
    )
    return backlog.head(limit)


def quarterly_demand(warehouse: Warehouse) -> dict[str, float]:
    """Compare the next 90 forecast days with the trailing 90 actual days."""
    forecast = warehouse.read("Ml_DemandForecast")
    demand = warehouse.read("Fact_EnergyDemand")
    dates = warehouse.read("Dim_Date")
    actual = _with_dates(demand, dates)
    actual["full_date"] = pd.to_datetime(actual["full_date"])
    latest = actual["full_date"].max()
    trailing = actual.loc[actual["full_date"] > latest - pd.Timedelta(days=90), "demand_mwh"].sum()
    forward = forecast.loc[forecast["horizon_day"] <= 90, "forecast_mwh"].sum()
    return {
        "trailing_90d_mwh": float(trailing),
        "next_quarter_mwh": float(forward),
        "delta_mwh": float(forward - trailing),
    }
