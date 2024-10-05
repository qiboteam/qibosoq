"""Program used by qibosoq to execute sequences."""

import logging
from typing import List

from qick import AveragerProgram, QickSoc

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import Element
from qibosoq.programs.flux import FluxProgram
from ..drivers.TI_DAC80508 import DAC80508
logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class ExecutePulseSequence(FluxProgram, AveragerProgram):
    """Class to execute arbitrary PulseSequences."""

    def __init__(
        self,
        soc: QickSoc,
        tidac: DAC80508,
        qpcfg: Config,
        sequence: List[Element],
        qubits: List[Qubit],
    ):
        """Init function, call super.__init__."""
        super().__init__(soc, tidac, qpcfg, sequence, qubits)

        self.reps = qpcfg.reps  # must be done after AveragerProgram init
        self.soft_avgs = qpcfg.soft_avgs

    def initialize(self):
        """Declre nyquist zones for all the DACs and all the readout frequencies.

        Function called by AveragerProgram.__init__.
        """
        self.declare_zones_and_ro(self.pulse_sequence)
        self.sync_all(self.wait_initialize)
