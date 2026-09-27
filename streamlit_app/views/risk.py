"""Geospatial risk, correlation, and a weather or load shock."""

import plotly.express as px
import streamlit as st

from ciri.analytics.advanced import scenario_summary
from ciri.analytics.queries import correlation_frame
from common import RISK_COLORS, render_sidebar, require_warehouse

store = require_warehouse()
render_sidebar(store)
risk = store.read("Mart_AssetRisk")

st.title("Risk intelligence")
st.caption("Composite score from age, failures, weather, maintenance, and load. The map is the current band, not a forecast.")

fig = px.scatter_map(
    risk,
    lat="latitude",
    lon="longitude",
    color="risk_label",
    color_discrete_map=RISK_COLORS,
    hover_name="asset_name",
    hover_data={"city": True, "risk_score": ":.1f", "asset_type": True, "latitude": False, "longitude": False},
    zoom=3,
    height=480,
)
fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)
with left:
    st.subheader("What moves together")
    corr = correlation_frame(store)
    fig = px.imshow(
        corr.round(2),
        text_auto=True,
        color_continuous_scale="RdBu",
        zmin=-1,
        zmax=1,
        aspect="auto",
    )
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
with right:
    st.subheader("Scenario")
    weather_delta = st.slider("Weather severity, points", -10, 30, 12)
    load_factor = st.slider("Load multiplier", 0.8, 1.5, 1.1, 0.05)
    result = scenario_summary(store, weather_delta=float(weather_delta), load_factor=float(load_factor))
    st.write(
        f"Under this shock, {result['assets_now_critical']} additional assets enter the critical band."
    )
    before = result["before"]
    after = result["after"]
    rows = [{"band": band, "today": before[band], "after shock": after[band]} for band in before]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption("Age and maintenance history stay fixed. Only weather severity and load are shocked.")
