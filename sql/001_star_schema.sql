-- AetherGrid star schema. Identifiers are quoted so Postgres keeps the
-- case used by the semantic model and the Python warehouse.

DROP VIEW IF EXISTS "Vw_ExecutiveKpi";
DROP VIEW IF EXISTS "Vw_OutageTrend";
DROP VIEW IF EXISTS "Vw_RegionRisk";

DROP TABLE IF EXISTS "Ml_DemandForecast";
DROP TABLE IF EXISTS "Ml_OutageScore";
DROP TABLE IF EXISTS "Ml_FailureScore";
DROP TABLE IF EXISTS "Ml_HealthScore";
DROP TABLE IF EXISTS "Ml_Anomaly";
DROP TABLE IF EXISTS "Mart_AssetRisk";
DROP TABLE IF EXISTS "Fs_AssetMonth";
DROP TABLE IF EXISTS "Ops_SensorReading";
DROP TABLE IF EXISTS "Fact_Outages";
DROP TABLE IF EXISTS "Fact_Incidents";
DROP TABLE IF EXISTS "Fact_EnergyDemand";
DROP TABLE IF EXISTS "Fact_Maintenance";
DROP TABLE IF EXISTS "Dim_Weather";
DROP TABLE IF EXISTS "Dim_Asset";
DROP TABLE IF EXISTS "Dim_Location";
DROP TABLE IF EXISTS "Dim_Date";
DROP TABLE IF EXISTS "Dim_RiskLevel";

CREATE TABLE "Dim_Date" (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name TEXT NOT NULL,
    is_weekend INTEGER NOT NULL,
    iso_week INTEGER NOT NULL
);

CREATE TABLE "Dim_Location" (
    location_id INTEGER PRIMARY KEY,
    region TEXT NOT NULL,
    city TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    grid_zone TEXT NOT NULL,
    criticality TEXT NOT NULL,
    base_mwh INTEGER NOT NULL,
    temp_delta REAL NOT NULL
);

CREATE TABLE "Dim_Asset" (
    asset_id INTEGER PRIMARY KEY,
    asset_name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    location_id INTEGER NOT NULL,
    commissioned_date TEXT NOT NULL,
    age_years INTEGER NOT NULL,
    manufacturer TEXT NOT NULL,
    capacity_mw INTEGER NOT NULL,
    voltage_kv INTEGER NOT NULL,
    customer_exposure INTEGER NOT NULL,
    status TEXT NOT NULL,
    on_maintenance_program INTEGER NOT NULL,
    FOREIGN KEY (location_id) REFERENCES "Dim_Location" (location_id)
);

CREATE TABLE "Dim_Weather" (
    weather_id INTEGER PRIMARY KEY,
    location_id INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    temperature_c REAL NOT NULL,
    wind_speed_kmh REAL NOT NULL,
    precipitation_mm REAL NOT NULL,
    storm_flag INTEGER NOT NULL,
    severity_score REAL NOT NULL,
    FOREIGN KEY (location_id) REFERENCES "Dim_Location" (location_id),
    FOREIGN KEY (date_key) REFERENCES "Dim_Date" (date_key)
);

CREATE TABLE "Dim_RiskLevel" (
    risk_level_id INTEGER PRIMARY KEY,
    risk_label TEXT NOT NULL,
    min_score INTEGER NOT NULL,
    max_score INTEGER NOT NULL
);

CREATE TABLE "Fact_Outages" (
    outage_id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    weather_id INTEGER NOT NULL,
    duration_hours REAL NOT NULL,
    customers_affected INTEGER NOT NULL,
    cause TEXT NOT NULL,
    outage_flag INTEGER NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES "Dim_Asset" (asset_id),
    FOREIGN KEY (location_id) REFERENCES "Dim_Location" (location_id),
    FOREIGN KEY (date_key) REFERENCES "Dim_Date" (date_key),
    FOREIGN KEY (weather_id) REFERENCES "Dim_Weather" (weather_id)
);

CREATE TABLE "Fact_Incidents" (
    incident_id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    weather_id INTEGER NOT NULL,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    resolution_hours REAL NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES "Dim_Asset" (asset_id),
    FOREIGN KEY (location_id) REFERENCES "Dim_Location" (location_id),
    FOREIGN KEY (date_key) REFERENCES "Dim_Date" (date_key)
);

CREATE TABLE "Fact_EnergyDemand" (
    demand_id INTEGER PRIMARY KEY,
    location_id INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    demand_mwh REAL NOT NULL,
    peak_mw REAL NOT NULL,
    load_factor REAL NOT NULL,
    FOREIGN KEY (location_id) REFERENCES "Dim_Location" (location_id),
    FOREIGN KEY (date_key) REFERENCES "Dim_Date" (date_key)
);

CREATE TABLE "Fact_Maintenance" (
    maintenance_id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,
    cost_usd INTEGER NOT NULL,
    duration_hours REAL NOT NULL,
    completed INTEGER NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES "Dim_Asset" (asset_id),
    FOREIGN KEY (location_id) REFERENCES "Dim_Location" (location_id),
    FOREIGN KEY (date_key) REFERENCES "Dim_Date" (date_key)
);

CREATE TABLE "Ops_SensorReading" (
    reading_id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    vibration_mm_s REAL NOT NULL,
    winding_temp_c REAL NOT NULL,
    load_pct REAL NOT NULL,
    oil_pressure_psi REAL NOT NULL,
    injected_anomaly INTEGER NOT NULL
);

CREATE TABLE "Fs_AssetMonth" (
    asset_month_id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL,
    age_years INTEGER NOT NULL,
    month TEXT NOT NULL,
    severity_score REAL NOT NULL,
    demand_mwh REAL NOT NULL,
    maintenance_count REAL NOT NULL,
    load_index REAL NOT NULL,
    prior_failures REAL NOT NULL,
    on_maintenance_program REAL NOT NULL,
    outage INTEGER NOT NULL,
    equipment_failure INTEGER NOT NULL
);

CREATE TABLE "Mart_AssetRisk" (
    asset_id INTEGER PRIMARY KEY,
    asset_name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    location_id INTEGER NOT NULL,
    region TEXT NOT NULL,
    city TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    age_years INTEGER NOT NULL,
    failures_365d INTEGER NOT NULL,
    weather_severity_30d REAL NOT NULL,
    maintenance_365d INTEGER NOT NULL,
    load_index REAL NOT NULL,
    risk_score REAL NOT NULL,
    risk_label TEXT NOT NULL
);

CREATE TABLE "Ml_OutageScore" (
    asset_id INTEGER PRIMARY KEY,
    month TEXT NOT NULL,
    outage_probability REAL NOT NULL
);

CREATE TABLE "Ml_FailureScore" (
    asset_id INTEGER PRIMARY KEY,
    month TEXT NOT NULL,
    failure_probability REAL NOT NULL
);

CREATE TABLE "Ml_HealthScore" (
    asset_id INTEGER PRIMARY KEY,
    health_score REAL NOT NULL
);

CREATE TABLE "Ml_DemandForecast" (
    location_id INTEGER NOT NULL,
    full_date TEXT NOT NULL,
    forecast_mwh REAL NOT NULL,
    horizon_day INTEGER NOT NULL
);

CREATE TABLE "Ml_Anomaly" (
    reading_id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    anomaly_flag INTEGER NOT NULL,
    anomaly_score REAL NOT NULL
);

CREATE INDEX idx_outage_date ON "Fact_Outages" (date_key);
CREATE INDEX idx_incident_date ON "Fact_Incidents" (date_key);
CREATE INDEX idx_demand_date ON "Fact_EnergyDemand" (date_key);
CREATE INDEX idx_weather_loc_date ON "Dim_Weather" (location_id, date_key);
