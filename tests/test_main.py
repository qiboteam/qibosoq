import logging

import qick

qick.QickSoc = None

from qibosoq import configuration as cfg

logger = logging.getLogger(cfg.MAIN_LOGGER_NAME)


def test_main(mocker, caplog):
    mocker.patch("qibosoq.rfsoc_server.serve")

    assert "Server starting at port" in caplog.text
