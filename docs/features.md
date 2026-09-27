# Features

## Data engineering

`python -m ciri bootstrap` generates the grid, validates it, loads the warehouse, scores risk, and trains the models. The generator is seeded (`seed=42` for the full grid) so a second run reproduces the same history.

The history is not random noise. Monthly outage and equipment-failure draws use a logit that increases with age, weather severity, load, and prior failures, and decreases when the asset is on the preventive-maintenance program. Demand follows a winter peak, a smaller summer peak, and heating and cooling degree effects. Sensor anomalies are injected and labeled so the detector can be scored.

## Warehouse

Star schema in `sql/001_star_schema.sql`. KPI views in `sql/002_kpi_views.sql`.

`Dim_RiskLevel` stores the band edges. The current score for each asset is `Mart_AssetRisk`, a mart built after the facts load. It is not a source fact.

## Models

| Model | Question | Algorithm | Metrics |
| --- | --- | --- | --- |
| Outage | Will this asset-month have an outage? | Gradient boosting classifier, balanced sample weights | Accuracy, precision, recall, F1, ROC AUC |
| Failure | Will this asset-month have an equipment failure? | Same | Same |
| Demand | What is tomorrow's location demand, then the next 90 days? | Gradient boosting regressor on lags, day-of-year, temperature | RMSE, MAE |
| Health | What is the engineer's health score? | Gradient boosting regressor | RMSE, MAE |
| Anomaly | Which sensor-days are unusual? | Isolation Forest | Precision, recall, F1, ROC AUC against injected faults |

The holdout for the classifiers is the last 20 percent of months. Demand holds out the last 45 days. Health holds out the last 20 percent of assets. Future weather in the demand forecast is the historical average for that day of year, not a weather forecast.

Classification metrics are null on the regressors, and RMSE and MAE are null on the classifiers. The file is `models/metrics.json`.

## Risk score

Five components, 100 points:

| Signal | Full points when |
| --- | --- |
| Age | 35 years or older (25 points) |
| Historical failures | 5 outages or equipment failures in 365 days (25) |
| Weather severity | 30-day severity of 100 (20) |
| Maintenance | No completed jobs in 365 days (15). Four or more jobs remove this penalty |
| Energy load | Last 30 days at least 1.2 times the location's own median day (15) |

Bands: 0–24 Low, 25–49 Medium, 50–74 High, 75–100 Critical.

The failure probability is shown next to the score. They are not the same number.

## Operations analyst

The analyst builds a short numeric brief (KPIs, regions, causes, backlog, quarter demand) and answers from that brief. With `OPENAI_API_KEY` set, the same brief is sent to `POST {OPENAI_BASE_URL}/chat/completions`. The system prompt forbids numbers that are not in the brief. If the call fails, the local answer is used.

Questions the local analyst routes directly:

- Which regions have the highest outage risk?
- What caused most failures this month?
- Which assets require preventive maintenance?
- What is the projected demand next quarter?
- Give me an executive summary.

## Scenario simulation

The risk page and `POST /scenarios` recompute bands after a weather-severity shock and a load multiplier. Age and maintenance history stay fixed.

## MLOps

Each training run appends `models/experiments.jsonl` and rewrites `models/registry.json` with a bumped patch version, a data hash, parameters, and metrics. Set `CIRI_MLFLOW=1` if MLflow is installed and the same metrics should be logged there.

`.github/workflows/ci.yml` runs the test suite. `.github/workflows/refresh.yml` rebuilds a short grid and retrains on a weekly schedule or on demand.
