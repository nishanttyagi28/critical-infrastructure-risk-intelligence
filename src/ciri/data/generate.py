"""Synthetic AetherGrid history.

The generator is seeded. Outages and equipment failures are drawn from a
latent risk that depends on age, weather, load, and whether the asset is on
the preventive-maintenance program. Models trained on this history should
beat a majority-class baseline; the relationships are documented in
docs/features.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ciri.config import PRODUCTION_END, PRODUCTION_START, RAW_DIR
from ciri.data.catalog import ASSET_TYPES, MANUFACTURERS, REGIONS
from ciri.logging_utils import get_logger, log_stage

logger = get_logger(__name__)


@dataclass(frozen=True)
class GenerateConfig:
    """Controls the size of a generated grid. Tests use a short window."""

    seed: int = 42
    start: date = PRODUCTION_START
    end: date = PRODUCTION_END
    locations_per_region: int = 3
    assets_per_location: int = 8
    sensor_assets: int = 48
    sensor_days: int = 180


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -20, 20)))


def _daterange(start: date, end: date) -> list[date]:
    days = (end - start).days + 1
    return [start + timedelta(days=offset) for offset in range(days)]


def _month_starts(start: date, end: date) -> list[date]:
    cursor = date(start.year, start.month, 1)
    months: list[date] = []
    while cursor <= end:
        months.append(cursor)
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def build_datasets(config: GenerateConfig | None = None) -> dict[str, pd.DataFrame]:
    """Return every raw table. Nothing is written."""
    cfg = config or GenerateConfig()
    rng = np.random.default_rng(cfg.seed)
    dates = _daterange(cfg.start, cfg.end)
    dim_date = _dim_date(dates)
    dim_location = _dim_location(cfg, rng)
    dim_asset = _dim_asset(dim_location, cfg, rng)
    dim_weather = _dim_weather(dim_location, dim_date, rng)
    fact_demand = _fact_demand(dim_location, dim_weather, rng)
    maintenance, on_program = _maintenance_plan(dim_asset, dates, rng)
    months = _monthly_panel(dim_asset, dim_weather, fact_demand, maintenance, on_program, cfg, rng)
    fact_outages, fact_incidents = _events_from_months(months, dim_asset, dim_weather, rng)
    sensors = _sensors(dim_asset, dates, cfg, rng)
    dim_risk = pd.DataFrame(
        [
            {"risk_level_id": 1, "risk_label": "Low", "min_score": 0, "max_score": 25},
            {"risk_level_id": 2, "risk_label": "Medium", "min_score": 25, "max_score": 50},
            {"risk_level_id": 3, "risk_label": "High", "min_score": 50, "max_score": 75},
            {"risk_level_id": 4, "risk_label": "Critical", "min_score": 75, "max_score": 100},
        ]
    )
    frames = {
        "Dim_Date": dim_date,
        "Dim_Location": dim_location,
        "Dim_Asset": dim_asset,
        "Dim_Weather": dim_weather,
        "Dim_RiskLevel": dim_risk,
        "Fact_Outages": fact_outages,
        "Fact_Incidents": fact_incidents,
        "Fact_EnergyDemand": fact_demand,
        "Fact_Maintenance": maintenance,
        "Ops_SensorReading": sensors,
        "Fs_AssetMonth": months,
    }
    return frames


def write_raw(frames: dict[str, pd.DataFrame], raw_dir: Path | None = None) -> Path:
    """Write raw CSV extracts."""
    target = raw_dir or RAW_DIR
    target.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(target / f"{name}.csv", index=False)
        log_stage(logger, "generate", table=name, rows=len(frame))  # type: ignore[arg-type]
    return target


def generate(config: GenerateConfig | None = None, raw_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Build the synthetic grid and write raw CSV files."""
    frames = build_datasets(config)
    write_raw(frames, raw_dir)
    logger.info("synthetic grid written seed=%s", (config or GenerateConfig()).seed)
    return frames


def _dim_date(dates: list[date]) -> pd.DataFrame:
    rows = []
    for current in dates:
        rows.append(
            {
                "date_key": int(current.strftime("%Y%m%d")),
                "full_date": current.isoformat(),
                "year": current.year,
                "quarter": (current.month - 1) // 3 + 1,
                "month": current.month,
                "month_name": current.strftime("%B"),
                "day": current.day,
                "day_of_week": current.weekday(),
                "day_name": current.strftime("%A"),
                "is_weekend": int(current.weekday() >= 5),
                "iso_week": current.isocalendar().week,
            }
        )
    return pd.DataFrame(rows)


def _dim_location(cfg: GenerateConfig, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    location_id = 1
    for region in REGIONS:
        cities = list(region["cities"])[: cfg.locations_per_region]
        for city, lat, lon in cities:
            rows.append(
                {
                    "location_id": location_id,
                    "region": region["region"],
                    "city": city,
                    "latitude": round(float(lat) + float(rng.normal(0, 0.02)), 4),
                    "longitude": round(float(lon) + float(rng.normal(0, 0.02)), 4),
                    "grid_zone": region["grid_zone"],
                    "criticality": region["criticality"],
                    "base_mwh": int(region["base_mwh"]),
                    "temp_delta": float(region["temp_delta"]),
                }
            )
            location_id += 1
    return pd.DataFrame(rows)


def _dim_asset(locations: pd.DataFrame, cfg: GenerateConfig, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    asset_id = 1
    as_of = cfg.end
    for location in locations.itertuples(index=False):
        region_code = "".join(word[0] for word in str(location.region).split())
        for slot in range(cfg.assets_per_location):
            spec = ASSET_TYPES[(asset_id + slot) % len(ASSET_TYPES)]
            commissioned_year = int(rng.integers(1978, 2023))
            commissioned = date(commissioned_year, int(rng.integers(1, 13)), int(rng.integers(1, 28)))
            age = as_of.year - commissioned.year - (
                (as_of.month, as_of.day) < (commissioned.month, commissioned.day)
            )
            on_program = int(rng.random() < 0.72)
            rows.append(
                {
                    "asset_id": asset_id,
                    "asset_name": f"{spec['code']}-{region_code}-{asset_id:04d}",
                    "asset_type": spec["asset_type"],
                    "location_id": int(location.location_id),
                    "commissioned_date": commissioned.isoformat(),
                    "age_years": int(age),
                    "manufacturer": MANUFACTURERS[int(rng.integers(0, len(MANUFACTURERS)))],
                    "capacity_mw": int(spec["capacity_mw"]),
                    "voltage_kv": int(spec["voltage_kv"]),
                    "customer_exposure": int(spec["customers"]),
                    "status": "in_service",
                    "on_maintenance_program": on_program,
                }
            )
            asset_id += 1
    return pd.DataFrame(rows)


def _dim_weather(locations: pd.DataFrame, dates: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    loc = locations[["location_id", "temp_delta"]].copy()
    panel = loc.merge(dates[["date_key", "full_date", "month"]], how="cross")
    doy = pd.to_datetime(panel["full_date"]).dt.dayofyear.to_numpy()
    seasonal = 10 + 14 * np.sin(2 * np.pi * (doy - 100) / 365.25)
    temp = seasonal + panel["temp_delta"].to_numpy() + rng.normal(0, 2.4, len(panel))
    wind = np.clip(12 + rng.normal(0, 6, len(panel)) + (temp < 0) * 4, 0, None)
    precip = np.clip(rng.gamma(1.1, 2.2, len(panel)) - 1.0, 0, None)
    storm = ((precip > 18) | (wind > 48)).astype(int)
    severity = np.clip(0.35 * wind + 1.15 * precip + 18 * storm, 0, 100)
    weather_id = np.arange(1, len(panel) + 1)
    return pd.DataFrame(
        {
            "weather_id": weather_id,
            "location_id": panel["location_id"].to_numpy(),
            "date_key": panel["date_key"].to_numpy(),
            "temperature_c": np.round(temp, 2),
            "wind_speed_kmh": np.round(wind, 2),
            "precipitation_mm": np.round(precip, 2),
            "storm_flag": storm,
            "severity_score": np.round(severity, 2),
        }
    )


def _fact_demand(locations: pd.DataFrame, weather: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    merged = weather.merge(locations[["location_id", "base_mwh"]], on="location_id", how="left")
    doy = pd.to_datetime(merged["date_key"].astype(str), format="%Y%m%d").dt.dayofyear.to_numpy()
    season = 1 + 0.16 * np.cos(2 * np.pi * (doy - 15) / 365.25) + 0.07 * np.cos(4 * np.pi * doy / 365.25)
    temp = merged["temperature_c"].to_numpy()
    heat = np.maximum(12 - temp, 0) * 0.018
    cool = np.maximum(temp - 24, 0) * 0.022
    noise = rng.normal(0, 0.035, len(merged))
    demand = merged["base_mwh"].to_numpy() * season * (1 + heat + cool) * (1 + noise)
    demand = np.clip(demand, 50, None)
    peak = demand / 20 * (1 + rng.uniform(0.02, 0.12, len(merged)))
    return pd.DataFrame(
        {
            "demand_id": np.arange(1, len(merged) + 1),
            "location_id": merged["location_id"].to_numpy(),
            "date_key": merged["date_key"].to_numpy(),
            "demand_mwh": np.round(demand, 2),
            "peak_mw": np.round(peak, 2),
            "load_factor": np.round(demand / (peak * 24), 3),
        }
    )


def _maintenance_plan(
    assets: pd.DataFrame, dates: list[date], rng: np.random.Generator
) -> tuple[pd.DataFrame, np.ndarray]:
    rows = []
    maintenance_id = 1
    years = max(1, len(dates) / 365.25)
    for asset in assets.itertuples(index=False):
        planned = 3 if asset.on_maintenance_program else 1
        count = int(planned * years) + int(rng.integers(0, 2))
        chosen = rng.choice(len(dates), size=min(count, len(dates)), replace=False)
        for index in chosen:
            kind = "preventive" if asset.on_maintenance_program and rng.random() < 0.8 else "inspection"
            if rng.random() < 0.12:
                kind = "corrective"
            rows.append(
                {
                    "maintenance_id": maintenance_id,
                    "asset_id": int(asset.asset_id),
                    "location_id": int(asset.location_id),
                    "date_key": int(dates[int(index)].strftime("%Y%m%d")),
                    "maintenance_type": kind,
                    "cost_usd": int(rng.integers(800, 28000)),
                    "duration_hours": round(float(rng.uniform(2, 36)), 1),
                    "completed": 1,
                }
            )
            maintenance_id += 1
    frame = pd.DataFrame(rows)
    return frame, assets["on_maintenance_program"].to_numpy()


def _monthly_panel(
    assets: pd.DataFrame,
    weather: pd.DataFrame,
    demand: pd.DataFrame,
    maintenance: pd.DataFrame,
    on_program: np.ndarray,
    cfg: GenerateConfig,
    rng: np.random.Generator,
) -> pd.DataFrame:
    weather = weather.copy()
    weather["month"] = pd.to_datetime(weather["date_key"].astype(str), format="%Y%m%d").dt.to_period("M").astype(str)
    demand = demand.copy()
    demand["month"] = pd.to_datetime(demand["date_key"].astype(str), format="%Y%m%d").dt.to_period("M").astype(str)
    maintenance = maintenance.copy()
    maintenance["month"] = pd.to_datetime(maintenance["date_key"].astype(str), format="%Y%m%d").dt.to_period("M").astype(str)

    weather_m = weather.groupby(["location_id", "month"], as_index=False)["severity_score"].mean()
    demand_m = demand.groupby(["location_id", "month"], as_index=False)["demand_mwh"].mean()
    maint_m = (
        maintenance.groupby(["asset_id", "month"]).size().reset_index(name="maintenance_count")
    )

    months = _month_starts(cfg.start, cfg.end)
    month_labels = [f"{item.year}-{item.month:02d}" for item in months]
    prior_failures = np.zeros(len(assets), dtype=float)
    records: list[pd.DataFrame] = []
    asset_age = assets["age_years"].to_numpy(dtype=float)
    location_ids = assets["location_id"].to_numpy()
    asset_ids = assets["asset_id"].to_numpy()
    program = on_program.astype(float)

    for label in month_labels:
        severity = weather_m.loc[weather_m["month"] == label, ["location_id", "severity_score"]]
        load = demand_m.loc[demand_m["month"] == label, ["location_id", "demand_mwh"]]
        month_frame = assets[["asset_id", "location_id", "asset_type", "age_years"]].copy()
        month_frame["month"] = label
        month_frame = month_frame.merge(severity, on="location_id", how="left")
        month_frame = month_frame.merge(load, on="location_id", how="left")
        month_maint = maint_m.loc[maint_m["month"] == label, ["asset_id", "maintenance_count"]]
        month_frame = month_frame.merge(month_maint, on="asset_id", how="left")
        month_frame["maintenance_count"] = month_frame["maintenance_count"].fillna(0)
        month_frame["severity_score"] = month_frame["severity_score"].fillna(20)
        month_frame["demand_mwh"] = month_frame["demand_mwh"].fillna(month_frame["demand_mwh"].median())
        load_index = month_frame["demand_mwh"] / month_frame["demand_mwh"].median()
        maint_count = month_frame["maintenance_count"].to_numpy()
        severity_v = month_frame["severity_score"].to_numpy()
        outage_logit = (
            -2.55
            + 0.055 * (asset_age - 22)
            + 0.028 * (severity_v - 25)
            + 0.55 * (load_index.to_numpy() - 1)
            + 0.12 * prior_failures
            - 0.85 * program
            - 0.25 * maint_count
        )
        failure_logit = (
            -2.85
            + 0.07 * (asset_age - 22)
            + 0.012 * (severity_v - 25)
            + 0.22 * prior_failures
            - 0.7 * program
            - 0.2 * maint_count
        )
        outage = rng.random(len(month_frame)) < _sigmoid(outage_logit)
        failure = rng.random(len(month_frame)) < _sigmoid(failure_logit)
        month_frame["load_index"] = np.round(load_index, 3)
        month_frame["prior_failures"] = prior_failures
        month_frame["on_maintenance_program"] = program
        month_frame["outage"] = outage.astype(int)
        month_frame["equipment_failure"] = failure.astype(int)
        records.append(month_frame)
        prior_failures = prior_failures + failure.astype(float)

    panel = pd.concat(records, ignore_index=True)
    panel.insert(0, "asset_month_id", np.arange(1, len(panel) + 1))
    return panel


def _events_from_months(
    months: pd.DataFrame,
    assets: pd.DataFrame,
    weather: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    asset_lookup = assets.set_index("asset_id")
    weather = weather.copy()
    weather["month"] = pd.to_datetime(weather["date_key"].astype(str), format="%Y%m%d").dt.to_period("M").astype(str)
    outage_rows = []
    incident_rows = []
    outage_id = 1
    incident_id = 1
    outage_months = months.loc[months["outage"] == 1]
    failure_months = months.loc[months["equipment_failure"] == 1]

    for row in outage_months.itertuples(index=False):
        asset = asset_lookup.loc[row.asset_id]
        day = _random_day(weather, int(asset.location_id), row.month, rng)
        if day is None:
            continue
        severity = float(day.severity_score)
        if severity > 45 and rng.random() < 0.7:
            cause = "weather"
        elif int(asset.age_years) > 30 and rng.random() < 0.55:
            cause = "equipment_failure"
        elif float(row.load_index) > 1.15 and rng.random() < 0.4:
            cause = "overload"
        else:
            cause = str(rng.choice(["vegetation", "wildlife", "planned_work", "equipment_failure"]))
        duration = float(np.clip(rng.lognormal(mean=1.3, sigma=0.55), 0.4, 72))
        customers = int(asset.customer_exposure * rng.uniform(0.15, 0.9)) if cause != "planned_work" else 0
        outage_rows.append(
            {
                "outage_id": outage_id,
                "asset_id": int(row.asset_id),
                "location_id": int(asset.location_id),
                "date_key": int(day.date_key),
                "weather_id": int(day.weather_id),
                "duration_hours": round(duration, 2),
                "customers_affected": customers,
                "cause": cause,
                "outage_flag": 1,
            }
        )
        outage_id += 1

    for row in failure_months.itertuples(index=False):
        asset = asset_lookup.loc[row.asset_id]
        day = _random_day(weather, int(asset.location_id), row.month, rng)
        if day is None:
            continue
        category = "equipment_failure" if rng.random() < 0.8 else str(rng.choice(["protection_alarm", "safety"]))
        status = "open" if rng.random() < 0.08 else "closed"
        incident_rows.append(
            {
                "incident_id": incident_id,
                "asset_id": int(row.asset_id),
                "location_id": int(asset.location_id),
                "date_key": int(day.date_key),
                "weather_id": int(day.weather_id),
                "severity": str(rng.choice(["low", "medium", "high", "critical"], p=[0.2, 0.4, 0.28, 0.12])),
                "category": category,
                "description": _incident_text(str(asset.asset_name), category, str(asset.asset_type)),
                "status": status,
                "resolution_hours": 0 if status == "open" else round(float(rng.uniform(2, 90)), 1),
            }
        )
        incident_id += 1

    # A smaller set of non-failure incidents so root-cause views are not one bar.
    extra = assets.sample(n=min(40, len(assets)), random_state=int(rng.integers(0, 10_000)))
    for asset in extra.itertuples(index=False):
        day = weather.loc[weather["location_id"] == asset.location_id].sample(n=1, random_state=int(rng.integers(0, 10_000))).iloc[0]
        category = str(rng.choice(["environmental", "public_damage", "safety"]))
        incident_rows.append(
            {
                "incident_id": incident_id,
                "asset_id": int(asset.asset_id),
                "location_id": int(asset.location_id),
                "date_key": int(day.date_key),
                "weather_id": int(day.weather_id),
                "severity": "low",
                "category": category,
                "description": _incident_text(str(asset.asset_name), category, str(asset.asset_type)),
                "status": "closed",
                "resolution_hours": round(float(rng.uniform(1, 24)), 1),
            }
        )
        incident_id += 1

    return pd.DataFrame(outage_rows), pd.DataFrame(incident_rows)


def _random_day(
    weather: pd.DataFrame, location_id: int, month: str, rng: np.random.Generator
) -> pd.Series | None:
    subset = weather.loc[(weather["location_id"] == location_id) & (weather["month"] == month)]
    if subset.empty:
        return None
    return subset.sample(n=1, random_state=int(rng.integers(0, 1_000_000))).iloc[0]


def _incident_text(name: str, category: str, asset_type: str) -> str:
    templates = {
        "equipment_failure": f"{name} ({asset_type}) tripped on an internal equipment fault. Crew isolated the bay and transferred load.",
        "protection_alarm": f"Protection alarm on {name} cleared after a relay check. No customer interruption recorded.",
        "safety": f"Safety hold at {name} while the crew confirmed clearances. Work resumed the same shift.",
        "environmental": f"Environmental watch near {name} after oil-containment inspection. No release confirmed.",
        "public_damage": f"Public damage report filed against {name}. Field inspection found no immediate service risk.",
    }
    return templates.get(category, f"Incident recorded on {name}.")


def _sensors(
    assets: pd.DataFrame, dates: list[date], cfg: GenerateConfig, rng: np.random.Generator
) -> pd.DataFrame:
    chosen = assets.head(min(cfg.sensor_assets, len(assets)))
    window = dates[-min(cfg.sensor_days, len(dates)) :]
    rows = []
    reading_id = 1
    for asset in chosen.itertuples(index=False):
        baseline_vib = 2.2 + asset.age_years / 40
        for current in window:
            injected = int(rng.random() < 0.03)
            vibration = float(rng.normal(baseline_vib, 0.25))
            winding = float(rng.normal(55 + asset.age_years / 8, 3))
            load_pct = float(np.clip(rng.normal(0.62, 0.08), 0.2, 1.05))
            oil = float(rng.normal(42, 2.5))
            if injected:
                vibration += float(rng.uniform(1.4, 2.4))
                winding += float(rng.uniform(8, 14))
                oil -= float(rng.uniform(4, 8))
            rows.append(
                {
                    "reading_id": reading_id,
                    "asset_id": int(asset.asset_id),
                    "location_id": int(asset.location_id),
                    "date_key": int(current.strftime("%Y%m%d")),
                    "vibration_mm_s": round(vibration, 3),
                    "winding_temp_c": round(winding, 2),
                    "load_pct": round(load_pct, 3),
                    "oil_pressure_psi": round(oil, 2),
                    "injected_anomaly": injected,
                }
            )
            reading_id += 1
    return pd.DataFrame(rows)


def main() -> None:
    generate()


if __name__ == "__main__":
    main()
