# Power BI

The three dashboards below are the semantic model for Power BI Desktop. The same views are implemented in the Streamlit console so they can be opened without Power BI. Extracts are written to `extracts/` on every ETL run. Postgres users can ignore the CSVs and connect to the tables in `sql/`.

## Connect

1. Open Power BI Desktop.
2. Get data, Text/CSV, and load every file in `extracts/`. Promote headers.
3. Or get data from PostgreSQL (`localhost:54329`, database `ciri`) after `docker compose up`.
4. Model the relationships below.
5. Create the measures in `measures.dax`.
6. Build the three pages. Field lists match the Streamlit pages.

## Relationships

| From | To |
| --- | --- |
| `Fact_Outages.asset_id` | `Dim_Asset.asset_id` |
| `Fact_Outages.location_id` | `Dim_Location.location_id` |
| `Fact_Outages.date_key` | `Dim_Date.date_key` |
| `Fact_Outages.weather_id` | `Dim_Weather.weather_id` |
| `Fact_Incidents.asset_id` | `Dim_Asset.asset_id` |
| `Fact_Incidents.location_id` | `Dim_Location.location_id` |
| `Fact_Incidents.date_key` | `Dim_Date.date_key` |
| `Fact_EnergyDemand.location_id` | `Dim_Location.location_id` |
| `Fact_EnergyDemand.date_key` | `Dim_Date.date_key` |
| `Fact_Maintenance.asset_id` | `Dim_Asset.asset_id` |
| `Fact_Maintenance.location_id` | `Dim_Location.location_id` |
| `Fact_Maintenance.date_key` | `Dim_Date.date_key` |
| `Mart_AssetRisk.asset_id` | `Dim_Asset.asset_id` |
| `Mart_AssetRisk.location_id` | `Dim_Location.location_id` |
| `Ml_HealthScore.asset_id` | `Dim_Asset.asset_id` |
| `Ml_OutageScore.asset_id` | `Dim_Asset.asset_id` |
| `Ml_FailureScore.asset_id` | `Dim_Asset.asset_id` |
| `Dim_Asset.location_id` | `Dim_Location.location_id` |
| `Dim_Weather.location_id` | `Dim_Location.location_id` |
| `Dim_Weather.date_key` | `Dim_Date.date_key` |

Filter the date table on the fact tables. Do not filter `Mart_AssetRisk` by date; it is the current score.

## Executive dashboard

Cards: Total Assets, Active Incidents, Critical Risks, Predicted Failures, Energy Demand MWh.

Visuals:

- Stacked area of Energy Demand MWh by `Dim_Date` month and `Dim_Location.region`.
- Bar of Average Risk Score by region.
- Donut of assets by `Mart_AssetRisk.risk_label`.
- Slicers: region, year.

## Operations dashboard

- Table of asset name, type, city, health, risk score, risk label, failures, maintenance jobs.
- Map: `Dim_Location` latitude and longitude, bubble color = risk label. Power BI's map visual uses the location columns on `Mart_AssetRisk` directly.
- Heatmap (matrix): region by asset type, values = Average Risk Score.
- Line of Outage Count by month.
- Clustered bar of outage cause.
- Card: Maintenance Cost.

## Forecast dashboard

- Card: Forecast MWh (sum of `Ml_DemandForecast`).
- Line of `forecast_mwh` by `full_date`, legend region (join location).
- Bar of top 15 `Ml_OutageScore.outage_probability` by asset name.
- Card: Predicted Failures.
- Table of failure probability with region.

`Dim_RiskLevel` is the band lookup (min and max score) if you want a calculated column instead of the stored label. The stored `risk_label` is the one the API uses, so prefer it.
