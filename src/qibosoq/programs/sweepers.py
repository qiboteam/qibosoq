"""Program used by qibosoq to execute sweeps."""

import logging
from typing import Iterable, List, Union

import numpy as np
from qick import NDAveragerProgram, QickSoc
from qick.averager_program import QickSweep, merge_sweeps
from qick.asm_v2 import AveragerProgramV2, QickSweep1D

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, ConfigV2, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Element
from qibosoq.programs.flux import FluxProgram, FluxProgramV2

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

    def __init__(
        self,
        soc: QickSoc,
        qpcfg: Config,
        sequence: List[Element],
        qubits: List[Qubit],
        *sweepers: Sweeper,
    ):
        """Init function, sets sweepers parameters before calling super.__init__."""
        self.sweepers = reversed_sweepers(sweepers)
        super().__init__(soc, qpcfg, sequence, qubits)

        self.reps = qpcfg.reps  # must be done after NDAveragerProgram init
        self.soft_avgs = qpcfg.soft_avgs

    def validate(self, sweeper: Sweeper):
        """Check if a sweeper is valid.

        In particular, it raises an error if:
            - sweeper is on bias, but not enough information has been given with the qubit
            - sweeper is on bias wih flux pulses in the sequence
            - sweeper is on flux pulses
            - sweeper is on duration
            - sweeper has pulse paramaters and bias
        """
        for idx, par in enumerate(sweeper.parameters):
            if par is Parameter.BIAS:
                if any(pulse.type == "flux" for pulse in self.sequence):
                    raise NotImplementedError(
                        "Sweepers on bias are not compatible with flux pulses."
                    )
                if any(par is not Parameter.BIAS for par in sweeper.parameters):
                    raise NotImplementedError(
                        "Sweepers on bias cannot be swept at the same time with other sweepers."
                    )
                qubit = self.qubits[sweeper.indexes[idx]]
                if qubit.dac is None or qubit.bias is None:
                    raise ValueError(f"Bias swept qubit had incomplete values: {qubit}")
            elif par is Parameter.DURATION:
                raise NotImplementedError("Sweepers on duration are not implemented.")
            else:
                if self.sequence[sweeper.indexes[idx]].type == "flux":
                    raise NotImplementedError(
                        "Sweepers on flux pulses are not implemented."
                    )

    def add_sweep_info_bias(self, sweeper: Sweeper) -> List[Sweeper]:
        """Generate RfsocSweep objects for biases.

        Args:
            sweeper: single qibolab sweeper object to register
        """
        sweep_list = []
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
        return sweep_list

    def add_sweep_info(self, sweeper: Sweeper):
        """Register RfsocSweep objects.

        Args:
            sweeper: single qibolab sweeper object to register
        """
        self.validate(sweeper)

        if sweeper.parameters[0] is Parameter.BIAS:
            sweep_list = self.add_sweep_info_bias(sweeper)
            merged = merge_sweeps(sweep_list)
            self.add_sweep(merged)
            return

        sweep_list = []
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

        merged = merge_sweeps(sweep_list)
        self.add_sweep(merged)

    def initialize(self):
        """Declre nyquist zones for all the DACs and all the readout frequencies.

        Function called by AveragerProgram.__init__.
        """
        self.declare_zones_and_ro(self.pulse_sequence)

        self.pulses_registered = True
        for pulse in self.pulse_sequence:
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

class ExecuteSweepsV2(FluxProgramV2, AveragerProgramV2):
    """Class to execute PulseSequences with parameter sweeps on tProc v2.

    Each Sweeper maps to one loop level via add_loop.  Swept pulse parameters
    (freq, gain, phase, delay) are passed as QickSweep1D objects to add_pulse /
    pulse(), which QICK v2 resolves into hardware loop instructions.
    """

    def __init__(
        self,
        soc: QickSoc,
        qpcfg: ConfigV2,
        sequence: List[Element],
        qubits: List[Qubit],
        *sweepers: Sweeper,
    ):
        self.sweepers = list(sweepers)
        super().__init__(soc, qpcfg, sequence, qubits)

    def validate(self, sweeper: Sweeper):
        """Raise if the sweeper requests an unsupported combination."""
        for idx, par in enumerate(sweeper.parameters):
            if par is Parameter.BIAS:
                if any(pulse.type == "flux" for pulse in self.sequence):
                    raise NotImplementedError(
                        "Sweepers on bias are not compatible with flux pulses."
                    )
                if any(p is not Parameter.BIAS for p in sweeper.parameters):
                    raise NotImplementedError(
                        "Sweepers on bias cannot be combined with other sweepers."
                    )
                qubit = self.qubits[sweeper.indexes[idx]]
                if qubit.dac is None or qubit.bias is None:
                    raise ValueError(f"Bias swept qubit had incomplete values: {qubit}")
            elif par is Parameter.DURATION:
                raise NotImplementedError("Sweepers on duration are not implemented.")
            else:
                if self.sequence[sweeper.indexes[idx]].type == "flux":
                    raise NotImplementedError(
                        "Sweepers on flux pulses are not implemented."
                    )

    def _initialize(self, cfg):
        """Declare channels, add sweep loops, and pre-register all pulses."""
        self.declare_gen_and_ro(self.pulse_sequence)

        for sweeper in self.sweepers:
            self.validate(sweeper)

        # One named loop per sweeper; index 0 becomes the outermost loop.
        for i, sweeper in enumerate(self.sweepers):
            self.add_loop(f"sweep_{i}", count=sweeper.expts)

        # Build sweep lookup tables.
        # pulse_sweeps: {seq_idx: {Parameter: QickSweep1D}}
        # bias_sweeps:  {qubit_idx: QickSweep1D}
        pulse_sweeps = {}
        bias_sweeps = {}
        for i, sweeper in enumerate(self.sweepers):
            loop = f"sweep_{i}"
            for idx, (par, jdx) in enumerate(zip(sweeper.parameters, sweeper.indexes)):
                start = float(sweeper.starts[idx])
                stop = float(sweeper.stops[idx])
                swept = QickSweep1D(loop, start, stop)
                if par is Parameter.BIAS:
                    bias_sweeps[jdx] = swept
                elif par is Parameter.DELAY:
                    # Set start_delay directly; _body will pass it as t=
                    self.sequence[jdx].start_delay = swept
                else:
                    pulse_sweeps.setdefault(jdx, {})[par] = swept

        # Register bias pulses (swept gain if bias is swept, static otherwise)
        for qi, qubit in enumerate(self.qubits):
            if qubit.bias is None or qubit.dac is None or qubit.bias == 0:
                continue
            flux_ch = qubit.dac
            sweetspot_gain = bias_sweeps.get(qi, float(qubit.bias))
            self.add_pulse(ch=flux_ch, name=f"bias_sweetspot_{flux_ch}",
                           style="const", freq=0, phase=0,
                           gain=sweetspot_gain, length=0.1)
            self.add_pulse(ch=flux_ch, name=f"bias_zero_{flux_ch}",
                           style="const", freq=0, phase=0, gain=0.0, length=0.1)

        # Register each pulse, substituting QickSweep1D for swept parameters
        for seq_idx, pulse in enumerate(self.sequence):
            if pulse.type == "flux":
                self._register_flux_pulse(pulse)
            elif pulse.type == "drive":
                swept = pulse_sweeps.get(seq_idx, {})
                self.add_pulse_to_register(
                    pulse,
                    freq=swept.get(Parameter.FREQUENCY),
                    gain=swept.get(Parameter.AMPLITUDE),
                    phase=swept.get(Parameter.RELATIVE_PHASE),
                )
            elif pulse.type == "readout" and pulse.adc is not None:
                self.add_ro_pulse_to_register(pulse)

    def _body(self, cfg):
        """Executed inside all sweep loops. Identical to ExecutePulseSequenceV2."""
        self.set_bias("sweetspot")

        for pulse in self.sequence:
            t = pulse.start_delay  # may be QickSweep1D for a DELAY sweep
            name = pulse.name

            if pulse.type == "readout":
                adc_ch = pulse.adc
                self.send_readoutconfig(ch=adc_ch, name=name + "_ro", t=t)
                self.pulse(ch=pulse.dac, name=name, t=t)
            elif pulse.type == "drive":
                self.pulse(ch=pulse.dac, name=name, t=t)
            elif pulse.type == "flux":
                self.execute_flux_pulse(pulse)
            else:
                raise ValueError(f"Unsupported pulse type: {pulse.type!r}")

        self.set_bias("zero")