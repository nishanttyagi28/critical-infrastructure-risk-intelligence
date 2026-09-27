"""Application logging. One file under logs/, plus the console."""

from __future__ import annotations

import logging
from pathlib import Path

from ciri.config import LOG_DIR

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured once for the process."""
    global _CONFIGURED
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not _CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(LOG_DIR / "ciri.log", encoding="utf-8"),
            ],
        )
        _CONFIGURED = True
    return logging.getLogger(name)


def log_stage(logger: logging.Logger, stage: str, **counts: object) -> None:
    """Log a completed pipeline stage with row counts."""
    detail = " ".join(f"{key}={value}" for key, value in counts.items())
    logger.info("stage=%s %s", stage, detail)
