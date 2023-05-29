"""Qibosoq configuration file"""

HOST = "192.168.0.81"
"""Server address"""
PORT = 6000
"""Port of the server"""

# Main logger configuration
MAIN_LOGGER_FILE = "/home/xilinx/logs/qibosoq.log"
"""Main logger file"""
MAIN_LOGGER_NAME = "qibosoq_logger"
"""Main logger name"""
# Program logger configuration
PROGRAM_LOGGER_FILE = "/home/xilinx/logs/program.log"
"""Program logger file"""
PROGRAM_LOGGER_NAME = "qick_program"
"""Program logger name"""

QICKSOC_LOCATION = "/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit"
"""Path of the qick bitstream to load"""
IS_MULTIPLEXED = True  # TODO this should be written in bitstream
"""Whether the readout is multiplexed or not"""
