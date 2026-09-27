"""AetherGrid operator console."""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", Path(__file__).resolve().parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

st.set_page_config(
    page_title="AetherGrid Risk Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

views = Path(__file__).parent / "views"
navigation = st.navigation(
    [
        st.Page(views / "executive.py", title="Executive Overview", default=True),
        st.Page(views / "assets.py", title="Asset Monitoring"),
        st.Page(views / "risk.py", title="Risk Intelligence"),
        st.Page(views / "forecast.py", title="Forecasting"),
        st.Page(views / "assistant.py", title="AI Assistant"),
        st.Page(views / "incidents.py", title="Incident Explorer"),
    ]
)
navigation.run()
