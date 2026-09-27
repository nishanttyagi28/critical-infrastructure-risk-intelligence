-- KPI views used by Power BI and by analysts querying Postgres directly.
-- SQLite loads the same text.

CREATE VIEW "Vw_OutageTrend" AS
SELECT
    d.year,
    d.month,
    d.month_name,
    l.region,
    COUNT(*) AS outage_count,
    SUM(o.customers_affected) AS customers_affected,
    AVG(o.duration_hours) AS avg_duration_hours
FROM "Fact_Outages" o
JOIN "Dim_Date" d ON d.date_key = o.date_key
JOIN "Dim_Location" l ON l.location_id = o.location_id
GROUP BY d.year, d.month, d.month_name, l.region;

CREATE VIEW "Vw_RegionRisk" AS
SELECT
    region,
    COUNT(*) AS assets,
    AVG(risk_score) AS avg_risk_score,
    SUM(CASE WHEN risk_label = 'Critical' THEN 1 ELSE 0 END) AS critical_assets,
    SUM(CASE WHEN risk_label = 'High' THEN 1 ELSE 0 END) AS high_assets
FROM "Mart_AssetRisk"
GROUP BY region;

CREATE VIEW "Vw_ExecutiveKpi" AS
SELECT
    (SELECT COUNT(*) FROM "Dim_Asset") AS total_assets,
    (SELECT COUNT(*) FROM "Fact_Incidents" WHERE status = 'open') AS active_incidents,
    (SELECT COUNT(*) FROM "Mart_AssetRisk" WHERE risk_label = 'Critical') AS critical_risks,
    (SELECT COUNT(*) FROM "Ml_FailureScore" WHERE failure_probability >= 0.50) AS predicted_failures;
