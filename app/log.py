"""Shared logger. Errors go to logs/error.log, outside the served frontend/ root."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import BASE_DIR

logger = logging.getLogger("app")


def configure_logging():
    """Attach one rotating file handler. Safe to call more than once."""
    if any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        return
    log_dir = Path(BASE_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "error.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
