"""Flux program used by qibosoq to execute sequences and sweeps."""

import logging
from typing import List

import numpy as np
from qick import QickSoc

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import Pulse
from qibosoq.programs.base import BaseProgram

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class FluxProgram(BaseProgram):
    """Abstract class for flux-tunable qubits programs."""

    def __init__(self, soc: QickSoc, qpcfg: Config, sequence: List[Pulse], qubits: List[Qubit]):
        """Define an empty dictionary for bias sweepers and call super().__init__."""
        self.bias_sweep_registers = {}
        super().__init__(soc, qpcfg, sequence, qubits)

    def set_bias(self, mode: str = "sweetspot"):
        """Set qubits flux lines to a bias level.

        Note that this fuction acts only on the qubits used in self.sequence.
        Args:
            mode (str): can be 'sweetspot' or 'zero'
        """
        duration = 48  # minimum len

        for qubit in self.qubits:
            flux_ch = qubit.dac
            # if bias is zero, just skip the qubit
            if flux_ch is None or qubit.bias == 0:
                continue
            max_gain = int(self.soccfg["gens"][flux_ch]["maxv"])

            if mode == "sweetspot":
                value = max_gain
            elif mode == "zero":
                value = 0
            else:
                raise NotImplementedError(f"Mode {mode} not supported")

            i_wf = np.full(duration, value)
            q_wf = np.zeros(len(i_wf))
            self.add_pulse(flux_ch, f"const_{value}_{flux_ch}", i_wf, q_wf)
            self.set_pulse_registers(
                ch=flux_ch,
                waveform=f"const_{value}_{flux_ch}",
                style="arb",
                outsel="input",
                stdysel="last",
                freq=0,
                phase=0,
                gain=int(max_gain * qubit.bias),
            )

            if flux_ch in self.bias_sweep_registers:
                swept_reg, non_swept_reg = self.bias_sweep_registers[flux_ch]
                if mode == "sweetspot":
                    non_swept_reg.set_to(swept_reg)
                elif mode == "zero":
                    non_swept_reg.set_to(0)

            self.pulse(ch=flux_ch)
        self.sync_all(50)  # wait all pulses are fired + 50 clks

    def declare_nqz_flux(self):
        """Declare nqz = 1 for used flux channel."""
        for qubit in self.qubits:
            if qubit.dac is not None:
                flux_ch = qubit.dac
                self.declare_gen(flux_ch, nqz=1)

    def body(self):
        """Body program with flux biases set."""
        self.set_bias("sweetspot")
        super().body(wait=False)
        # the next two lines are redunant for security reasons
        self.set_bias("zero")
        self.soc.reset_gens()
        self.sync_all(self.relax_delay)
