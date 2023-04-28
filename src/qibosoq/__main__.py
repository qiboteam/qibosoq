"""Main qibosoq program, starts the server"""

import logging
import logging.handlers
import os
import sys

from qibosoq.rfsoc_server import serve


def define_logger():
    """Define logger format and handler"""

    new_logger = logging.getLogger("__name__")
    new_logger.setLevel(logging.DEBUG)

    filename = "/home/xilinx/logs/qibosoq.log"
    formatter = logging.Formatter("%(levelname)s :: %(asctime)s ::  %(message)s", "%Y-%m-%d %H:%M:%S")

    # Creates a qibosoq.log.<n> file if qibosoq.log already exists
    # The n value goes up to five
    handler = logging.handlers.RotatingFileHandler(filename, mode="w", backupCount=5, delay=True)
    if os.path.isfile(filename):
        handler.doRollover()
    handler.setFormatter(formatter)
    new_logger.addHandler(handler)
    return new_logger


logger = define_logger()

HOST = "192.168.0.81"  # Server address
PORT = 6000  # Port to listen on

try:
    logger.info("Server starting at port %d and IP %s", PORT, HOST)
    serve(HOST, PORT)
except KeyboardInterrupt:
    logger.info("Server closed by Keyboard combination")
    sys.exit(0)
