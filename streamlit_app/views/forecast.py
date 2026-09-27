"""Demand forecast, outage probability, and the risk shock as a forward view."""

import pandas as pd
import plotly.express as px
import streamlit as st

from ciri.analytics.queries import quarterly_demand
from common import render_sidebar, require_warehouse

store = require_warehouse()
render_sidebar(store)

st.title("Forecasting")
quarter = quarterly_demand(store)
delta = quarter["delta_mwh"]
columns = st.columns(3)
columns[0].metric("Trailing 90 days", f"{quarter['trailing_90d_mwh'] / 1000:.1f} GWh")
columns[1].metric("Next quarter forecast", f"{quarter['next_quarter_mwh'] / 1000:.1f} GWh")
columns[2].metric("Change", f"{delta / 1000:+.1f} GWh")

locations = store.read("Dim_Location")
forecast = store.read("Ml_DemandForecast").merge(locations[["location_id", "region", "city"]], on="location_id")
forecast["full_date"] = pd.to_datetime(forecast["full_date"])
region = st.selectbox("Region", ["All"] + sorted(forecast["region"].unique()))
view = forecast if region == "All" else forecast.loc[forecast["region"] == region]
daily = view.groupby("full_date", as_index=False)["forecast_mwh"].sum()
fig = px.line(daily, x="full_date", y="forecast_mwh", labels={"full_date": "Date", "forecast_mwh": "Forecast MWh"})
fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")
st.caption("Each location is walked forward 90 days. Future temperature is the historical average for that day of year.")

st.subheader("Near-term outage probability")
scores = store.read("Ml_OutageScore").merge(
    store.read("Mart_AssetRisk")[["asset_id", "asset_name", "region", "city", "risk_label"]],
    on="asset_id",
)
top = scores.sort_values("outage_probability", ascending=False).head(15)
fig = px.bar(
    top,
    x="outage_probability",
    y="asset_name",
    color="risk_label",
    orientation="h",
    labels={"outage_probability": "Probability", "asset_name": ""},
)
fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10), yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, width="stretch")

st.subheader("Failure probability")
failure = store.read("Ml_FailureScore")
st.metric("Assets at or above 0.50", f"{int((failure['failure_probability'] >= 0.50).sum())}")
st.dataframe(
    failure.merge(scores[["asset_id", "asset_name", "region"]], on="asset_id")
    .sort_values("failure_probability", ascending=False)
    .head(20),
    width="stretch",
    hide_index=True,
)
