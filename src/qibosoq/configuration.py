"""Qibosoq configuration file"""
import os


def from_env(name, default=None):
    return os.getenv(f"QIBOSOQ_{name}", default)


HOST = from_env("HOST", "192.168.0.81")
"""Server address"""

PORT = int(from_env("PORT", 6000))
"""Port of the server"""

MAIN_LOGGER_FILE = from_env("MAIN_LOGGER_FILE", "/home/xilinx/logs/qibosoq.log")
"""Main logger file"""

MAIN_LOGGER_NAME = from_env("MAIN_LOGGER_NAME", "qibosoq_logger")
"""Main logger name"""

PROGRAM_LOGGER_FILE = from_env("PROGRAM_LOGGER_FILE", "/home/xilinx/logs/program.log")
"""Program logger file"""

PROGRAM_LOGGER_NAME = from_env("PROGRAM_LOGGER_NAME", "qick_program")
"""Program logger name"""

QICKSOC_LOCATION = from_env("BITSTREAM", "/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit")
"""Path of the qick bitstream to load"""

IS_MULTIPLEXED = from_env("IS_MULTIPLEXED", "True") == "True"  # TODO this should be written in bitstream
"""Whether the readout is multiplexed or not"""
