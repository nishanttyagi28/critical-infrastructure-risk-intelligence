"""Shared loader for the operator console."""

from __future__ import annotations

import streamlit as st

from ciri.mlops.registry import load_registry
from ciri.warehouse.store import Warehouse

RISK_COLORS = {
    "Low": "#3d9a78",
    "Medium": "#d4a017",
    "High": "#e07a3d",
    "Critical": "#d64545",
}


@st.cache_resource
def warehouse() -> Warehouse:
    return Warehouse()


def require_warehouse() -> Warehouse:
    """Stop the page when the warehouse has not been built."""
    store = warehouse()
    if not store.ready():
        st.error(
            "The warehouse is empty. From the project root run "
            "`PYTHONPATH=src python -m ciri bootstrap`, then reload this page."
        )
        st.stop()
    return store


def render_sidebar(store: Warehouse) -> None:
    registry = load_registry()
    st.sidebar.caption("AetherGrid control center")
    st.sidebar.write(f"Warehouse: {store.backend_name()}")
    version = registry.get("version", "not trained")
    st.sidebar.write(f"Model: {version}")
    trained = registry.get("trained_at", "")
    if trained:
        st.sidebar.caption(f"Trained {trained}")
