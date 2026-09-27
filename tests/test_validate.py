"""Quality gates quarantine bad rows and reject broken foreign keys."""

import pandas as pd
import pytest

from ciri.data.validate import assert_foreign_keys, validate_frame
from ciri.errors import DataValidationError


def test_quarantine_drops_negative_demand(tmp_path):
    frame = pd.DataFrame(
        {
            "demand_mwh": [10.0] * 29 + [-1.0],
            "peak_mw": [1.0] * 30,
        }
    )
    clean = validate_frame("Fact_EnergyDemand", frame, quarantine_dir=tmp_path)
    assert len(clean) == 29
    assert clean["demand_mwh"].min() == 10
    assert (tmp_path / "Fact_EnergyDemand.csv").exists()


def test_too_many_rejects_fail_the_load(tmp_path):
    frame = pd.DataFrame({"demand_mwh": [-1, -2, 3], "peak_mw": [1, 1, 1]})
    with pytest.raises(DataValidationError):
        validate_frame("Fact_EnergyDemand", frame, quarantine_dir=tmp_path)


def test_foreign_key_mismatch():
    frames = {
        "Dim_Asset": pd.DataFrame({"asset_id": [1], "location_id": [9]}),
        "Dim_Location": pd.DataFrame({"location_id": [1]}),
        "Dim_Date": pd.DataFrame({"date_key": [20240101]}),
        "Fact_Outages": pd.DataFrame({"asset_id": [1], "location_id": [1], "date_key": [20240101]}),
        "Fact_Incidents": pd.DataFrame({"asset_id": [1]}),
        "Fact_EnergyDemand": pd.DataFrame({"location_id": [1]}),
        "Fact_Maintenance": pd.DataFrame({"asset_id": [1]}),
        "Dim_Weather": pd.DataFrame({"location_id": [1]}),
    }
    with pytest.raises(DataValidationError, match="Dim_Asset.location_id"):
        assert_foreign_keys(frames)
