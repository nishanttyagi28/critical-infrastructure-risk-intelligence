"""Composite score bands and component bounds."""

from ciri.risk.scoring import component_scores, risk_label, simulate_scenario
import pandas as pd


def test_bands():
    assert risk_label(0) == "Low"
    assert risk_label(24.9) == "Low"
    assert risk_label(25) == "Medium"
    assert risk_label(49.9) == "Medium"
    assert risk_label(50) == "High"
    assert risk_label(74.9) == "High"
    assert risk_label(75) == "Critical"
    assert risk_label(100) == "Critical"


def test_components_stay_inside_weights():
    parts = component_scores(80, 12, 140, 0, 2.0)
    assert parts["risk_score"] <= 100
    assert parts["age_component"] == 25
    assert parts["failure_component"] == 25
    assert parts["weather_component"] == 20
    assert parts["maintenance_component"] == 15
    assert parts["load_component"] == 15


def test_maintenance_lowers_the_score():
    neglected = component_scores(20, 1, 30, 0, 0.8)["risk_score"]
    maintained = component_scores(20, 1, 30, 4, 0.8)["risk_score"]
    assert maintained < neglected


def test_scenario_can_move_a_band():
    frame = pd.DataFrame(
        [
            {
                "age_years": 35,
                "failures_365d": 2,
                "weather_severity_30d": 40,
                "maintenance_365d": 1,
                "load_index": 0.9,
                "risk_label": "Medium",
                "risk_score": 40,
            }
        ]
    )
    shocked = simulate_scenario(frame, weather_delta=40, load_factor=1.4)
    assert shocked.iloc[0]["risk_score"] > frame.iloc[0]["risk_score"]
