"""Main qibosoq program, starts the server"""

import logging
import logging.handlers
import os
import sys

from qibosoq.rfsoc_server import serve


def define_logger():
    """Define logger format and handler"""

    logger = logging.getLogger("__name__")
    logger.setLevel(logging.DEBUG)

    filename = "/home/xilinx/logs/qibosoq.log"
    formatter = logging.Formatter("%(levelname)s :: %(asctime)s ::  %(message)s", "%Y-%m-%d %H:%M:%S")

    # Creates a qibosoq.log.<n> file if qibosoq.log already exists
    # The n value goes up to five
    handler = logging.handlers.RotatingFileHandler(filename, mode="w", backupCount=5, delay=True)
    if os.path.isfile(filename):
        handler.doRollover()

    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger


logger = define_logger()

HOST = "192.168.0.72"  # Server address
PORT = 6000  # Port to listen on

try:
    logger.info(f"Server starting at port {PORT} and IP {HOST}")
    serve(HOST, PORT)
except KeyboardInterrupt:
    logger.info("Server closed by Keyboard combination")
    sys.exit(0)
