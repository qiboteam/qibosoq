"""Base program used by qibosoq to execute sequences and sweeps."""

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Dict, List, Tuple

import numpy as np
import numpy.typing as npt
from qick import QickProgram, QickSoc

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import Arbitrary, Drag, Gaussian, Pulse, Rectangular

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class BaseProgram(ABC, QickProgram):
    """Abstract class for QickPrograms."""

    def __init__(self, soc: QickSoc, qpcfg: Config, sequence: List[Pulse], qubits: List[Qubit]):
        """In this function we define the most important settings.

        In detail:
            * max_gain, adc_trig_offset, max_sampling_rate, reps are imported from
              qpcfg (runcard settings)
            * relaxdelay (for each execution) is taken from qpcfg (runcard)
            * syncdelay (for each measurement) is defined explicitly
            * wait_initialize is defined explicitly
            * super.__init__ (this will init AveragerProgram or RAveragerProgram)
        """
        self.soc = soc
        self.soccfg = soc  # this is used by qick

        self.sequence = sequence
        self.qubits = qubits

        # general settings
        self.adc_trig_offset = qpcfg.adc_trig_offset
        self.reps = qpcfg.reps

        # mux settings
        self.is_mux = qibosoq_cfg.IS_MULTIPLEXED
        self.readouts_per_experiment = len([pulse for pulse in self.sequence if pulse.type == "readout"])

        self.relax_delay = self.us2cycles(qpcfg.repetition_duration)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        self.pulses_registered = False
        self.registered_waveforms = {}
        for pulse in sequence:
            if pulse.dac not in self.registered_waveforms:
                self.registered_waveforms[pulse.dac] = []

        if self.is_mux:
            self.multi_ro_pulses = self.group_mux_ro()
            self.readouts_per_experiment = len(self.multi_ro_pulses)

        # pylint: disable-next=too-many-function-args
        super().__init__(soc, asdict(qpcfg))

    def declare_nqz_zones(self, sequence: List[Pulse]):
        """Declare nqz zone (1-2) for a given PulseSequence.

        Args:
            sequence (PulseSequence): sequence of pulses to consider
        """
        ch_already_declared = []
        for pulse in sequence:
            freq = pulse.frequency
            gen_ch = pulse.dac

            if gen_ch not in ch_already_declared:
                ch_already_declared.append(gen_ch)
                sampling_rate = self.soccfg["gens"][gen_ch]["fs"]
                zone = 1 if freq < sampling_rate / 2 else 2
                self.declare_gen(gen_ch, nqz=zone)

    def declare_readout_freq(self):
        """Declare ADCs downconversion frequencies."""
        adc_ch_already_declared = []
        for readout_pulse in (pulse for pulse in self.sequence if pulse.type == "readout"):
            adc_ch = readout_pulse.adc
            ro_ch = readout_pulse.dac
            if adc_ch not in adc_ch_already_declared:
                adc_ch_already_declared.append(adc_ch)
                length = self.soc.us2cycles(readout_pulse.duration, gen_ch=ro_ch)

                freq = readout_pulse.frequency

                # in declare_readout frequency in MHz
                self.declare_readout(ch=adc_ch, length=length, freq=freq, gen_ch=ro_ch)

    def add_pulse_to_register(self, pulse: Pulse):
        """Call the set_pulse_registers function, needed before firing a pulse.

        Args:
            pulse (Pulse): pulse object to load in the register
        """
        gen_ch = pulse.dac
        max_gain = int(self.soccfg["gens"][gen_ch]["maxv"])

        # assign gain parameter
        gain = int(pulse.amplitude * max_gain)
        phase = self.deg2reg(pulse.relative_phase, gen_ch=gen_ch)

        # pulse freq converted with frequency matching
        freq = self.soc.freq2reg(pulse.frequency, gen_ch=gen_ch, ro_ch=pulse.adc)

        # pulse length converted with DAC CLK
        us_length = pulse.duration
        soc_length = self.soc.us2cycles(us_length, gen_ch=gen_ch)

        if isinstance(pulse, Rectangular):
            self.set_pulse_registers(ch=gen_ch, style="const", freq=freq, phase=phase, gain=gain, length=soc_length)
            return

        if isinstance(pulse, Gaussian):
            sigma = (soc_length / pulse.rel_sigma) * np.sqrt(2)
            name = f"{gen_ch}_gaus_{round(sigma, 2)}_{round(soc_length, 2)}"
            if name not in self.registered_waveforms[gen_ch]:
                self.add_gauss(ch=gen_ch, name=name, sigma=sigma, length=soc_length)
                self.registered_waveforms[gen_ch].append(name)
        elif isinstance(pulse, Drag):
            delta = -self.soccfg["gens"][gen_ch]["samps_per_clk"] * self.soccfg["gens"][gen_ch]["f_fabric"] / 2
            sigma = (soc_length / pulse.rel_sigma) * np.sqrt(2)
            name = f"{gen_ch}_drag_{round(sigma, 2)}_{round(soc_length, 2)}_{round(pulse.beta, 2)}_{round(delta, 2)}"
            if name not in self.registered_waveforms[gen_ch]:
                self.add_DRAG(
                    ch=gen_ch,
                    name=name,
                    sigma=sigma,
                    delta=delta,
                    alpha=pulse.beta,
                    length=soc_length,
                )
                self.registered_waveforms[gen_ch].append(name)
        elif isinstance(pulse, Arbitrary):
            name = pulse.name
            if name not in self.registered_waveforms[gen_ch]:
                self.add_pulse(gen_ch, name, pulse.i_values, pulse.q_values)
                self.registered_waveforms[gen_ch].append(name)

        self.set_pulse_registers(
            ch=gen_ch,
            style="arb",
            freq=freq,
            phase=phase,
            gain=gain,
            waveform=name,
        )

    def execute_drive_pulse(self, pulse: Pulse, last_pulse_registered: Dict):
        """Register a drive pulse if needed, then trigger the respective DAC.

        A pulse gets register if:
        - it didn't happen in `initialize` (`self.pulses_registered` is False)
        - it is not identical to the last pulse registered

        """
        if not self.pulses_registered and (
            pulse.dac not in last_pulse_registered or pulse != last_pulse_registered[pulse.dac]
        ):
            self.add_pulse_to_register(pulse)
            last_pulse_registered[pulse.dac] = pulse
        self.pulse(ch=pulse.dac, t=0)

    def execute_readout_pulse(
        self, pulse: Pulse, muxed_pulses_executed: List[Pulse], muxed_ro_executed_indexes: List[int]
    ):
        """Register a readout pulse and perform a measurement."""
        adcs = []
        if self.is_mux:
            if pulse in muxed_pulses_executed:
                return
            idx_mux = next(idx for idx, mux_time in enumerate(self.multi_ro_pulses) if pulse in mux_time)
            self.add_muxed_readout_to_register(self.multi_ro_pulses[idx_mux])
            muxed_ro_executed_indexes.append(idx_mux)
            for ro_pulse in self.multi_ro_pulses[idx_mux]:
                adcs.append(ro_pulse.adc)
                muxed_pulses_executed.append(ro_pulse)
        else:
            if not self.pulses_registered:
                self.add_pulse_to_register(pulse)
            adcs = [pulse.adc]

        self.measure(
            pulse_ch=pulse.dac,
            adcs=adcs,
            adc_trig_offset=self.adc_trig_offset,
            wait=False,
            syncdelay=self.syncdelay,
        )

    # pylint: disable=unexpected-keyword-arg, arguments-renamed
    def acquire(
        self,
        soc: QickSoc,
        load_pulses: bool = True,
        progress: bool = False,
        debug: bool = False,
        average: bool = False,
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Call the super() acquire function.

        Args:
            load_pulse, progress, debug (bool): internal Qick parameters
            progress (bool): if true shows a progress bar, slows down things
            debug (bool): if true prints the program actually executed
            average (bool): if true return averaged res, otherwise single shots
        """
        readouts_per_experiment = self.readouts_per_experiment
        # if there are no readouts, temporaray set 1 so that qick can execute properly
        reads_per_rep = 1 if readouts_per_experiment == 0 else readouts_per_experiment

        res = super().acquire(
            soc,
            readouts_per_experiment=reads_per_rep,
            load_pulses=load_pulses,
            progress=progress,
            debug=debug,
        )
        # if there are no actual readouts, return empty lists
        if readouts_per_experiment == 0:
            return [], []
        if average:
            # for sweeps res has 3 parameters, the first is not used
            return res[-2:]
        # super().acquire function fill buffers used in collect_shots
        return self.collect_shots()[-2:]

    def collect_shots(self) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Read the internal buffers and returns single shots (i,q)."""
        tot_i = []
        tot_q = []

        adcs = []  # list of adcs per readouts (not unique values)
        lengths = []  # length of readouts (only one per adcs)
        for pulse in (pulse for pulse in self.sequence if pulse.type == "readout"):
            adc_ch = pulse.adc
            ro_ch = pulse.dac
            if adc_ch not in adcs:
                lengths.append(self.soc.us2cycles(pulse.duration, gen_ch=ro_ch))
            adcs.append(adc_ch)

        adcs, adc_count = np.unique(adcs, return_counts=True)

        for idx, adc_ch in enumerate(adcs):
            count = adc_count[idx]
            if self.expts:  # self.expts is None if this is not a sweep
                shape = (count, self.expts, self.reps)
            else:
                shape = (count, self.reps)
            i_val = self.di_buf[idx].reshape(shape) / lengths[idx]
            q_val = self.dq_buf[idx].reshape(shape) / lengths[idx]

            tot_i.append(i_val)
            tot_q.append(q_val)
        return np.array(tot_i), np.array(tot_q)

    def declare_gen_mux_ro(self):
        """Declare nqz zone for multiplexed readout."""
        adc_ch_added = []

        mux_freqs = []
        mux_gains = []

        ro_ch = None
        for pulse in (pulse for pulse in self.sequence if pulse.type == "readout"):
            adc_ch = pulse.adc
            ro_ch = pulse.dac

            if adc_ch not in adc_ch_added:
                adc_ch_added.append(adc_ch)
                freq = pulse.frequency
                zone = 1 if freq < self.soccfg["gens"][ro_ch]["fs"] / 2 else 2
                mux_freqs.append(freq)
                mux_gains.append(pulse.amplitude)
        if ro_ch is None:
            return
        self.declare_gen(
            ch=ro_ch,
            nqz=zone,
            mixer_freq=0,
            mux_freqs=mux_freqs,
            mux_gains=mux_gains,
            ro_ch=adc_ch_added[0],
        )

    def add_muxed_readout_to_register(self, ro_pulses: List[Pulse]):
        """Register multiplexed pulse before firing it."""
        # readout amplitude gets divided by len(mask), we are here fixing the values
        mask = [0, 1, 2]

        pulse = ro_pulses[0]
        gen_ch = pulse.dac
        length = self.soc.us2cycles(pulse.duration, gen_ch=gen_ch)

        if pulse.shape != "rectangular":
            raise TypeError("Only rectangular pulses can be multiplexed")

        self.set_pulse_registers(ch=gen_ch, style="const", length=length, mask=mask)

    def group_mux_ro(self) -> list:
        """Create a list containing readout pulses grouped by start time.

        Example of list:
        [[pulse1, pulse2], [pulse3]]
        """
        mux_list = []
        len_last_readout = 0
        for pulse in (pulse for pulse in self.sequence if pulse.type == "readout"):
            if pulse.start_delay <= len_last_readout and len(mux_list) > 0:
                # add the pulse to the last multiplexed readout
                mux_list[-1].append(pulse)
            else:
                # add a new multiplexed readout
                mux_list.append([pulse])
            len_last_readout = pulse.duration

        return mux_list

    @abstractmethod
    def initialize(self):
        """Abstract initialization."""
        raise NotImplementedError
