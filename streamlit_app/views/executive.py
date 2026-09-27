"""Executive overview: the numbers a control-center lead reads first."""

import pandas as pd
import plotly.express as px
import streamlit as st

from ciri.analytics.queries import demand_trend, executive_kpis, region_risk
from common import RISK_COLORS, render_sidebar, require_warehouse

store = require_warehouse()
render_sidebar(store)
kpis = executive_kpis(store)

st.title("Executive overview")
st.caption("AetherGrid demonstration grid. Figures are synthetic and seeded, not a live utility feed.")

demand_delta = kpis["demand_last_30d_mwh"] - kpis["demand_prior_30d_mwh"]
columns = st.columns(4)
columns[0].metric("Total assets", f"{int(kpis['total_assets'])}")
columns[1].metric("Active incidents", f"{int(kpis['active_incidents'])}")
columns[2].metric("Critical risks", f"{int(kpis['critical_risks'])}")
columns[3].metric("Predicted failures", f"{int(kpis['predicted_failures'])}")

columns = st.columns(2)
columns[0].metric(
    "Energy demand, last 30 days",
    f"{kpis['demand_last_30d_mwh'] / 1000:.1f} GWh",
    delta=f"{demand_delta / 1000:.1f} GWh vs prior 30 days",
)
columns[1].metric("Outage probability ≥ 0.50", f"{int(kpis['predicted_outages'])} assets")

left, right = st.columns((3, 2))
trend = demand_trend(store)
with left:
    st.subheader("Energy demand")
    fig = px.area(
        trend,
        x="period",
        y="demand_mwh",
        color="region",
        labels={"period": "Month", "demand_mwh": "MWh"},
    )
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    st.plotly_chart(fig, width="stretch")
with right:
    st.subheader("Risk by region")
    regions = region_risk(store)
    fig = px.bar(
        regions,
        x="avg_risk",
        y="region",
        orientation="h",
        labels={"avg_risk": "Average risk score", "region": ""},
        color="avg_risk",
        color_continuous_scale=["#3d9a78", "#d4a017", "#d64545"],
    )
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")

st.subheader("Region table")
display = regions.copy()
display["avg_risk"] = display["avg_risk"].round(1)
st.dataframe(display, width="stretch", hide_index=True)

risk = store.read("Mart_AssetRisk")
band = risk["risk_label"].value_counts().reindex(["Low", "Medium", "High", "Critical"]).fillna(0)
band_frame = pd.DataFrame({"risk_label": band.index, "assets": band.values})
st.subheader("Fleet risk bands")
fig = px.bar(
    band_frame,
    x="risk_label",
    y="assets",
    color="risk_label",
    color_discrete_map=RISK_COLORS,
)
fig.update_layout(showlegend=False, height=280, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")
