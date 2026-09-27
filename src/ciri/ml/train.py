"""Train the five models and write scores back to the warehouse.

Classification models report accuracy, precision, recall, F1, and ROC AUC.
Regression models report RMSE and MAE. Anomaly detection is unsupervised
Isolation Forest, scored against the anomalies the generator injected.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, IsolationForest
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.utils.class_weight import compute_sample_weight

from ciri.config import MODEL_DIR
from ciri.errors import ModelError
from ciri.logging_utils import get_logger, log_stage
from ciri.mlops.registry import frame_digest, record_experiment
from ciri.warehouse.store import Warehouse

logger = get_logger(__name__)

CLASSIFIER_FEATURES = [
    "age_years",
    "severity_score",
    "load_index",
    "maintenance_count",
    "prior_failures",
    "on_maintenance_program",
]


def train_all(warehouse: Warehouse | None = None, model_dir: Path | None = None) -> dict[str, object]:
    """Fit every model on the current warehouse and store predictions."""
    wh = warehouse or Warehouse()
    target = model_dir or MODEL_DIR
    target.mkdir(parents=True, exist_ok=True)
    if not wh.ready():
        raise ModelError("warehouse is empty; run the ETL before training")

    months = wh.read("Fs_AssetMonth")
    demand = wh.read("Fact_EnergyDemand")
    weather = wh.read("Dim_Weather")
    dates = wh.read("Dim_Date")
    sensors = wh.read("Ops_SensorReading")
    assets = wh.read("Dim_Asset")

    outage_metrics, outage_scores = _train_classifier(months, "outage", target / "outage_model.joblib")
    failure_metrics, failure_scores = _train_classifier(
        months, "equipment_failure", target / "failure_model.joblib"
    )
    demand_metrics, demand_forecast = _train_demand(demand, weather, dates, target / "demand_model.joblib")
    health_metrics, health_scores = _train_health(months, assets, target / "health_model.joblib")
    anomaly_metrics, anomaly_scores = _train_anomaly(sensors, target / "anomaly_model.joblib")

    wh.replace(outage_scores, "Ml_OutageScore")
    wh.replace(failure_scores, "Ml_FailureScore")
    wh.replace(demand_forecast, "Ml_DemandForecast")
    wh.replace(health_scores, "Ml_HealthScore")
    wh.replace(anomaly_scores, "Ml_Anomaly")

    metrics = {
        "outage": outage_metrics,
        "failure": failure_metrics,
        "demand": demand_metrics,
        "health": health_metrics,
        "anomaly": anomaly_metrics,
    }
    (target / "metrics.json").write_text(pd.Series(metrics).to_json(indent=2), encoding="utf-8")
    document = record_experiment(
        metrics=metrics,
        params={"algorithm": "gradient_boosting", "anomaly": "isolation_forest", "seed": 42},
        data_hash=frame_digest(months),
        model_dir=target,
    )
    log_stage(logger, "train", models=5, version=str(document["version"]))
    return document


def _classification_metrics(y_true: np.ndarray, proba: np.ndarray) -> dict[str, float | None]:
    pred = (proba >= 0.5).astype(int)
    metrics: dict[str, float | None] = {
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": None,
        "rmse": None,
        "mae": None,
    }
    if len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, proba))
    return metrics


def _regression_metrics(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float | None]:
    return {
        "accuracy": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "roc_auc": None,
        "rmse": float(np.sqrt(mean_squared_error(y_true, pred))),
        "mae": float(mean_absolute_error(y_true, pred)),
    }


def _matrix(frame: pd.DataFrame) -> pd.DataFrame:
    matrix = frame[CLASSIFIER_FEATURES].astype(float).copy()
    types = pd.get_dummies(frame["asset_type"], prefix="type")
    return pd.concat([matrix, types], axis=1)


def _align(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    matrix = _matrix(frame)
    for column in columns:
        if column not in matrix.columns:
            matrix[column] = 0.0
    return matrix[columns].astype(float)


def _train_classifier(
    months: pd.DataFrame, label: str, path: Path
) -> tuple[dict[str, float | None], pd.DataFrame]:
    ordered = months.sort_values(["month", "asset_id"]).reset_index(drop=True)
    unique_months = list(ordered["month"].drop_duplicates())
    cut = max(1, int(len(unique_months) * 0.8))
    train_months = set(unique_months[:cut])
    train = ordered.loc[ordered["month"].isin(train_months)]
    test = ordered.loc[~ordered["month"].isin(train_months)]
    if test.empty:
        test = train.tail(max(1, len(train) // 5))
        train = train.iloc[: len(train) - len(test)]
    x_train = _matrix(train)
    labels = train[label].astype(int)
    model = GradientBoostingClassifier(random_state=42, max_depth=3, n_estimators=80, learning_rate=0.08)
    model.fit(x_train, labels, sample_weight=compute_sample_weight("balanced", labels))
    x_test = _align(test, list(x_train.columns))
    proba = model.predict_proba(x_test)[:, 1]
    metrics = _classification_metrics(test[label].to_numpy().astype(int), proba)
    latest_month = ordered["month"].max()
    latest = ordered.loc[ordered["month"] == latest_month].copy()
    latest_x = _align(latest, list(x_train.columns))
    latest["probability"] = model.predict_proba(latest_x)[:, 1]
    column = "outage_probability" if label == "outage" else "failure_probability"
    scores = latest[["asset_id", "month", "probability"]].rename(columns={"probability": column})
    scores["asset_id"] = scores["asset_id"].astype(int)
    joblib.dump({"model": model, "columns": list(x_train.columns), "label": label}, path)
    logger.info("trained %s roc_auc=%s f1=%s", label, metrics["roc_auc"], metrics["f1"])
    return metrics, scores.reset_index(drop=True)


def _train_health(
    months: pd.DataFrame, assets: pd.DataFrame, path: Path
) -> tuple[dict[str, float | None], pd.DataFrame]:
    latest = months.sort_values("month").groupby("asset_id", as_index=False).tail(1)
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 3.5, len(latest))
    health = (
        96
        - 1.15 * latest["age_years"].to_numpy()
        - 6.5 * latest["prior_failures"].to_numpy()
        + 8.0 * latest["on_maintenance_program"].to_numpy()
        + noise
    )
    health = np.clip(health, 5, 99)
    features = latest[["age_years", "prior_failures", "maintenance_count", "severity_score", "load_index"]].astype(float)
    types = pd.get_dummies(latest["asset_type"], prefix="type")
    matrix = pd.concat([features.reset_index(drop=True), types.reset_index(drop=True)], axis=1)
    # Hold out 20 percent of assets. The target uses the maintenance program,
    # which the model does not see directly.
    cut = max(1, int(len(matrix) * 0.8))
    model = GradientBoostingRegressor(random_state=42, max_depth=3, n_estimators=80)
    model.fit(matrix.iloc[:cut], health[:cut])
    pred = model.predict(matrix.iloc[cut:])
    metrics = _regression_metrics(health[cut:], pred)
    all_pred = np.clip(model.predict(matrix), 0, 100)
    scores = pd.DataFrame({"asset_id": latest["asset_id"].astype(int).to_numpy(), "health_score": np.round(all_pred, 2)})
    joblib.dump({"model": model, "columns": list(matrix.columns)}, path)
    logger.info("trained health rmse=%s mae=%s", metrics["rmse"], metrics["mae"])
    return metrics, scores


def _train_demand(
    demand: pd.DataFrame, weather: pd.DataFrame, dates: pd.DataFrame, path: Path
) -> tuple[dict[str, float | None], pd.DataFrame]:
    frame = demand.merge(dates[["date_key", "full_date"]], on="date_key", how="left")
    frame = frame.merge(weather[["location_id", "date_key", "temperature_c"]], on=["location_id", "date_key"], how="left")
    frame["full_date"] = pd.to_datetime(frame["full_date"])
    frame = frame.sort_values(["location_id", "full_date"])
    grouped = frame.groupby("location_id", group_keys=False)
    frame["lag_1"] = grouped["demand_mwh"].shift(1)
    frame["lag_7"] = grouped["demand_mwh"].shift(7)
    frame["lag_14"] = grouped["demand_mwh"].shift(14)
    doy = frame["full_date"].dt.dayofyear
    frame["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    frame["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    model_frame = frame.dropna(subset=["lag_1", "lag_7", "lag_14"]).copy()
    feature_cols = ["lag_1", "lag_7", "lag_14", "sin_doy", "cos_doy", "temperature_c", "location_id"]
    cutoff = model_frame["full_date"].max() - pd.Timedelta(days=45)
    train = model_frame.loc[model_frame["full_date"] < cutoff]
    test = model_frame.loc[model_frame["full_date"] >= cutoff]
    if train.empty or test.empty:
        train = model_frame.iloc[: int(len(model_frame) * 0.8)]
        test = model_frame.iloc[int(len(model_frame) * 0.8) :]
    model = GradientBoostingRegressor(random_state=42, max_depth=3, n_estimators=100)
    model.fit(train[feature_cols], train["demand_mwh"])
    pred = model.predict(test[feature_cols])
    metrics = _regression_metrics(test["demand_mwh"].to_numpy(), pred)
    forecast = _forecast_horizon(model_frame, model, feature_cols, horizon=90)
    joblib.dump({"model": model, "columns": feature_cols}, path)
    logger.info("trained demand rmse=%s mae=%s", metrics["rmse"], metrics["mae"])
    return metrics, forecast


def _forecast_horizon(
    history: pd.DataFrame,
    model: GradientBoostingRegressor,
    columns: list[str],
    horizon: int,
) -> pd.DataFrame:
    """Walk each location forward. Future temperature is the climatology of that day-of-year."""
    climatology = history.groupby(history["full_date"].dt.dayofyear)["temperature_c"].mean()
    rows = []
    for location_id, group in history.groupby("location_id"):
        group = group.sort_values("full_date")
        lags = list(group["demand_mwh"].tail(14))
        cursor = group["full_date"].max()
        for step in range(1, horizon + 1):
            cursor = cursor + pd.Timedelta(days=1)
            doy = int(cursor.dayofyear)
            temp = float(climatology.get(doy, climatology.mean()))
            features = {
                "lag_1": lags[-1],
                "lag_7": lags[-7],
                "lag_14": lags[-14],
                "sin_doy": np.sin(2 * np.pi * doy / 365.25),
                "cos_doy": np.cos(2 * np.pi * doy / 365.25),
                "temperature_c": temp,
                "location_id": location_id,
            }
            predicted = float(model.predict(pd.DataFrame([features])[columns])[0])
            predicted = max(predicted, 0.0)
            lags.append(predicted)
            rows.append(
                {
                    "location_id": int(location_id),
                    "full_date": cursor.date().isoformat(),
                    "forecast_mwh": round(predicted, 2),
                    "horizon_day": step,
                }
            )
    return pd.DataFrame(rows)


def _train_anomaly(sensors: pd.DataFrame, path: Path) -> tuple[dict[str, float | None], pd.DataFrame]:
    features = ["vibration_mm_s", "winding_temp_c", "load_pct", "oil_pressure_psi"]
    model = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
    model.fit(sensors[features])
    scores = -model.decision_function(sensors[features])
    flags = (model.predict(sensors[features]) == -1).astype(int)
    y_true = sensors["injected_anomaly"].to_numpy().astype(int)
    # Higher anomaly_score means more unusual. Rank-normalize for ROC AUC.
    rank = (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)
    metrics = _classification_metrics(y_true, rank)
    metrics["precision"] = float(precision_score(y_true, flags, zero_division=0))
    metrics["recall"] = float(recall_score(y_true, flags, zero_division=0))
    metrics["f1"] = float(f1_score(y_true, flags, zero_division=0))
    metrics["accuracy"] = float(accuracy_score(y_true, flags))
    output = pd.DataFrame(
        {
            "reading_id": sensors["reading_id"].astype(int),
            "asset_id": sensors["asset_id"].astype(int),
            "date_key": sensors["date_key"].astype(int),
            "anomaly_flag": flags,
            "anomaly_score": np.round(scores, 4),
        }
    )
    joblib.dump({"model": model, "columns": features}, path)
    logger.info("trained anomaly f1=%s roc_auc=%s", metrics["f1"], metrics["roc_auc"])
    return metrics, output


def main() -> None:
    train_all()


if __name__ == "__main__":
    main()
