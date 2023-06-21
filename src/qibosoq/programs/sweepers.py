"""Program used by qibosoq to execute sweeps."""

import logging
from typing import List, Tuple

import numpy as np
from qick import NDAveragerProgram, QickSoc
from qick.averager_program import QickSweep, merge_sweeps

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components import Config, Parameter, Pulse, Qubit, Sweeper
from qibosoq.programs.flux import FluxProgram

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class ExecuteSweeps(FluxProgram, NDAveragerProgram):
    """Class to execute arbitrary PulseSequences with a single sweep."""

    def __init__(
        self,
        soc: QickSoc,
        qpcfg: Config,
        sequence: List[Pulse],
        qubits: List[Qubit],
        sweepers: Tuple[Sweeper, ...],
    ):
        """Init function, sets sweepers parameters before calling super.__init__."""
        self.sweepers = self.sweepers_to_reversed_list(sweepers)
        super().__init__(soc, qpcfg, sequence, qubits)

    @staticmethod
    def sweepers_to_reversed_list(sweepers) -> List[Sweeper]:
        """Ensure that sweepers is a list and reverse it.

        This is because sweepers are handled by Qick in the opposite order.
        """
        if isinstance(sweepers, Sweeper):
            return [sweepers]
        return list(reversed(sweepers))

    def add_sweep_info(self, sweeper: Sweeper):
        """Register RfsocSweep objects.

        Args:
            sweeper (RfsocSweep): single qibolab sweeper object to register
        """
        starts = sweeper.starts
        stops = sweeper.stops

        sweep_list = []
        sweeper.parameters = [Parameter(par) for par in sweeper.parameters]
        sweeper.starts = np.array(sweeper.starts)
        sweeper.stops = np.array(sweeper.stops)
        if sweeper.parameters[0] is Parameter.BIAS:
            for idx, jdx in enumerate(sweeper.indexes):
                gen_ch = self.qubits[jdx].dac
                sweep_type = SWEEPERS_TYPE[sweeper.parameters[0]]
                std_register = self.get_gen_reg(gen_ch, sweep_type)
                swept_register = self.new_gen_reg(gen_ch, name=f"sweep_bias_{gen_ch}")
                self.bias_sweep_registers[gen_ch] = (swept_register, std_register)

                max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])
                starts = (sweeper.starts * max_gain).astype(int)
                stops = (sweeper.stops * max_gain).astype(int)

                new_sweep = QickSweep(
                    self,
                    swept_register,  # sweeper_register
                    starts[idx],  # start
                    stops[idx],  # stop
                    sweeper.expts,  # number of points
                )
                sweep_list.append(new_sweep)
        else:
            for idx, jdx in enumerate(sweeper.indexes):
                pulse = self.sequence[jdx]
                gen_ch = pulse.dac

                sweep_type = SWEEPERS_TYPE[sweeper.parameters[idx]]
                register = self.get_gen_reg(gen_ch, sweep_type)

                if sweeper.parameters[idx] is Parameter.AMPLITUDE:
                    max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])
                    starts = (sweeper.starts * max_gain).astype(int)
                    stops = (sweeper.stops * max_gain).astype(int)

                new_sweep = QickSweep(
                    self,
                    register,  # sweeper_register
                    starts[idx],  # start
                    stops[idx],  # stop
                    sweeper.expts,  # number of points
                )
                sweep_list.append(new_sweep)

        self.add_sweep(merge_sweeps(sweep_list))

    def initialize(self):
        """Declre nyquist zones for all the DACs and all the readout frequencies.

        Function called by AveragerProgram.__init__.
        """
        self.declare_nqz_zones([pulse for pulse in self.sequence if pulse.type == "drive"])
        self.declare_nqz_flux()
        if self.is_mux:
            self.declare_gen_mux_ro()
        else:
            self.declare_nqz_zones([pulse for pulse in self.sequence if pulse.type == "readout"])
        self.declare_readout_freq()

        self.pulses_registered = True
        for pulse in self.sequence:
            if self.is_mux:
                if pulse.type != "drive":
                    continue
            self.add_pulse_to_register(pulse)

        for sweeper in self.sweepers:
            self.add_sweep_info(sweeper)

        for _, registers in self.bias_sweep_registers.items():
            swept_reg, non_swept_reg = registers
            non_swept_reg.set_to(swept_reg)

        self.sync_all(self.wait_initialize)


SWEEPERS_TYPE = {
    Parameter.FREQUENCY: "freq",
    Parameter.AMPLITUDE: "gain",
    Parameter.BIAS: "gain",
    Parameter.RELATIVE_PHASE: "phase",
    Parameter.START: "t",
}
