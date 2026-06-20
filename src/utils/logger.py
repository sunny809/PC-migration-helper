"""Logging configuration for PC Migration Helper."""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure application-wide logging.

    Args:
        debug: If True, set log level to DEBUG; otherwise INFO.

    Returns:
        The configured root logger for the application.
    """
    logger = logging.getLogger("migrate")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Prevent duplicate handlers on re-initialization
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_fmt = logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s"
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # File handler (rotating, 5MB max, 3 backups)
    log_dir = os.path.join(os.path.expanduser("~"), ".migrate", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "migrate.log")

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger
