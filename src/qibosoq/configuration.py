"""Qibosoq configuration file"""

# Server address
HOST = "192.168.0.81"
# Port to listen on
PORT = 6000

# Main logger configuration
MAIN_LOGGER_FILE = "/home/xilinx/logs/qibosoq.log"
MAIN_LOGGER_NAME = "qibosoq_logger"
# Program logger configuration
PROGRAM_LOGGER_FILE = "/home/xilinx/logs/program.log"
PROGRAM_LOGGER_NAME = "qick_program"

# Position of the used bitsream
QICKSOC_LOCATION = "/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit"
IS_MULTIPLEXED = True  # TODO this should be written in bitstream
