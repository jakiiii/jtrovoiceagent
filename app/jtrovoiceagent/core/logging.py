from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from jtrovoiceagent.core.config import LoggingConfig


def configure_logging(config: LoggingConfig) -> None:
    log_dir = Path(config.directory)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / config.filename

    root = logging.getLogger()
    root.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=config.rotate_bytes,
        backupCount=config.backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if config.console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)
