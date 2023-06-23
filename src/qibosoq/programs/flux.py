"""Flux program used by qibosoq to execute sequences and sweeps."""

import logging
from typing import List

import numpy as np
from qick import QickSoc

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components import Config, Pulse, Qubit
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

    def flux_pulse(self, pulse: Pulse, time: int):
        """Fire a fast flux pulse the starts and ends in sweetspot."""
        gen_ch = pulse.dac
        sweetspot = 0  # TODO int(qubit.flux.bias * self.max_gain)

        duration = self.soc.us2cycles(pulse.duration, gen_ch=gen_ch)
        samples_per_clk = self._gen_mgrs[gen_ch].samps_per_clk
        duration *= samples_per_clk  # the duration here is expressed in samples

        padding = samples_per_clk
        while True:  # compute padding length
            tot_len = padding + duration
            if tot_len % samples_per_clk == 0 and tot_len > 48:
                break
            padding += 1

        amp = int(pulse.amplitude * self.max_gain) + sweetspot

        i_vals = np.full(duration, amp)
        i_vals = np.append(i_vals, np.full(padding, sweetspot))
        q_vals = np.zeros(len(i_vals))

        self.add_pulse(gen_ch, pulse.name, i_vals, q_vals)
        self.set_pulse_registers(
            ch=gen_ch,
            waveform=pulse.name,
            style="arb",
            outsel="input",
            stdysel="last",
            freq=0,
            phase=0,
            gain=self.max_gain,
        )
        self.pulse(ch=gen_ch, t=time)

    def declare_nqz_flux(self):
        """Declare nqz = 1 for used flux channel."""
        for qubit in self.qubits:
            if qubit.dac is not None:
                flux_ch = qubit.dac
                self.declare_gen(flux_ch, nqz=1)

    def body(self):
        """Body program with flux biases set."""
        self.set_bias("sweetspot")
        muxed_ro_executed_time = []
        muxed_pulses_executed = []

        last_pulse_registered = {}
        for idx in self.gen_chs:
            last_pulse_registered[idx] = None

        for pulse in self.sequence:
            # time follows tproc CLK
            time = self.soc.us2cycles(pulse.start)

            adc_ch = pulse.adc
            gen_ch = pulse.dac

            if pulse.type == "drive":
                if not self.pulses_registered:
                    # TODO
                    if not pulse == last_pulse_registered[gen_ch]:
                        self.add_pulse_to_register(pulse)
                        last_pulse_registered[gen_ch] = pulse
                self.pulse(ch=gen_ch, t=time)
            elif pulse.type == "flux":
                self.flux_pulse(pulse, time=time)
            elif pulse.type == "readout":
                if self.is_mux:
                    if pulse not in muxed_pulses_executed:
                        start = list(self.multi_ro_pulses)[len(muxed_ro_executed_time)]
                        time = self.soc.us2cycles(start)
                        self.add_muxed_readout_to_register(self.multi_ro_pulses[start])
                        muxed_ro_executed_time.append(start)
                        adcs = []
                        for ro_pulse in self.multi_ro_pulses[start]:
                            adcs.append(ro_pulse.adc)
                            muxed_pulses_executed.append(ro_pulse)
                    else:
                        continue
                else:
                    if not self.pulses_registered:
                        self.add_pulse_to_register(pulse)
                    adcs = [adc_ch]

                self.measure(
                    pulse_ch=gen_ch,
                    adcs=adcs,
                    adc_trig_offset=time + self.adc_trig_offset,
                    t=time,
                    wait=False,
                    syncdelay=self.syncdelay,
                )
        self.wait_all()
        self.set_bias("zero")
        self.soc.reset_gens()
        self.sync_all(self.relax_delay)
