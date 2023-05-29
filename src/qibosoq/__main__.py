"""Main qibosoq program, starts the server"""

import os
import sys

import qibosoq.configuration as cfg
from qibosoq.log import define_loggers
from qibosoq.rfsoc_server import serve

logger, program_logger = define_loggers()

try:
    logger.info("Server starting at port %d and IP %s", cfg.PORT, cfg.HOST)
    serve(cfg.HOST, cfg.PORT)
except KeyboardInterrupt:
    logger.info("Server closed by Keyboard combination")
    sys.exit(0)
