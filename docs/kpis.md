# KPI definitions

All figures are computed from the warehouse after bootstrap. They describe the demonstration grid.

| KPI | Definition | Where it is shown |
| --- | --- | --- |
| Total assets | Count of `Dim_Asset` | Executive, API `/kpis` |
| Active incidents | `Fact_Incidents` with `status = open` | Executive, API `/kpis` |
| Critical risks | `Mart_AssetRisk.risk_label = Critical` | Executive |
| High risks | `risk_label = High` | Executive region table |
| Predicted failures | Assets whose latest `failure_probability` is at least 0.50 | Executive, forecast page |
| Predicted outages | Assets whose latest `outage_probability` is at least 0.50 | Executive |
| Energy demand, last 30 days | Sum of `Fact_EnergyDemand.demand_mwh` over the last 30 dates | Executive |
| Demand change | Last 30 days minus the prior 30 days | Executive delta |
| Average risk by region | Mean `risk_score` | Executive, risk page |
| Trailing 90-day demand | Sum of actual MWh | Forecast page |
| Next quarter demand | Sum of `Ml_DemandForecast` over 90 days | Forecast page, analyst |
| Outage count | Count of `Fact_Outages` in the window | Incident explorer |
| Customers affected | Sum of `customers_affected` | Incident explorer |
| Maintenance backlog | Risk score descending among assets with at most one job in 365 days | Assistant, API `/maintenance/backlog` |
| Anomaly flags | Sensor-days the isolation forest marks | `Ml_Anomaly` |

`Vw_ExecutiveKpi`, `Vw_OutageTrend`, and `Vw_RegionRisk` expose the same definitions to SQL and to Power BI.
