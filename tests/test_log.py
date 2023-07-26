from logging import Logger

import qibosoq
from qibosoq.log import define_loggers


def test_define_loggers():
    qibosoq.configuration.MAIN_LOGGER_FILE = "/tmp/test_log.log"
    qibosoq.configuration.PROGRAM_LOGGER_FILE = "/tmp/test_log2.log"

    log1, log2 = define_loggers()
    assert isinstance(log1, Logger)
    assert isinstance(log2, Logger)
