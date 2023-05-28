"""Main qibosoq program, starts the server"""

import logging
import logging.handlers
import os
import sys
from typing import Tuple

from qibosoq.rfsoc_server import serve

HOST = "192.168.0.81"  # Server address
PORT = 6000  # Port to listen on

MAIN_LOGGER_FILE = "/home/xilinx/logs/qibosoq.log"
PROGRAM_LOGGER_FILE = "/home/xilinx/logs/program.log"
PROGRAM_LOGGER_NAME = "qick_program"


def configure_logger(name: str, filename: str, backup_count: int):
    """Create and configure logger"""
    new_logger = logging.getLogger(name)
    new_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s :: %(asctime)s ::  %(message)s", "%Y-%m-%d %H:%M:%S")

    handler = logging.handlers.RotatingFileHandler(filename, mode="w", backupCount=backup_count, delay=True)
    if os.path.isfile(filename):
        handler.doRollover()
    handler.setFormatter(formatter)
    new_logger.addHandler(handler)
    return new_logger


def define_loggers() -> Tuple[logging.Logger, logging.Logger]:
    """Define main logger and program logger"""
    main = configure_logger(__name__, MAIN_LOGGER_FILE, 5)
    program = configure_logger(PROGRAM_LOGGER_NAME, PROGRAM_LOGGER_FILE, 3)
    return main, program


logger, program_logger = define_loggers()

try:
    logger.info("Server starting at port %d and IP %s", PORT, HOST)
    serve(HOST, PORT)
except KeyboardInterrupt:
    logger.info("Server closed by Keyboard combination")
    sys.exit(0)
