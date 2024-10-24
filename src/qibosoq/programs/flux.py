"""Flux program used by qibosoq to execute sequences and sweeps."""

import logging
from typing import Dict, List, Tuple

import numpy as np
from qick import QickSoc
from qick.asm_v1 import QickRegister

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import (
    Arbitrary,
    Element,
    FluxExponential,
    Pulse,
    Rectangular,
)
from qibosoq.programs.base import BaseProgram
from ..drivers.TI_DAC80508 import DAC80508

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class FluxProgram(BaseProgram):
    """Abstract class for flux-tunable qubits programs."""

    def __init__(
        self, soc: QickSoc, ti_dac: DAC80508, qpcfg: Config, sequence: List[Element], qubits: List[Qubit]
    ):
        """Define an empty dictionary for bias sweepers and call super().__init__."""
        self.bias_sweep_registers: Dict[int, Tuple[QickRegister, QickRegister]] = {}
        self.ti_dac = ti_dac
        super().__init__(soc, qpcfg, sequence, qubits)


    def execute_flux_pulse(self, pulse: Pulse):
        """Fire a fast flux pulse."""
        gen_ch = pulse.dac
        max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])
        # bias = self.find_qubit_sweetspot(pulse)
        # sweetspot = np.trunc(bias * max_gain).astype(int)

        num_samples = self.soc.us2cycles(pulse.duration, gen_ch=gen_ch)
        samples_per_clk = self._gen_mgrs[gen_ch].samps_per_clk
        num_samples *= samples_per_clk  # the duration here is expressed in samples

        if isinstance(pulse, Rectangular):
            amp = np.trunc(pulse.amplitude * max_gain).astype(int)
            # i_vals = np.full(num_samples, amp) # no predistortion!

            # PREDISTORTION
            x  = np.arange(0, num_samples) * pulse.duration/num_samples
            square_waveform = np.ones(num_samples)
            predistortion_1 = np.exp(0.155* x) # (compensate DC filtering)
            predistortion_2 = 0.05 * np.exp(-100 * x) # (compensate RF filtering)
            i_vals  = np.clip(0.9 * amp * (0.5 * (square_waveform + predistortion_1) + predistortion_2), -max_gain, max_gain)

        elif isinstance(pulse, FluxExponential):
            i_vals = pulse.i_values(num_samples, max_gain)
        elif isinstance(pulse, Arbitrary):
            i_vals = np.array(pulse.i_values)
            logger.info("Arbitrary shaped flux pulse. q_vals will be ignored.")
        else:
            raise NotImplementedError(
                "Only Rectangular, FluxExponential and Arbitrary are supported for flux pulses"
            )

        # # add a clock cycle of sweetspot values
        # i_vals = np.append(i_vals + sweetspot, np.full(samples_per_clk, sweetspot))
        q_vals = np.zeros(len(i_vals))

        if (abs(i_vals) > max_gain).any():
            raise ValueError("Flux pulse got amplitude > 1")

        self.add_pulse(gen_ch, pulse.name, i_vals, q_vals)
        self.set_pulse_registers(
            ch=gen_ch,
            waveform=pulse.name,
            style="arb",
            outsel="input",
            stdysel="zero",
            freq=0,
            phase=0,
            gain=max_gain,
        )
        self.pulse(ch=gen_ch)

    def declare_nqz_flux(self):
        """Declare nqz = 1 for used flux channel."""
        for qubit in self.qubits:
            if qubit.rf_dac is not None:
                flux_ch = qubit.rf_dac
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

        # self.set_bias("sweetspot")

        for elem in self.sequence:
            # wait the needed wait time so that the start is timed correctly
            if isinstance(elem.start_delay, QickRegister):
                self.sync(elem.start_delay.page, elem.start_delay.addr)
            else:  # assume is number
                delay_start = self.soc.us2cycles(elem.start_delay)
                if delay_start != 0:
                    self.synci(delay_start)

            if elem.type == "readout":
                self.execute_readout_pulse(
                    elem, muxed_pulses_executed, muxed_ro_executed_indexes
                )
            elif elem.type == "drive":
                assert isinstance(elem, Pulse)
                self.execute_drive_pulse(elem, last_pulse_registered)
            elif elem.type == "flux":
                assert isinstance(elem, Pulse)
                self.execute_flux_pulse(elem)

        self.wait_all()
        # self.set_bias("zero")
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
            self.declare_nqz_zones(
                [pulse for pulse in sequence if pulse.type == "readout"]
            )
        self.declare_readout_freq()
