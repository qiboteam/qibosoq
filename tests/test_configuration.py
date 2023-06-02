import os
from importlib import reload
from unittest import mock

import qibosoq.configuration as cfg

variables = {
    "QIBOSOQ_HOST": "192.168.0.72",
    "QIBOSOQ_PORT": "7000",
    "QIBOSOQ_MAIN_LOGGER_FILE": "/logs/main.log",
    "QIBOSOQ_MAIN_LOGGER_NAME": "mylogger",
    "QIBOSOQ_PROGRAM_LOGGER_FILE": "/logs/program.log",
    "QIBOSOQ_PROGRAM_LOGGER_NAME": "myprogramlogger",
    "QIBOSOQ_BITSTREAM": "/qicksoc.bit",
    "QIBOSOQ_IS_MULTIPLEXED": "False",
}


@mock.patch.dict(os.environ, variables)
def test_configuration_changes():
    reload(cfg)
    assert cfg.HOST == "192.168.0.72"
    assert cfg.PORT == 7000
    assert cfg.MAIN_LOGGER_FILE == "/logs/main.log"
    assert cfg.MAIN_LOGGER_NAME == "mylogger"
    assert cfg.PROGRAM_LOGGER_FILE == "/logs/program.log"
    assert cfg.PROGRAM_LOGGER_NAME == "myprogramlogger"
    assert cfg.QICKSOC_LOCATION == "/qicksoc.bit"
    assert cfg.IS_MULTIPLEXED is False


@mock.patch.dict(os.environ, {})
def test_configuration_default():
    reload(cfg)
    assert cfg.HOST == "192.168.0.81"
    assert cfg.PORT == 6000
    assert cfg.MAIN_LOGGER_FILE == "/home/xilinx/logs/qibosoq.log"
    assert cfg.MAIN_LOGGER_NAME == "qibosoq_logger"
    assert cfg.PROGRAM_LOGGER_FILE == "/home/xilinx/logs/program.log"
    assert cfg.PROGRAM_LOGGER_NAME == "qick_program"
    assert cfg.QICKSOC_LOCATION == "/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit"
    assert cfg.IS_MULTIPLEXED is True
