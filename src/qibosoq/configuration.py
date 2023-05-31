"""Qibosoq configuration file"""
import os

HOST = "192.168.0.81"
"""Server address"""
if "QIBOSOQ_HOST" in os.environ:
    HOST = os.environ["QIBOSOQ_HOST"]
PORT = 6000
"""Port of the server"""
if "QIBOSOQ_PORT" in os.environ:
    PORT = int(os.environ["QIBOSOQ_PORT"])

# Main logger configuration
MAIN_LOGGER_FILE = "/home/xilinx/logs/qibosoq.log"
"""Main logger file"""
if "QIBOSOQ_MAIN_LOGGER_FILE" in os.environ:
    MAIN_LOGGER_FILE = os.environ["QIBOSOQ_MAIN_LOGGER_FILE"]
MAIN_LOGGER_NAME = "qibosoq_logger"
"""Main logger name"""
if "QIBOSOQ_MAIN_LOGGER_NAME" in os.environ:
    MAIN_LOGGER_NAME = os.environ["QIBOSOQ_MAIN_LOGGER_NAME"]
# Program logger configuration
PROGRAM_LOGGER_FILE = "/home/xilinx/logs/program.log"
"""Program logger file"""
if "QIBOSOQ_PROGRAM_LOGGER_FILE" in os.environ:
    PROGRAM_LOGGER_FILE = os.environ["QIBOSOQ_PROGRAM_LOGGER_FILE"]
PROGRAM_LOGGER_NAME = "qick_program"
"""Program logger name"""
if "QIBOSOQ_PROGRAM_LOGGER_NAME" in os.environ:
    PROGRAM_LOGGER_NAME = os.environ["QIBOSOQ_PROGRAM_LOGGER_NAME"]

QICKSOC_LOCATION = "/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit"
"""Path of the qick bitstream to load"""
if "QICKSOC_LOCATION" in os.environ:
    QICKSOC_LOCATION = os.environ["QICKSOC_LOCATION"]
IS_MULTIPLEXED = True  # TODO this should be written in bitstream
"""Whether the readout is multiplexed or not"""
if "QIBOSOQ_IS_MULTIPLEXED" in os.environ:
    IS_MULTIPLEXED = bool(os.environ["QIBOSOQ_IS_MULTIPLEXED"])
