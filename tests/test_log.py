from logging import Logger

from qibosoq.log import define_loggers


def test_define_loggers():
    log1, log2 = define_loggers()
    assert isinstance(log1, Logger)
    assert isinstance(log2, Logger)
