"""Loggers configuration."""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Tuple

import qibosoq.configuration as cfg


def configure_logger(name: str, filename: str, backup_count: int):
    """Create and configure logger."""
    # if the log directory does not exsist, create it
    dir_path = Path(filename).parent
    if not dir_path.exists():
        dir_path.mkdir()

    if name is not None:
        new_logger = logging.getLogger(name)
    else:
        new_logger = logging
    new_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s :: %(asctime)s ::  %(message)s", "%Y-%m-%d %H:%M:%S")

    handler = logging.handlers.RotatingFileHandler(filename, mode="w", backupCount=backup_count, delay=True)
    if os.path.isfile(filename):
        handler.doRollover()
    handler.setFormatter(formatter)
    new_logger.addHandler(handler)
    return new_logger


def define_loggers() -> Tuple[logging.Logger, logging.Logger]:
    """Define main logger and program logger."""
    main = configure_logger(cfg.MAIN_LOGGER_NAME, cfg.MAIN_LOGGER_FILE, 5)
    program = configure_logger(cfg.PROGRAM_LOGGER_NAME, cfg.PROGRAM_LOGGER_FILE, 3)
    return main, program
