"""Base program used by qibosoq to execute sequences and sweeps."""

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import List, Tuple

import numpy as np
import numpy.typing as npt
from qick import QickProgram, QickSoc

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components import Config, Pulse, Qubit

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
        self.readouts_per_experiment = None

        self.relax_delay = self.us2cycles(qpcfg.repetition_duration)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        self.pulses_registered = False
        self.registered_waveform = []

        if self.is_mux:
            self.multi_ro_pulses = self.create_mux_ro_dict()
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

        # pulse length converted with DAC CLK
        us_length = pulse.duration
        soc_length = self.soc.us2cycles(us_length, gen_ch=gen_ch)

        is_drag = pulse.shape == "drag"
        is_gaus = pulse.shape == "gaussian"
        is_rect = pulse.shape == "rectangular"

        # pulse freq converted with frequency matching
        freq = self.soc.freq2reg(pulse.frequency, gen_ch=gen_ch, ro_ch=pulse.adc)

        # if pulse is drag or gauss first define the i-q shape and then set reg
        if is_drag or is_gaus:
            name = pulse.name
            sigma = (soc_length / pulse.rel_sigma) * np.sqrt(2)

            if is_gaus:
                name = f"{gen_ch}_gaus_{round(sigma, 2)}_{round(soc_length, 2)}"
                if name not in self.registered_waveform:
                    self.add_gauss(ch=gen_ch, name=name, sigma=sigma, length=soc_length)
                    self.registered_waveform.append(name)

            elif is_drag:
                # delta will be divided for the same quantity, we are setting it = 1
                delta = self.soccfg["gens"][gen_ch]["samps_per_clk"] * self.soccfg["gens"][gen_ch]["f_fabric"]
                name = (
                    f"{gen_ch}_drag_{round(sigma, 2)}_{round(soc_length, 2)}_{round(pulse.beta, 2)}_{round(delta, 2)}"
                )

                if name not in self.registered_waveform:
                    self.add_DRAG(
                        ch=gen_ch,
                        name=name,
                        sigma=sigma,
                        delta=delta,
                        alpha=-pulse.beta,
                        length=soc_length,
                    )
                    self.registered_waveform.append(name)

            self.set_pulse_registers(
                ch=gen_ch,
                style="arb",
                freq=freq,
                phase=phase,
                gain=gain,
                waveform=name,
            )

        # if pulse is rectangular set directly register
        elif is_rect:
            self.set_pulse_registers(ch=gen_ch, style="const", freq=freq, phase=phase, gain=gain, length=soc_length)

        else:
            raise NotImplementedError(f"Shape {pulse} not supported!")

    def body(self, wait: bool = True):
        """Execute sequence of pulses.

        For each pulses calls the add_pulse_to_register function (if not already registered)
        before firing it. If the pulse is a readout, it does a measurement and does
        not wait for the end of it. At the end of the sequence wait for meas and clock.
        """
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
        if wait:
            self.sync_all(self.relax_delay)

    # pylint: disable=unexpected-keyword-arg, arguments-renamed
    def acquire(
        self,
        soc: QickSoc,
        readouts_per_experiment: int = 1,
        load_pulses: bool = True,
        progress: bool = False,
        debug: bool = False,
        average: bool = False,
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Call the super() acquire function.

        Args:
            readouts_per_experiment (int): relevant for internal acquisition
            load_pulse, progress, debug (bool): internal Qick parameters
            progress (bool): if true shows a progress bar, slows down things
            debug (bool): if true prints the program actually executed
            average (bool): if true return averaged res, otherwise single shots
        """
        if self.readouts_per_experiment is not None:
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

    def create_mux_ro_dict(self) -> dict:
        """Create a dictionary containing grouped readout pulses.

        Example of dictionary:
        { 'start_time_0': [pulse1, pulse2],
        'start_time_1': [pulse3]}
        """
        mux_dict = {}
        for pulse in (pulse for pulse in self.sequence if pulse.type == "readout"):
            if round(pulse.start, 5) not in mux_dict:
                if len(mux_dict) > 0:
                    if (pulse.start - list(mux_dict)[-1]) < 2:  # TODO not 2, but pulses len
                        mux_dict[round(pulse.start, 5)] = mux_dict[list(mux_dict)[-1]]
                        del mux_dict[list(mux_dict)[-2]]
                    else:
                        mux_dict[round(pulse.start, 5)] = []
                else:
                    mux_dict[round(pulse.start, 5)] = []
            mux_dict[round(pulse.start, 5)].append(pulse)

        self.readouts_per_experiment = len(mux_dict)
        return mux_dict

    @abstractmethod
    def initialize(self):
        """Abstract initialization."""
        raise NotImplementedError
