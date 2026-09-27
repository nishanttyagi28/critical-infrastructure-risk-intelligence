"""Operations API.

Run from the project root:

    PYTHONPATH=src uvicorn api.main:app --port 8766
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ciri import __version__
from ciri.analytics.advanced import scenario_summary
from ciri.analytics.queries import (
    correlation_frame,
    demand_trend,
    executive_kpis,
    maintenance_backlog,
    outage_trend,
    quarterly_demand,
    region_risk,
    root_causes,
)
from ciri.llm.analyst import answer_question, summarize_outages
from ciri.ml.predict import explain_asset
from ciri.mlops.registry import load_registry
from ciri.warehouse.store import Warehouse

app = FastAPI(
    title="Critical Infrastructure Risk Intelligence Platform",
    version=__version__,
    description="AetherGrid warehouse, risk scores, forecasts, and the operations analyst.",
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class ScenarioRequest(BaseModel):
    weather_delta: float = Field(0, ge=-30, le=40)
    load_factor: float = Field(1.0, ge=0.5, le=1.8)


def _warehouse() -> Warehouse:
    warehouse = Warehouse()
    if not warehouse.ready():
        raise HTTPException(status_code=503, detail="Warehouse is empty. Run python -m ciri bootstrap.")
    return warehouse


@app.get("/health")
def health() -> dict[str, str]:
    warehouse = Warehouse()
    return {
        "status": "ok" if warehouse.ready() else "empty",
        "backend": warehouse.backend_name(),
        "version": __version__,
    }


@app.get("/kpis")
def kpis() -> dict[str, float]:
    return executive_kpis(_warehouse())


@app.get("/assets")
def assets(region: str | None = None, risk: str | None = None) -> list[dict[str, object]]:
    frame = _warehouse().read("Mart_AssetRisk")
    if region:
        frame = frame.loc[frame["region"] == region]
    if risk:
        frame = frame.loc[frame["risk_label"] == risk]
    return frame.to_dict(orient="records")


@app.get("/assets/{asset_id}")
def asset_detail(asset_id: int) -> dict[str, object]:
    warehouse = _warehouse()
    risk = warehouse.read("Mart_AssetRisk")
    match = risk.loc[risk["asset_id"] == asset_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="Asset not found")
    payload = match.iloc[0].to_dict()
    payload["explanation"] = explain_asset(asset_id, warehouse)
    return payload


@app.get("/risk/regions")
def regions() -> list[dict[str, object]]:
    return region_risk(_warehouse()).to_dict(orient="records")


@app.get("/incidents")
def incidents(status: str | None = None) -> list[dict[str, object]]:
    frame = _warehouse().read("Fact_Incidents")
    if status:
        frame = frame.loc[frame["status"] == status]
    return frame.sort_values("date_key", ascending=False).head(200).to_dict(orient="records")


@app.get("/forecast/demand")
def forecast_demand() -> dict[str, object]:
    warehouse = _warehouse()
    return {
        "quarter": quarterly_demand(warehouse),
        "series": warehouse.read("Ml_DemandForecast").to_dict(orient="records"),
    }


@app.get("/forecast/outages")
def forecast_outages() -> list[dict[str, object]]:
    frame = _warehouse().read("Ml_OutageScore").sort_values("outage_probability", ascending=False)
    return frame.head(50).to_dict(orient="records")


@app.get("/analytics/correlation")
def correlation() -> dict[str, object]:
    frame = correlation_frame(_warehouse())
    return {"columns": list(frame.columns), "values": frame.round(3).values.tolist()}


@app.get("/analytics/root-causes")
def causes() -> dict[str, list[dict[str, object]]]:
    bundle = root_causes(_warehouse())
    return {
        "incidents": bundle["incidents"].to_dict(orient="records"),
        "outages": bundle["outages"].to_dict(orient="records"),
    }


@app.get("/analytics/demand-trend")
def demand() -> list[dict[str, object]]:
    frame = demand_trend(_warehouse())
    frame["period"] = frame["period"].astype(str)
    return frame.to_dict(orient="records")


@app.get("/analytics/outage-trend")
def outages() -> list[dict[str, object]]:
    frame = outage_trend(_warehouse())
    frame["period"] = frame["period"].astype(str)
    return frame.to_dict(orient="records")


@app.post("/scenarios")
def scenarios(body: ScenarioRequest) -> dict[str, object]:
    return scenario_summary(_warehouse(), weather_delta=body.weather_delta, load_factor=body.load_factor)


@app.post("/ask")
def ask(body: AskRequest) -> dict[str, object]:
    result = answer_question(body.question, _warehouse())
    return {
        "question": result.question,
        "answer": result.answer,
        "recommendations": result.recommendations,
        "source": result.source,
    }


@app.get("/reports/outage-summary")
def outage_summary() -> dict[str, str]:
    return {"summary": summarize_outages(_warehouse())}


@app.get("/maintenance/backlog")
def backlog() -> list[dict[str, object]]:
    return maintenance_backlog(_warehouse()).to_dict(orient="records")


@app.get("/models/registry")
def registry() -> dict[str, object]:
    return load_registry()
