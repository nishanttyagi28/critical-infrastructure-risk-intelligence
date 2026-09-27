"""Answer operating questions from the warehouse.

When OPENAI_API_KEY is set, the question and a grounded context packet are
sent to an OpenAI-compatible chat endpoint. The model is instructed to use
only that packet. If the key is missing, or the call fails, the same packet
is rendered by the local analyst so the console still answers.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import pandas as pd

from ciri.analytics.queries import (
    executive_kpis,
    maintenance_backlog,
    quarterly_demand,
    region_risk,
    root_causes,
)
from ciri.config import openai_settings
from ciri.logging_utils import get_logger
from ciri.warehouse.store import Warehouse

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are the AetherGrid operations analyst. Answer only from the warehouse "
    "context. Do not invent assets, regions, or figures. If the context does not "
    "contain the answer, say what is missing. Close with three operational "
    "recommendations that follow from the figures."
)


@dataclass(frozen=True)
class AnalystAnswer:
    question: str
    answer: str
    recommendations: list[str]
    source: str
    context: str


def answer_question(question: str, warehouse: Warehouse) -> AnalystAnswer:
    """Answer one natural-language question."""
    context = build_context(warehouse)
    remote = _remote_answer(question, context)
    if remote is not None:
        return AnalystAnswer(
            question=question,
            answer=remote,
            recommendations=_recommendations(question, warehouse),
            source="openai-compatible",
            context=context,
        )
    local = _local_answer(question, warehouse)
    return AnalystAnswer(
        question=question,
        answer=local,
        recommendations=_recommendations(question, warehouse),
        source="warehouse",
        context=context,
    )


def build_context(warehouse: Warehouse) -> str:
    """Compact, numeric brief the model is allowed to use."""
    kpis = executive_kpis(warehouse)
    regions = region_risk(warehouse).head(5)
    causes = root_causes(warehouse, trailing_days=30)
    quarter = quarterly_demand(warehouse)
    backlog = maintenance_backlog(warehouse, limit=5)
    lines = [
        "Executive KPIs:",
        f"- assets: {int(kpis['total_assets'])}",
        f"- open incidents: {int(kpis['active_incidents'])}",
        f"- critical risk assets: {int(kpis['critical_risks'])}",
        f"- high risk assets: {int(kpis['high_risks'])}",
        f"- assets with failure probability >= 0.50: {int(kpis['predicted_failures'])}",
        f"- assets with outage probability >= 0.50: {int(kpis['predicted_outages'])}",
        f"- energy demand last 30 days MWh: {kpis['demand_last_30d_mwh']:.0f}",
        f"- energy demand prior 30 days MWh: {kpis['demand_prior_30d_mwh']:.0f}",
        "Regions by average risk score:",
    ]
    for row in regions.itertuples(index=False):
        lines.append(
            f"- {row.region}: avg {row.avg_risk:.1f}, critical {int(row.critical)}, high {int(row.high)}"
        )
    lines.append("Outage causes in the last 30 days:")
    if causes["outages"].empty:
        lines.append("- none")
    else:
        for row in causes["outages"].itertuples(index=False):
            lines.append(f"- {row.cause}: {int(row.outages)} outages, {int(row.customers)} customers")
    lines.append("Incident categories in the last 30 days:")
    if causes["incidents"].empty:
        lines.append("- none")
    else:
        for row in causes["incidents"].itertuples(index=False):
            lines.append(f"- {row.category}: {int(row.incidents)}")
    lines.append(
        "Demand: trailing 90 days "
        f"{quarter['trailing_90d_mwh']:.0f} MWh; next 90 days forecast "
        f"{quarter['next_quarter_mwh']:.0f} MWh."
    )
    lines.append("Assets that need preventive maintenance (high score, at most one job in 365 days):")
    if backlog.empty:
        lines.append("- none")
    else:
        for row in backlog.itertuples(index=False):
            lines.append(
                f"- {row.asset_name} in {row.city} ({row.region}), {row.risk_label}, score {row.risk_score:.1f}"
            )
    return "\n".join(lines)


def _remote_answer(question: str, context: str) -> str | None:
    settings = openai_settings()
    if not settings["api_key"]:
        return None
    payload = {
        "model": settings["model"],
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {question}\n\nWarehouse context:\n{context}"},
        ],
    }
    try:
        response = httpx.post(
            f"{settings['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {settings['api_key']}"},
            json=payload,
            timeout=40.0,
        )
        response.raise_for_status()
        body = response.json()
        return str(body["choices"][0]["message"]["content"]).strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        logger.exception("openai-compatible request failed; using the warehouse analyst")
        return None


def _local_answer(question: str, warehouse: Warehouse) -> str:
    text = question.lower()
    kpis = executive_kpis(warehouse)
    if "region" in text and "risk" in text:
        regions = region_risk(warehouse)
        rows = list(regions.head(3).itertuples(index=False))

        def _band(row, first: bool) -> str:
            detail = (
                f"{row.avg_risk:.1f} ({int(row.critical)} critical, {int(row.high)} high)"
            )
            if first:
                return f"{row.region} has the highest average risk score at {detail}"
            return f"{row.region} at {detail}"

        if len(rows) == 1:
            return f"{_band(rows[0], True)}."
        if len(rows) == 2:
            return f"{_band(rows[0], True)}, followed by {_band(rows[1], False)}."
        return (
            f"{_band(rows[0], True)}, followed by {_band(rows[1], False)} "
            f"and {_band(rows[2], False)}."
        )
    if any(word in text for word in ("cause", "caused", "root")) or (
        "failure" in text and "month" in text
    ):
        causes = root_causes(warehouse, trailing_days=30)
        if causes["outages"].empty and causes["incidents"].empty:
            return "No outages or incidents were recorded in the last 30 days."
        parts = []
        if not causes["outages"].empty:
            lead = causes["outages"].iloc[0]
            parts.append(
                f"The leading outage cause in the last 30 days is {str(lead['cause']).replace('_', ' ')} "
                f"({int(lead['outages'])} events, {int(lead['customers'])} customers)."
            )
        if not causes["incidents"].empty:
            lead_i = causes["incidents"].iloc[0]
            parts.append(
                f"The leading incident category is {str(lead_i['category']).replace('_', ' ')} ({int(lead_i['incidents'])} reports)."
            )
        return " ".join(parts)
    if "maintenance" in text or "preventive" in text:
        backlog = maintenance_backlog(warehouse, limit=5)
        if backlog.empty:
            return "No asset currently combines elevated risk with a thin maintenance history."
        names = ", ".join(
            f"{row.asset_name} ({row.city}, {row.risk_label})" for row in backlog.itertuples(index=False)
        )
        return f"Preventive maintenance should go to: {names}."
    if "demand" in text or "quarter" in text or "forecast" in text:
        quarter = quarterly_demand(warehouse)
        direction = "above" if quarter["delta_mwh"] >= 0 else "below"
        return (
            f"Trailing 90-day demand was {quarter['trailing_90d_mwh']:,.0f} MWh. "
            f"The next-quarter forecast is {quarter['next_quarter_mwh']:,.0f} MWh, "
            f"{abs(quarter['delta_mwh']):,.0f} MWh {direction} the trailing quarter."
        )
    if "summar" in text or "executive" in text:
        return (
            f"AetherGrid is watching {int(kpis['total_assets'])} assets. "
            f"{int(kpis['active_incidents'])} incidents are still open and "
            f"{int(kpis['critical_risks'])} "
            f"{'asset sits' if int(kpis['critical_risks']) == 1 else 'assets sit'} in the critical band. "
            f"{int(kpis['predicted_failures'])} assets have a failure probability of at least 0.50. "
            f"Demand over the last 30 days was {kpis['demand_last_30d_mwh']:,.0f} MWh."
        )
    return (
        "I answered from the latest warehouse brief. "
        f"{int(kpis['critical_risks'])} "
        f"{'asset is' if int(kpis['critical_risks']) == 1 else 'assets are'} critical and "
        f"{int(kpis['predicted_failures'])} are flagged by the failure model. "
        "Ask about regions at risk, causes this month, preventive maintenance, or next-quarter demand."
    )


def _recommendations(question: str, warehouse: Warehouse) -> list[str]:
    text = question.lower()
    backlog = maintenance_backlog(warehouse, limit=3)
    names = [str(name) for name in backlog["asset_name"].head(3)] if not backlog.empty else []
    recs = []
    if names:
        recs.append("Schedule preventive work on " + ", ".join(names) + " before the next storm window.")
    recs.append("Review open incidents in critical regions at the next operations briefing.")
    if "demand" in text or "forecast" in text:
        recs.append("Check generation and import coverage against the 90-day demand forecast.")
    else:
        recs.append("Hold load transfers ready for assets whose outage probability is above 0.50.")
    return recs[:3]


def summarize_outages(warehouse: Warehouse) -> str:
    """Short outage brief for the incident explorer."""
    causes = root_causes(warehouse, trailing_days=30)
    frame: pd.DataFrame = causes["outages"]
    if frame.empty:
        return "No outages in the last 30 days."
    total = int(frame["outages"].sum())
    customers = int(frame["customers"].sum())
    lead = frame.iloc[0]
    return (
        f"{total} outages in the last 30 days affected {customers} customers. "
        f"The most common cause was {lead['cause']} ({int(lead['outages'])} events)."
    )
