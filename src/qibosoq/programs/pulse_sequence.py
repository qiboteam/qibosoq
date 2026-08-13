"""Program used by qibosoq to execute sequences."""

import logging
from typing import List

from qick import AveragerProgram, QickSoc
from qick.asm_v2 import AveragerProgramV2


import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, ConfigV2, Qubit
from qibosoq.components.pulses import Element
from qibosoq.programs.flux import FluxProgram, FluxProgramV2
from qibosoq.components.pulses import (
    Arbitrary,
    Drag,
    Element,
    FlatTop,
    Gaussian,
    Hann,
    Measurement,
    Pulse,
    Rectangular,
)

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class ExecutePulseSequence(FluxProgram, AveragerProgram):
    """Class to execute arbitrary PulseSequences."""

    def __init__(
        self,
        soc: QickSoc,
        qpcfg: Config,
        sequence: List[Element],
        qubits: List[Qubit],
    ):
        """Init function, call super.__init__."""
        super().__init__(soc, qpcfg, sequence, qubits)

        self.reps = qpcfg.reps  # must be done after AveragerProgram init
        self.soft_avgs = qpcfg.soft_avgs

    def initialize(self):
        """Declare nyquist zones for all the DACs and all the readout frequencies.

        Function called by AveragerProgram.__init__.
        """
        self.declare_zones_and_ro(self.pulse_sequence)
        self.sync_all(self.wait_initialize)


class ExecutePulseSequenceV2(FluxProgramV2, AveragerProgramV2):
    """Class to execute arbitrary PulseSequences on tProc v2."""

    def _initialize(self, cfg):
        """Executed once before the reps loop.

        Declares generators and readouts, then pre-registers all pulse
        waveforms so that _body can fire them without calling add_pulse.
        """
        self.declare_gen_and_ro(self.pulse_sequence)
        self.register_bias_pulses()

        for pulse in self.sequence:
            if pulse.type == "flux":
                self._register_flux_pulse(pulse)
            elif pulse.type == "drive":
                self.add_pulse_to_register(pulse)
            elif (
                pulse.type == "readout"
                and isinstance(pulse, Pulse)
                and pulse.adc is not None
                and not self.is_mux
            ):
                self.add_ro_pulse_to_register(pulse)

        if self.is_mux:
            self.register_mux_readout_groups()

    def _body(self, cfg):
        """Executed inside the hardware repetitions loop. Plays the pulse sequence."""
        self.set_bias("sweetspot")
        muxed_readouts_executed = []

        for pulse in self.sequence:
            t = pulse.start_delay

            if pulse.type == "readout":
                if self.is_mux and isinstance(pulse, Pulse):
                    if pulse in muxed_readouts_executed:
                        continue
                    mux_group = next(
                        group for group in self.multi_ro_pulses if pulse in group
                    )
                    self.execute_mux_readout_group(mux_group)
                    muxed_readouts_executed.extend(mux_group)
                else:
                    self.execute_readout(pulse)
            elif pulse.type == "drive":
                self.pulse(ch=pulse.dac, name=pulse.name, t=t)
            elif pulse.type == "flux":
                self.execute_flux_pulse(pulse)
            else:
                raise ValueError(f"Unsupported pulse type: {pulse.type!r}")

        self.set_bias("zero")