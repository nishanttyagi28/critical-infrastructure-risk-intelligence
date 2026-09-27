"""Operating territory for the demonstration grid.

AetherGrid is a fictional multi-region utility. Coordinates are real places
so geospatial views sit on a recognizable map. The figures are synthetic.
"""

from __future__ import annotations

REGIONS: list[dict[str, object]] = [
    {
        "region": "North Intertie",
        "grid_zone": "MRO-N",
        "criticality": "high",
        "cities": [("Duluth", 46.7867, -92.1005), ("Hibbing", 47.4272, -92.9377), ("Superior", 46.7208, -92.1041)],
        "base_mwh": 4200,
        "temp_delta": -4.0,
    },
    {
        "region": "Metro Ring",
        "grid_zone": "MRO-C",
        "criticality": "critical",
        "cities": [("Minneapolis", 44.9778, -93.2650), ("Saint Paul", 44.9537, -93.0900), ("Bloomington", 44.8408, -93.2983)],
        "base_mwh": 9100,
        "temp_delta": 0.0,
    },
    {
        "region": "Industrial Belt",
        "grid_zone": "RFC-W",
        "criticality": "high",
        "cities": [("Gary", 41.5934, -87.3464), ("Hammond", 41.5834, -87.5000), ("Joliet", 41.5250, -88.0817)],
        "base_mwh": 7600,
        "temp_delta": 1.5,
    },
    {
        "region": "River Hydro",
        "grid_zone": "MRO-S",
        "criticality": "medium",
        "cities": [("La Crosse", 43.8014, -91.2396), ("Winona", 44.0499, -91.6393), ("Red Wing", 44.5625, -92.5338)],
        "base_mwh": 2800,
        "temp_delta": -1.0,
    },
    {
        "region": "Coastal Corridor",
        "grid_zone": "NPCC-S",
        "criticality": "high",
        "cities": [("Providence", 41.8240, -71.4128), ("New Bedford", 41.6362, -70.9342), ("Fall River", 41.7015, -71.1550)],
        "base_mwh": 5400,
        "temp_delta": 2.0,
    },
    {
        "region": "Mountain Intertie",
        "grid_zone": "WECC-N",
        "criticality": "medium",
        "cities": [("Bozeman", 45.6770, -111.0429), ("Helena", 46.5891, -112.0391), ("Butte", 46.0038, -112.5348)],
        "base_mwh": 1900,
        "temp_delta": -6.0,
    },
    {
        "region": "Desert Solar",
        "grid_zone": "WECC-S",
        "criticality": "medium",
        "cities": [("Tucson", 32.2226, -110.9747), ("Yuma", 32.6927, -114.6277), ("Las Cruces", 32.3199, -106.7637)],
        "base_mwh": 3600,
        "temp_delta": 10.0,
    },
    {
        "region": "Capital District",
        "grid_zone": "RFC-E",
        "criticality": "critical",
        "cities": [("Albany", 42.6526, -73.7562), ("Schenectady", 42.8142, -73.9396), ("Troy", 42.7284, -73.6918)],
        "base_mwh": 4800,
        "temp_delta": -0.5,
    },
]

ASSET_TYPES: list[dict[str, object]] = [
    {"asset_type": "Substation", "code": "SUB", "capacity_mw": 180, "voltage_kv": 230, "customers": 14000},
    {"asset_type": "Transmission Line", "code": "LN", "capacity_mw": 320, "voltage_kv": 345, "customers": 22000},
    {"asset_type": "Distribution Transformer", "code": "XF", "capacity_mw": 25, "voltage_kv": 13, "customers": 1800},
    {"asset_type": "Generation Unit", "code": "GEN", "capacity_mw": 240, "voltage_kv": 138, "customers": 0},
    {"asset_type": "Switchgear", "code": "SWG", "capacity_mw": 40, "voltage_kv": 34, "customers": 900},
    {"asset_type": "Battery Storage", "code": "BESS", "capacity_mw": 50, "voltage_kv": 34, "customers": 0},
]

MANUFACTURERS = [
    "Helios Electric",
    "Northwind Turbines",
    "Vale Switchgear",
    "Lumen Transformers",
    "Harbor Power Systems",
]

OUTAGE_CAUSES = [
    "weather",
    "equipment_failure",
    "vegetation",
    "wildlife",
    "overload",
    "planned_work",
]

INCIDENT_CATEGORIES = [
    "equipment_failure",
    "safety",
    "environmental",
    "protection_alarm",
    "public_damage",
]
