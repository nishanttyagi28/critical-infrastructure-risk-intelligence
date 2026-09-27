"""Generate the grid, load the warehouse, and train the models."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from ciri.analytics.queries import executive_kpis, quarterly_demand, region_risk
from ciri.config import PROCESSED_DIR
from ciri.data.generate import GenerateConfig, generate
from ciri.etl.pipeline import run_etl
from ciri.logging_utils import get_logger
from ciri.ml.train import train_all

logger = get_logger(__name__)


def bootstrap(config: GenerateConfig | None = None, raw_dir: Path | None = None) -> dict[str, object]:
    """Run the full refresh. Returns the model registry document."""
    frames = generate(config, raw_dir=raw_dir)
    warehouse = run_etl(raw_dir=raw_dir)
    document = train_all(warehouse)
    snapshot = {
        "kpis": executive_kpis(warehouse),
        "regions": region_risk(warehouse).to_dict(orient="records"),
        "quarter": quarterly_demand(warehouse),
        "model_version": document["version"],
        "rows": {name: int(len(frame)) for name, frame in frames.items()},
    }
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "impact_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    logger.info("bootstrap complete version=%s", document["version"])
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the AetherGrid warehouse and models.")
    parser.add_argument("--tiny", action="store_true", help="Short history for tests and CI.")
    args = parser.parse_args()
    config = None
    if args.tiny:
        config = GenerateConfig(
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
            locations_per_region=1,
            assets_per_location=4,
            sensor_assets=12,
            sensor_days=40,
        )
    bootstrap(config)


if __name__ == "__main__":
    main()
