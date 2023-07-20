"""Program used by qibosoq to execute sequences."""

import logging

from qick import AveragerProgram

import qibosoq.configuration as qibosoq_cfg
from qibosoq.programs.flux import FluxProgram

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class ExecutePulseSequence(FluxProgram, AveragerProgram):
    """Class to execute arbitrary PulseSequences."""

    def initialize(self):
        """Declre nyquist zones for all the DACs and all the readout frequencies.

        Function called by AveragerProgram.__init__.
        """
        self.declare_zones_and_ro(self.sequence)
        self.sync_all(self.wait_initialize)
