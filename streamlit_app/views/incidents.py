"""Incident and outage explorer, including a short outage brief."""

import pandas as pd
import plotly.express as px
import streamlit as st

from ciri.analytics.queries import outage_trend, root_causes
from ciri.llm.analyst import summarize_outages
from common import render_sidebar, require_warehouse

store = require_warehouse()
render_sidebar(store)

st.title("Incident explorer")
st.write(summarize_outages(store))

causes = root_causes(store, trailing_days=90)
left, right = st.columns(2)
with left:
    st.subheader("Outage causes, 90 days")
    if causes["outages"].empty:
        st.info("No outages in this window.")
    else:
        fig = px.bar(causes["outages"], x="cause", y="outages")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
with right:
    st.subheader("Incident categories, 90 days")
    if causes["incidents"].empty:
        st.info("No incidents in this window.")
    else:
        fig = px.bar(causes["incidents"], x="category", y="incidents")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

trend = outage_trend(store)
monthly = trend.groupby("period", as_index=False)["outages"].sum()
fig = px.line(monthly, x="period", y="outages", labels={"period": "Month", "outages": "Outages"})
fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")

incidents = store.read("Fact_Incidents")
dates = store.read("Dim_Date")[["date_key", "full_date"]]
assets = store.read("Dim_Asset")[["asset_id", "asset_name", "asset_type"]]
locations = store.read("Dim_Location")[["location_id", "region", "city"]]
frame = incidents.merge(dates, on="date_key").merge(assets, on="asset_id").merge(locations, on="location_id")
frame["full_date"] = pd.to_datetime(frame["full_date"])

filters = st.columns(3)
status = filters[0].selectbox("Status", ["All"] + sorted(frame["status"].unique()))
category = filters[1].selectbox("Category", ["All"] + sorted(frame["category"].unique()))
region = filters[2].selectbox("Region", ["All"] + sorted(frame["region"].unique()))
view = frame
if status != "All":
    view = view.loc[view["status"] == status]
if category != "All":
    view = view.loc[view["category"] == category]
if region != "All":
    view = view.loc[view["region"] == region]
st.dataframe(
    view.sort_values("full_date", ascending=False)[
        ["full_date", "asset_name", "city", "region", "category", "severity", "status", "description"]
    ].head(100),
    width="stretch",
    hide_index=True,
)
