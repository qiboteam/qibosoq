"""Program used by qibosoq to execute sweeps."""

import logging
from typing import Iterable, List, Union

from qick import NDAveragerProgram, QickSoc
from qick.averager_program import QickSweep, merge_sweeps

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Pulse
from qibosoq.programs.flux import FluxProgram

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


def reversed_sweepers(sweepers: Union[Sweeper, Iterable[Sweeper]]) -> List[Sweeper]:
    """Ensure that sweepers is a list and reverse it.

    This is because sweepers are handled by Qick in the opposite order.
    """
    if isinstance(sweepers, Sweeper):
        return [sweepers]
    return list(reversed(sweepers))  # type: ignore


class ExecuteSweeps(FluxProgram, NDAveragerProgram):
    """Class to execute arbitrary PulseSequences with a single sweep."""

    def __init__(self, soc: QickSoc, qpcfg: Config, sequence: List[Pulse], qubits: List[Qubit], *sweepers: Sweeper):
        """Init function, sets sweepers parameters before calling super.__init__."""
        self.sweepers = reversed_sweepers(sweepers)
        super().__init__(soc, qpcfg, sequence, qubits)

    def add_sweep_info(self, sweeper: Sweeper):
        """Register RfsocSweep objects.

        Args:
            sweeper: single qibolab sweeper object to register
        """
        sweep_list = []

        if sweeper.parameters[0] is Parameter.BIAS:
            for idx, jdx in enumerate(sweeper.indexes):
                gen_ch = self.qubits[jdx].dac
                if gen_ch is None:
                    raise ValueError("Qubit dac (flux bias) not provided.")
                sweep_type = "gain"
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

                sweep_type = sweeper.parameters[idx].value
                register = self.get_gen_reg(gen_ch, sweep_type)

                if sweeper.parameters[idx] is Parameter.AMPLITUDE:
                    max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])
                    starts = (sweeper.starts * max_gain).astype(int)
                    stops = (sweeper.stops * max_gain).astype(int)
                else:
                    starts = sweeper.starts
                    stops = sweeper.stops
                    if sweeper.parameters[idx] is Parameter.DELAY:
                        # define a new register for the delay
                        register = self.new_gen_reg(gen_ch, reg_type="time", tproc_reg=True)
                        pulse.start_delay = register

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
        self.declare_zones_and_ro(self.sequence)

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
