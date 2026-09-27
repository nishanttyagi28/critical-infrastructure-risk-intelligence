"""Asset list, health, and a single-asset explanation."""

import plotly.express as px
import streamlit as st

from ciri.ml.predict import explain_asset
from common import RISK_COLORS, render_sidebar, require_warehouse

store = require_warehouse()
render_sidebar(store)
risk = store.read("Mart_AssetRisk")
health = store.read("Ml_HealthScore")
frame = risk.merge(health, on="asset_id", how="left")

st.title("Asset monitoring")
regions = ["All"] + sorted(frame["region"].unique())
types = ["All"] + sorted(frame["asset_type"].unique())
bands = ["All", "Low", "Medium", "High", "Critical"]
filters = st.columns(3)
region = filters[0].selectbox("Region", regions)
asset_type = filters[1].selectbox("Asset type", types)
band = filters[2].selectbox("Risk band", bands)
view = frame
if region != "All":
    view = view.loc[view["region"] == region]
if asset_type != "All":
    view = view.loc[view["asset_type"] == asset_type]
if band != "All":
    view = view.loc[view["risk_label"] == band]

left, right = st.columns((2, 1))
with left:
    st.dataframe(
        view[
            [
                "asset_name",
                "asset_type",
                "city",
                "region",
                "age_years",
                "health_score",
                "risk_score",
                "risk_label",
                "failures_365d",
                "maintenance_365d",
            ]
        ].sort_values("risk_score", ascending=False),
        width="stretch",
        hide_index=True,
    )
with right:
    fig = px.histogram(view, x="health_score", nbins=20, labels={"health_score": "Health score"})
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")

st.subheader("Asset detail")
if view.empty:
    st.info("No assets match these filters.")
else:
    choice = st.selectbox("Asset", view.sort_values("asset_name")["asset_name"])
    selected = view.loc[view["asset_name"] == choice].iloc[0]
    detail = st.columns(4)
    detail[0].metric("Risk", f"{selected.risk_score:.1f}", selected.risk_label)
    detail[1].metric("Health", f"{selected.health_score:.0f}")
    detail[2].metric("Age", f"{int(selected.age_years)} years")
    detail[3].metric("Failures, 365d", f"{int(selected.failures_365d)}")
    explanation = explain_asset(int(selected.asset_id), store)
    st.write(
        f"Outage probability {explanation['outage_probability']:.2f}. "
        f"Failure probability {explanation['failure_probability']:.2f}."
    )
    if explanation["drivers"]:
        st.write("Above the fleet median on: " + ", ".join(explanation["drivers"]) + ".")
    compare = st.container()
    compare.dataframe(explanation["comparisons"], width="stretch", hide_index=True)

type_risk = view.groupby(["region", "asset_type"], as_index=False)["risk_score"].mean()
if not type_risk.empty:
    fig = px.density_heatmap(
        type_risk,
        x="asset_type",
        y="region",
        z="risk_score",
        color_continuous_scale=["#3d9a78", "#d4a017", "#d64545"],
        labels={"risk_score": "Avg risk"},
    )
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
