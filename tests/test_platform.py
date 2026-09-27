"""Generate, load, train, and ask a question on a short grid."""

from datetime import date

import pandas as pd
from fastapi.testclient import TestClient

from ciri.analytics.queries import region_risk
from ciri.data.generate import GenerateConfig, build_datasets
from ciri.etl.pipeline import run_etl
from ciri.llm.analyst import answer_question
from ciri.ml.train import train_all
from ciri.warehouse.store import Warehouse

TINY = GenerateConfig(
    seed=7,
    start=date(2024, 1, 1),
    end=date(2024, 8, 31),
    locations_per_region=1,
    assets_per_location=4,
    sensor_assets=16,
    sensor_days=50,
)


def _build(tmp_path):
    frames = build_datasets(TINY)
    raw = tmp_path / "raw"
    for name, frame in frames.items():
        raw.mkdir(parents=True, exist_ok=True)
        frame.to_csv(raw / f"{name}.csv", index=False)
    warehouse = Warehouse(f"sqlite:///{tmp_path / 'ciri.db'}")
    run_etl(raw_dir=raw, warehouse=warehouse, processed_dir=tmp_path / "processed")
    train_all(warehouse, model_dir=tmp_path / "models")
    return frames, warehouse


def test_generator_covers_the_star_schema():
    frames = build_datasets(TINY)
    assert len(frames["Dim_Location"]) == 8
    assert len(frames["Dim_Asset"]) == 32
    assert frames["Fact_Outages"]["outage_id"].is_unique
    assert frames["Fact_EnergyDemand"]["demand_mwh"].min() > 0
    assert set(frames["Dim_RiskLevel"]["risk_label"]) == {"Low", "Medium", "High", "Critical"}


def test_etl_trains_and_answers(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    frames, warehouse = _build(tmp_path)
    assert warehouse.ready()
    risk = warehouse.read("Mart_AssetRisk")
    assert len(risk) == len(frames["Dim_Asset"])
    assert set(risk["risk_label"]).issubset({"Low", "Medium", "High", "Critical"})
    regions = region_risk(warehouse)
    assert not regions.empty
    outage = warehouse.read("Ml_OutageScore")
    assert outage["outage_probability"].between(0, 1).all()
    import json

    metrics = json.loads((tmp_path / "models" / "metrics.json").read_text(encoding="utf-8"))
    # The short panel (32 assets, eight months) is noisier than the full grid.
    # Full-grid outage ROC AUC in models/metrics.json is above 0.70.
    assert metrics["outage"]["roc_auc"] > 0.62
    assert metrics["failure"]["roc_auc"] > 0.65
    assert metrics["demand"]["rmse"] > 0
    assert metrics["health"]["mae"] is not None
    assert metrics["anomaly"]["roc_auc"] > 0.7
    answer = answer_question("Which regions have the highest outage risk?", warehouse)
    assert answer.source == "warehouse"
    assert answer.answer
    assert answer.recommendations
    quarter = answer_question("What is the projected demand next quarter?", warehouse)
    assert "MWh" in quarter.answer


def test_api_health_and_ask(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _frames, warehouse = _build(tmp_path)
    monkeypatch.setattr("api.main.Warehouse", lambda: warehouse)
    from api.main import app

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    kpis = client.get("/kpis")
    assert kpis.status_code == 200
    assert kpis.json()["total_assets"] == 32
    asked = client.post("/ask", json={"question": "Which assets require preventive maintenance?"})
    assert asked.status_code == 200
    assert asked.json()["source"] == "warehouse"
    shock = client.post("/scenarios", json={"weather_delta": 15, "load_factor": 1.2})
    assert shock.status_code == 200
    assert "assets_now_critical" in shock.json()
    missing = client.get("/assets/999999")
    assert missing.status_code == 404
