"""Program used by qibosoq to execute sequences."""

from typing import List

from qick import AveragerProgram, QickSoc
from qick.asm_v2 import AveragerProgramV2

from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import Element, Pulse
from qibosoq.programs.flux import FluxProgram, FluxProgramV2


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
        self.play_sequence()
        self.set_bias("zero")