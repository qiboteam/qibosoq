"""Flux program used by qibosoq to execute sequences and sweeps."""

import logging
from typing import Dict, List, Tuple

import numpy as np
from qick import QickSoc
from qick.qick_asm import QickRegister

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import FluxExponential, Pulse, Rectangular
from qibosoq.programs.base import BaseProgram

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class FluxProgram(BaseProgram):
    """Abstract class for flux-tunable qubits programs."""

    def __init__(self, soc: QickSoc, qpcfg: Config, sequence: List[Pulse], qubits: List[Qubit]):
        """Define an empty dictionary for bias sweepers and call super().__init__."""
        self.bias_sweep_registers: Dict[int, Tuple[QickRegister, QickRegister]] = {}
        super().__init__(soc, qpcfg, sequence, qubits)

    def set_bias(self, mode: str = "sweetspot"):
        """Set qubits flux lines to a bias level.

        Note that this fuction acts only on the qubits used in self.sequence.
        Args:
            mode (str): can be 'sweetspot' or 'zero'
        """
        duration = 48  # minimum len

        for qubit in self.qubits:
            # if bias is zero, just skip the qubit
            if qubit.bias is None or qubit.dac is None or qubit.bias == 0:
                continue

            flux_ch = qubit.dac
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

    def find_qubit_sweetspot(self, pulse: Pulse):
        """Return bias of a qubit from flux pulse."""
        bias = 0.0
        for qubit in self.qubits:
            if pulse.dac == qubit.dac:
                bias = qubit.bias if qubit.bias else 0
        return bias

    def execute_flux_pulse(self, pulse: Pulse):
        """Fire a fast flux pulse the starts and ends in sweetspot."""
        gen_ch = pulse.dac
        max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])
        bias = self.find_qubit_sweetspot(pulse)
        sweetspot = int(bias * max_gain)

        duration = self.soc.us2cycles(pulse.duration, gen_ch=gen_ch)
        samples_per_clk = self._gen_mgrs[gen_ch].samps_per_clk
        duration *= samples_per_clk  # the duration here is expressed in samples
        padding = samples_per_clk

        if isinstance(pulse, Rectangular):
            amp = int(pulse.amplitude * max_gain)
            i_vals = np.full(duration, amp)
        elif isinstance(pulse, FluxExponential):
            i_vals = pulse.get_i_values(duration, max_gain)
        else:
            raise NotImplementedError("Only Rectangular and FluxExponential flux pulses are supported")

        i_vals = np.append(i_vals + sweetspot, np.full(padding, sweetspot))
        q_vals = np.zeros(len(i_vals))

        if (abs(i_vals) > max_gain).any():
            raise ValueError("Flux pulse got amplitude > 1")

        self.add_pulse(gen_ch, pulse.name, i_vals, q_vals)
        self.set_pulse_registers(
            ch=gen_ch,
            waveform=pulse.name,
            style="arb",
            outsel="input",
            stdysel="last",
            freq=0,
            phase=0,
            gain=max_gain,
        )
        self.pulse(ch=gen_ch)

    def declare_nqz_flux(self):
        """Declare nqz = 1 for used flux channel."""
        for qubit in self.qubits:
            if qubit.dac is not None:
                flux_ch = qubit.dac
                self.declare_gen(flux_ch, nqz=1)

    def body(self):
        """Execute sequence of pulses.

        For each pulses calls the add_pulse_to_register function (if not already registered)
        before firing it. If the pulse is a readout, it does a measurement and does
        not wait for the end of it. At the end of the sequence wait for meas and clock.
        """
        # in the form of {dac_number_0: last_pulse_of_dac_0, ...}
        last_pulse_registered = {}
        muxed_pulses_executed = []
        muxed_ro_executed_indexes = []

        self.set_bias("sweetspot")

        for pulse in self.sequence:
            # wait the needed wait time so that the start is timed correctly
            if isinstance(pulse.start_delay, QickRegister):
                self.sync(pulse.start_delay.page, pulse.start_delay.addr)
            else:  # assume is number
                delay_start = self.soc.us2cycles(pulse.start_delay)
                if delay_start != 0:
                    self.synci(delay_start)

            if pulse.type == "drive":
                self.execute_drive_pulse(pulse, last_pulse_registered)
            elif pulse.type == "flux":
                self.execute_flux_pulse(pulse)
            elif pulse.type == "readout":
                self.execute_readout_pulse(pulse, muxed_pulses_executed, muxed_ro_executed_indexes)

        self.wait_all()
        self.set_bias("zero")
        self.sync_all(self.relax_delay)

    def declare_zones_and_ro(self, sequence: List[Pulse]):
        """Declare all nqz zones and readout frequencies.

        Declares drives, fluxes and readout (mux or not) and readout freq.
        """
        self.declare_nqz_zones([pulse for pulse in sequence if pulse.type == "drive"])
        self.declare_nqz_flux()
        if self.is_mux:
            self.declare_gen_mux_ro()
        else:
            self.declare_nqz_zones([pulse for pulse in sequence if pulse.type == "readout"])
        self.declare_readout_freq()
