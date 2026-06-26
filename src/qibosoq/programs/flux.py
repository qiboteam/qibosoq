"""Flux program used by qibosoq to execute sequences and sweeps."""

import logging
from typing import Dict, List, Tuple

import numpy as np
from qick import QickSoc
from qick.asm_v1 import QickRegister

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, ConfigV2, Qubit
from qibosoq.components.pulses import (
    Arbitrary,
    Element,
    FluxExponential,
    Pulse,
    Rectangular,
)
from qibosoq.programs.base import BaseProgram, BaseProgramV2

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class FluxProgram(BaseProgram):
    """Abstract class for flux-tunable qubits programs."""

    def __init__(
        self, soc: QickSoc, qpcfg: Config, sequence: List[Element], qubits: List[Qubit]
    ):
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
                gain=np.trunc(max_gain * qubit.bias).astype(int),
            )

            if flux_ch in self.bias_sweep_registers:
                swept_reg, non_swept_reg = self.bias_sweep_registers[flux_ch]
                if mode == "sweetspot":
                    non_swept_reg.set_to(swept_reg)
                elif mode == "zero":
                    non_swept_reg.set_to(0)

            self.pulse(ch=flux_ch)
        self.sync_all(50)  # wait all pulses are fired + 50 clks

    def find_qubit_sweetspot(self, pulse: Pulse) -> float:
        """Return bias of a qubit from flux pulse."""
        for qubit in self.qubits:
            if pulse.dac == qubit.dac:
                return qubit.bias if qubit.bias else 0
        return 0.0

    def execute_flux_pulse(self, pulse: Pulse):
        """Fire a fast flux pulse the starts and ends in sweetspot."""
        gen_ch = pulse.dac
        max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])
        bias = self.find_qubit_sweetspot(pulse)
        sweetspot = np.trunc(bias * max_gain).astype(int)

        duration = self.soc.us2cycles(pulse.duration, gen_ch=gen_ch)
        samples_per_clk = self._gen_mgrs[gen_ch].samps_per_clk
        duration *= samples_per_clk  # the duration here is expressed in samples

        if isinstance(pulse, Rectangular):
            amp = np.trunc(pulse.amplitude * max_gain).astype(int)
            i_vals = np.full(duration, amp)
        elif isinstance(pulse, FluxExponential):
            i_vals = pulse.i_values(duration, max_gain)
        elif isinstance(pulse, Arbitrary):
            i_vals = np.array(pulse.i_values)
            logger.info("Arbitrary shaped flux pulse. q_vals will be ignored.")
        else:
            raise NotImplementedError(
                "Only Rectangular, FluxExponential and Arbitrary are supported for flux pulses"
            )

        # add a clock cycle of sweetspot values
        i_vals = np.append(i_vals + sweetspot, np.full(samples_per_clk, sweetspot))
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
                is_ch_mux = "n_tones" in self.soccfg["gens"][flux_ch]
                if not is_ch_mux:
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
            self.declare_nqz_zones(
                [pulse for pulse in sequence if pulse.type == "readout"]
            )
        self.declare_readout_freq()


class FluxProgramV2(BaseProgramV2):
    """Abstract class for flux-tunable qubits programs."""

    def __init__(
        self, soc: QickSoc, qpcfg: ConfigV2, sequence: List[Element], qubits: List[Qubit]
    ):
        """Call super().__init__."""
        super().__init__(soc, qpcfg, sequence, qubits)

    def register_bias_pulses(self):
        """Pre-register constant bias pulses for all flux qubits.

        Must be called from _initialize before the repetition loop.
        Registers both sweetspot and zero-amplitude pulses per qubit DAC.
        """
        for qubit in self.qubits:
            if qubit.bias is None or qubit.dac is None or qubit.bias == 0:
                continue
            flux_ch = qubit.dac
            for name, gain in [
                (f"bias_sweetspot_{flux_ch}", float(qubit.bias)),
                (f"bias_zero_{flux_ch}", 0.0),
            ]:
                self.add_pulse(
                    ch=flux_ch,
                    name=name,
                    style="const",
                    freq=0,
                    phase=0,
                    gain=gain,
                    length=0.1,  # 0.1 µs — short enough to not delay the experiment
                )

    def set_bias(self, mode: str = "sweetspot"):
        """Fire a pre-registered constant bias pulse on every flux DAC.

        register_bias_pulses() must have been called in _initialize first.
        Args:
            mode: 'sweetspot' applies qubit.bias amplitude; 'zero' outputs nothing.
        """
        for qubit in self.qubits:
            if qubit.bias is None or qubit.dac is None or qubit.bias == 0:
                continue
            flux_ch = qubit.dac
            if mode == "sweetspot":
                name = f"bias_sweetspot_{flux_ch}"
            elif mode == "zero":
                name = f"bias_zero_{flux_ch}"
            else:
                raise NotImplementedError(f"Mode {mode} not supported")
            self.pulse(ch=flux_ch, name=name, t=0)

    def find_qubit_sweetspot(self, pulse: Pulse) -> float:
        """Return bias of a qubit from flux pulse."""
        for qubit in self.qubits:
            if pulse.dac == qubit.dac:
                return qubit.bias if qubit.bias else 0
        return 0.0

    def _register_flux_pulse(self, pulse: Pulse):
        """Pre-register a flux pulse envelope and pulse definition.

        Must be called from _initialize for each flux pulse in the sequence.
        Uses add_envelope + add_pulse(style='arb'), the v2 equivalents of the
        v1 four-argument add_pulse + set_pulse_registers pair.
        """
        gen_ch = pulse.dac
        max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])
        bias = self.find_qubit_sweetspot(pulse)
        sweetspot = np.trunc(bias * max_gain).astype(int)

        duration_cycles = self.soc.us2cycles(pulse.duration, gen_ch=gen_ch)
        samples_per_clk = self.soccfg["gens"][gen_ch]["samps_per_clk"]
        duration_samples = int(duration_cycles * samples_per_clk)

        if isinstance(pulse, Rectangular):
            amp = np.trunc(pulse.amplitude * max_gain).astype(int)
            i_vals = np.full(duration_samples, amp)
        elif isinstance(pulse, FluxExponential):
            i_vals = pulse.i_values(duration_samples, max_gain)
        elif isinstance(pulse, Arbitrary):
            i_vals = np.array(pulse.i_values)
            logger.info("Arbitrary shaped flux pulse. q_vals will be ignored.")
        else:
            raise NotImplementedError(
                "Only Rectangular, FluxExponential and Arbitrary are supported for flux pulses"
            )

        # append one clock cycle of sweetspot to return to sweetspot after pulse
        i_vals = np.append(i_vals + sweetspot, np.full(samples_per_clk, sweetspot))
        q_vals = np.zeros(len(i_vals))

        if (abs(i_vals) > max_gain).any():
            raise ValueError("Flux pulse got amplitude > 1")

        self.add_envelope(ch=gen_ch, name=pulse.name, idata=i_vals, qdata=q_vals)
        self.add_pulse(
            ch=gen_ch,
            name=pulse.name,
            style="arb",
            envelope=pulse.name,
            freq=0,
            phase=0,
            gain=1.0,  # amplitude already encoded in i_vals (scaled to max_gain)
        )

    def execute_flux_pulse(self, pulse: Pulse):
        """Fire a pre-registered flux pulse (_register_flux_pulse must be called first)."""
        self.pulse(ch=pulse.dac, name=pulse.name, t=0)

    def declare_nqz_flux(self):
        """Declare nqz = 1 for used flux channel."""
        for qubit in self.qubits:
            if qubit.dac is not None:
                flux_ch = qubit.dac
                is_ch_mux = "n_tones" in self.soccfg["gens"][flux_ch]
                if not is_ch_mux:
                    self.declare_gen(flux_ch, nqz=1)

    def declare_gen_and_ro(self, sequence: List[Pulse]):
        """Declare all generators and readout frequencies.

        Declares drives, fluxes and readout (mux or not) and readout freq.
        """
        # declare generators first
        # for simplicity, we assume that there it is axis_signal_gen_v6 or axis_sg_int4_v2 (no mux) 
        self.batch_declare_gen([pulse for pulse in sequence if pulse.type == "drive"])

        self.declare_nqz_flux()
        if self.is_mux:
            self.declare_gen_mux_ro()
        else:
            self.declare_nqz_zones(
                [pulse for pulse in sequence if pulse.type == "readout"]
            )
        self.declare_readout_freq()
