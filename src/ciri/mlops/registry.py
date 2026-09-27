"""File-based model registry and experiment log.

Each training run appends one JSON line to models/experiments.jsonl and
updates models/registry.json. If MLflow is installed and CIRI_MLFLOW=1,
the same metrics are logged there as well.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ciri.config import MODEL_DIR
from ciri.logging_utils import get_logger

logger = get_logger(__name__)


def frame_digest(frame: pd.DataFrame) -> str:
    """Stable hash of a modeling table."""
    hashed = pd.util.hash_pandas_object(frame, index=False).values.tobytes()
    return hashlib.sha256(hashed).hexdigest()


def next_version(current: str | None) -> str:
    """Bump the patch number. The first recorded run is 1.0.0."""
    if not current:
        return "1.0.0"
    major, minor, patch = (int(part) for part in current.split("."))
    return f"{major}.{minor}.{patch + 1}"


def record_experiment(
    *,
    metrics: dict[str, dict[str, float | None]],
    params: dict[str, object],
    data_hash: str,
    model_dir: Path | None = None,
) -> dict[str, object]:
    """Persist the run and return the registry document."""
    target = model_dir or MODEL_DIR
    target.mkdir(parents=True, exist_ok=True)
    registry_path = target / "registry.json"
    previous = None
    if registry_path.exists():
        previous = json.loads(registry_path.read_text(encoding="utf-8")).get("version")
    document: dict[str, object] = {
        "version": next_version(previous if isinstance(previous, str) else None),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_hash": data_hash,
        "params": params,
        "metrics": metrics,
    }
    registry_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    with (target / "experiments.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(document) + "\n")
    _maybe_mlflow(document)
    logger.info("registered model version=%s", document["version"])
    return document


def load_registry(model_dir: Path | None = None) -> dict[str, object]:
    path = (model_dir or MODEL_DIR) / "registry.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _maybe_mlflow(document: dict[str, object]) -> None:
    if os.environ.get("CIRI_MLFLOW", "").strip() not in {"1", "true", "True"}:
        return
    try:
        import mlflow
    except ImportError:
        logger.info("CIRI_MLFLOW is set but mlflow is not installed")
        return
    mlflow.set_experiment("aethergrid-risk")
    with mlflow.start_run(run_name=str(document["version"])):
        metrics = document["metrics"]
        if isinstance(metrics, dict):
            for model_name, values in metrics.items():
                if not isinstance(values, dict):
                    continue
                for metric, value in values.items():
                    if isinstance(value, (int, float)):
                        mlflow.log_metric(f"{model_name}_{metric}", float(value))
