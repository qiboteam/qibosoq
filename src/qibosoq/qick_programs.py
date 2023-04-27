""" QickPrograms used by qibosoq to execute sequences and sweeps """

from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import List, Tuple

import numpy as np
from qibolab.instruments.rfsoc import QickProgramConfig
from qibolab.platforms.abstract import Qubit
from qibolab.pulses import Drag, Gaussian, Pulse, PulseSequence, PulseType, Rectangular
from qibolab.sweeper import Parameter, Sweeper
from qick import AveragerProgram, QickSoc, RAveragerProgram

# conversion coefficients (in qibolab we use Hz and ns)
HZ_TO_MHZ = 1e-6
NS_TO_US = 1e-3


class FluxProgram:  # TODO include and test
    @staticmethod
    # TODO use
    def from_volt_to_gain(volt: float, p0: int = 329, p1: int = 25634):
        return int(p0 + volt * p1)

    def set_bias(self, mode="sweetspot"):
        duration = 48  # minimum len
        self.sync_all()

        for idx in self.qubits:
            qubit = self.qubits[idx]
            if qubit.flux:
                ch = qubit.flux.ports[0][1]
                if mode == "sweetspot":
                    value = qubit.flux.bias
                elif mode == "zero":
                    value = 0
                else:
                    raise NotImplementedError(f"Mode {mode} not supported")
                i_wf = np.full(duration, value)
                q_wf = np.zeros(len(i_wf))
                self.add_pulse(ch, f"const_{value}_{idx}", i_wf, q_wf)

                print(f"Setting bias of ch {ch} to gain {self.max_flux_gain}")
                self.set_pulse_registers(
                    ch=ch,
                    waveform=f"const_{value}_{idx}",
                    style="arb",
                    outsel="input",
                    stdysel="last",
                    freq=0,
                    phase=0,
                    gain=self.max_flux_gain,
                )
                self.pulse(ch=ch)
        self.sync_all()

    def flux_pulse(self, pulse, time):
        qubit = self.qubits[pulse.qubit]
        gen_ch = qubit.flux.ports[0][1]
        sweetspot = qubit.flux.bias  # TODO convert units

        duration = self.soc.us2cycles(pulse.duration * NS_TO_US, gen_ch=gen_ch)
        samples_per_clk = self._gen_mgrs[gen_ch].samps_per_clk
        duration *= samples_per_clk

        padding = samples_per_clk
        while True:
            tot_len = padding + duration
            if tot_len % samples_per_clk == 0 and tot_len > 48:
                break
            else:
                padding += 1

        amp = int(pulse.amplitude * self.max_flux_gain) + sweetspot

        i = np.full(duration, amp)
        i = np.append(i, np.full(padding, sweetspot))
        q = np.zeros(len(i))

        self.add_pulse(gen_ch, pulse.serial, i, q)
        self.set_pulse_registers(
            ch=gen_ch,
            waveform=pulse.serial,
            style="arb",
            outsel="input",
            stdysel="last",
            freq=0,
            phase=0,
            gain=self.max_flux_gain,
        )
        self.pulse(ch=gen_ch, t=time)


class GeneralQickProgram(ABC):
    """Abstract class for QickPrograms"""

    def __init__(
        self, soc: QickSoc, qpcfg: QickProgramConfig, sequence: PulseSequence, qubits: List[Qubit], is_mux: bool = True
    ):
        """In this function we define the most important settings.

        In detail:
            * max_gain, adc_trig_offset, max_sampling_rate, reps are imported from
              qpcfg (runcard settings)
            * relaxdelay (for each execution) is taken from qpcfg (runcard)
            * syncdelay (for each measurement) is defined explicitly
            * wait_initialize is defined explicitly
            * super.__init__ (this will init AveragerProgram or RAveragerProgram)
        """
        # TODO is_mux should be in config
        self.is_mux = is_mux

        self.soc = soc
        self.soccfg = soc  # this is used by qick

        self.sequence = sequence
        self.qubits = qubits

        # general settings
        self.max_gain = qpcfg.max_gain
        self.max_flux_gain = 24000  # TODO not hardcode
        self.adc_trig_offset = qpcfg.adc_trig_offset
        self.max_sampling_rate = qpcfg.sampling_rate
        self.mixer_freq = qpcfg.mixer_freq
        self.LO_freq = qpcfg.LO_freq

        self.reps = qpcfg.reps

        self.relax_delay = self.us2cycles(qpcfg.repetition_duration * NS_TO_US)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        self.pulses_registered = False

        self.readouts_per_experiment = len(self.sequence.ro_pulses)
        if is_mux:
            self.multi_ro_pulses = {}
            for pulse in self.sequence.ro_pulses:
                if pulse.start not in self.multi_ro_pulses:
                    self.multi_ro_pulses[pulse.start] = []
                self.multi_ro_pulses[pulse.start].append(pulse)
            self.readouts_per_experiment = len(self.multi_ro_pulses)

        super().__init__(soc, asdict(qpcfg))

    def declare_nqz_zones(self, sequence: PulseSequence):
        """Declare nqz zone (1-2) for a given PulseSequence

        Args:
            sequence (PulseSequence): sequence of pulses to consider
        """

        ch_already_declared = []
        for pulse in sequence:
            freq = pulse.frequency
            if pulse.type is PulseType.DRIVE:
                ch = self.qubits[pulse.qubit].drive.ports[0][1]
                max_sampling_rate = self.max_sampling_rate
            elif pulse.type is PulseType.READOUT:
                ch = self.qubits[pulse.qubit].readout.ports[0][1]

            if pulse.type is PulseType.READOUT:
                freq = freq - self.mixer_freq - self.LO_freq
                max_sampling_rate = 1_536_000_000  # TODO this should be in config

            if ch not in ch_already_declared:
                ch_already_declared.append(ch)
                zone = 1 if freq < max_sampling_rate / 2 else 2
                self.declare_gen(ch, nqz=zone)

    def declare_gen_mux_ro(self):
        """
        Only one readout channel is supported
        """

        adc_ch_added = []
        mux_freqs = []
        mux_gains = []
        for pulse in self.sequence.ro_pulses:
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]

            if adc_ch not in adc_ch_added:
                adc_ch_added.append(adc_ch)
                # TODO add parameters to QickProgramConfig
                freq = pulse.frequency - self.mixer_freq - self.LO_freq
                max_sampling_rate = 1_536_000_000  # TODO this should be in config
                zone = 1 if freq < max_sampling_rate / 2 else 2
                freq = freq * HZ_TO_MHZ

                mux_gains.append(pulse.amplitude)
                mux_freqs.append(freq)

        print(f"declare gen {ro_ch} {zone} {self.mixer_freq} {mux_freqs} {mux_gains} {adc_ch_added[0]}")

        self.declare_gen(
            ch=ro_ch,
            nqz=zone,
            mixer_freq=self.mixer_freq,
            mux_freqs=mux_freqs,
            mux_gains=mux_gains,
            ro_ch=adc_ch_added[0],  # we use just one for dec
        )

    def declare_readout_freq(self):
        """Declare ADCs downconversion frequencies"""

        adc_ch_already_declared = []
        for readout_pulse in self.sequence.ro_pulses:
            adc_ch = self.qubits[readout_pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[readout_pulse.qubit].readout.ports[0][1]
            if adc_ch not in adc_ch_already_declared:
                adc_ch_already_declared.append(adc_ch)
                length = self.soc.us2cycles(readout_pulse.duration * NS_TO_US, ro_ch=adc_ch)

                freq = readout_pulse.frequency - self.mixer_freq - self.LO_freq
                freq = freq * HZ_TO_MHZ
                # in declare_readout frequency in MHz
                print(f"declare readout {adc_ch} {length} {freq} {ro_ch}")
                self.declare_readout(ch=adc_ch, length=length, freq=freq, gen_ch=ro_ch)

    def add_pulse_to_register(self, pulse: Pulse):
        """Calls the set_pulse_registers function, needed before firing a pulse

        Args:
            pulse (Pulse): pulse object to load in the register
        """

        # check if the pulse is sweeped
        is_sweeped = self.is_pulse_sweeped(pulse)

        # find channels relevant for this pulse
        qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
        adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
        ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
        gen_ch = qd_ch if pulse.type is PulseType.DRIVE else ro_ch

        # assign gain parameter
        gain_set = False
        if is_sweeped:
            if self.sweeper.parameter == Parameter.amplitude:
                gain = self.cfg["start"]
                gain_set = True
        if not gain_set:
            gain = int(pulse.amplitude * self.max_gain)

        # phase converted from rad (qibolab) to deg (qick) and then to reg vals
        phase = self.deg2reg(np.degrees(pulse.relative_phase), gen_ch=gen_ch)

        # pulse length converted with DAC CLK
        us_length = pulse.duration * NS_TO_US
        soc_length = self.soc.us2cycles(us_length, gen_ch=gen_ch)

        is_drag = isinstance(pulse.shape, Drag)
        is_gaus = isinstance(pulse.shape, Gaussian)
        is_rect = isinstance(pulse.shape, Rectangular)

        # pulse freq converted with frequency matching
        if pulse.type is PulseType.DRIVE:
            freq_set = False
            if is_sweeped:
                if self.sweeper.parameter == Parameter.frequency:
                    freq = self.cfg["start"]
                    freq_set = True
            if not freq_set:
                freq = self.soc.freq2reg(pulse.frequency * HZ_TO_MHZ, gen_ch=gen_ch)
        elif pulse.type is PulseType.READOUT:
            freq = self.soc.freq2reg(pulse.frequency * HZ_TO_MHZ, gen_ch=gen_ch, ro_ch=adc_ch)
        else:
            raise NotImplementedError(f"Pulse type {pulse.type} not supported!")

        # if pulse is drag or gauss first define the i-q shape and then set reg
        if is_drag or is_gaus:
            name = pulse.serial
            sigma = soc_length / pulse.shape.rel_sigma

            if is_gaus:
                self.add_gauss(ch=gen_ch, name=name, sigma=sigma, length=soc_length)

            elif is_drag:
                self.add_DRAG(
                    ch=gen_ch,
                    name=name,
                    sigma=sigma,
                    delta=1,
                    alpha=pulse.shape.beta,
                    length=soc_length,
                )

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
            raise NotImplementedError(f"Shape {pulse.shape} not supported!")

    def add_muxed_readout_to_register(self, ro_pulses: List[Pulse]):
        mask = [0, 1, 2]  # TODO now hardcoded

        pulse = ro_pulses[0]
        gen_ch = self.qubits[pulse.qubit].readout.ports[0][1]

        us_length = pulse.duration * NS_TO_US
        soc_length = self.soc.us2cycles(us_length, gen_ch=gen_ch)

        if not isinstance(pulse.shape, Rectangular):
            raise Exception("Only Rectangular ro pulses are supported")

        print(f"set pulse register {gen_ch} {soc_length} {mask}")
        self.set_pulse_registers(ch=gen_ch, style="const", length=soc_length, mask=mask)

    def body(self):
        """Execute sequence of pulses.

        For each pulses calls the add_pulse_to_register function (if not already registered)
        before firing it. If the pulse is a readout, it does a measurement and does
        not wait for the end of it. At the end of the sequence wait for meas and clock.
        """

        muxed_ro_executed_pulses_time = []

        for pulse in self.sequence:
            # time follows tproc CLK
            time = self.soc.us2cycles(pulse.start * NS_TO_US)

            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type is PulseType.DRIVE else ro_ch

            if pulse.type is PulseType.DRIVE:
                if not self.pulses_registered:
                    self.add_pulse_to_register(pulse)
                self.pulse(ch=gen_ch, t=time)
            elif pulse.type is PulseType.READOUT:
                if self.is_mux:
                    if pulse.start not in muxed_ro_executed_pulses_time:
                        self.add_muxed_readout_to_register(self.multi_ro_pulses[pulse.start])
                        muxed_ro_executed_pulses_time.append(pulse.start)
                        adcs = []
                        for ro_pulse in self.multi_ro_pulses[pulse.start]:
                            adcs.append(self.qubits[ro_pulse.qubit].feedback.ports[0][1])

                        print(f"measure {ro_ch} {adcs} {time} {self.adc_trig_offset} {self.syncdelay}")
                        self.measure(
                            pulse_ch=ro_ch,
                            adcs=adcs,
                            adc_trig_offset=time + self.adc_trig_offset,
                            t=time,
                            wait=True,  # False,
                            syncdelay=200,  # self.syncdelay,
                        )
                else:
                    if not self.pulses_registered:
                        self.add_pulse_to_register(pulse)
                    adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
                    self.measure(
                        pulse_ch=ro_ch,
                        adcs=[adc_ch],
                        adc_trig_offset=time + self.adc_trig_offset,
                        t=time,
                        wait=False,
                        syncdelay=self.syncdelay,
                    )
        self.wait_all()
        self.sync_all(self.relax_delay)

    def acquire(
        self,
        soc: QickSoc,
        load_pulses: bool = True,
        progress: bool = False,
        debug: bool = False,
        average: bool = False,
    ) -> Tuple[List[float], List[float]]:
        """Calls the super() acquire function.

        Args:
            readouts_per_experiment (int): relevant for internal acquisition
            load_pulse, progress, debug (bool): internal Qick parameters
            progress (bool): if true shows a progress bar, slows down things
            debug (bool): if true prints the program actually executed
            average (bool): if true return averaged res, otherwise single shots
        """
        res = super().acquire(
            soc,
            readouts_per_experiment=self.readouts_per_experiment,
            load_pulses=load_pulses,
            progress=progress,
            debug=debug,
        )
        if average:
            # for sequences res has 3 parameters, the first is not used
            return res[-2:]
        # super().acquire function fill buffers used in collect_shots
        return self.collect_shots()[-2:]

    def collect_shots(self) -> Tuple[List[float], List[float]]:
        """Reads the internal buffers and returns single shots (i,q)"""

        tot_i = []
        tot_q = []

        adcs = []  # list of adcs per readouts (not unique values)
        lengths = []  # length of readouts (only one per adcs)
        for pulse in self.sequence.ro_pulses:
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            if adc_ch not in adcs:
                lengths.append(self.soc.us2cycles(pulse.duration * NS_TO_US, gen_ch=ro_ch))
            adcs.append(adc_ch)

        adcs, adc_count = np.unique(adcs, return_counts=True)

        for idx, adc_ch in enumerate(adcs):
            count = adc_count[adc_ch]
            if self.expts:  # self.expts is None if this is not a sweep
                shape = (count, self.expts, self.reps)
            else:
                shape = (count, self.reps)
            i_val = self.di_buf[idx].reshape(shape) / lengths[idx]
            q_val = self.dq_buf[idx].reshape(shape) / lengths[idx]

            tot_i.append(i_val)
            tot_q.append(q_val)
        return tot_i, tot_q

    @abstractmethod
    def initialize(self):
        raise NotImplementedError

    @abstractmethod
    def is_pulse_sweeped(self, pulse: Pulse) -> bool:
        raise NotImplementedError


class ExecutePulseSequence(GeneralQickProgram, AveragerProgram):
    """Class to execute arbitrary PulseSequences"""

    def initialize(self):
        """Function called by AveragerProgram.__init__"""

        self.declare_nqz_zones(self.sequence.qd_pulses)
        if self.is_mux:
            self.declare_gen_mux_ro()
        else:
            self.declare_nqz_zones(self.sequence.ro_pulses)

        self.declare_readout_freq()
        self.sync_all(self.wait_initialize)

    def is_pulse_sweeped(self, pulse: Pulse) -> bool:
        """ExecutePulseSequence does not have sweeps so always returns False"""
        return False


class ExecuteSingleSweep(GeneralQickProgram, RAveragerProgram):
    """Class to execute arbitrary PulseSequences with a single sweep"""

    def __init__(
        self, soc: QickSoc, qpcfg: QickProgramConfig, sequence: PulseSequence, qubits: List[Qubit], sweeper: Sweeper
    ):
        """Init function, sets sweepers parameters before calling super.__init__"""

        # sweeper Settings
        self.sweeper = sweeper
        self.sweeper_reg = None
        self.sweeper_page = None
        qpcfg.expts = len(sweeper.values)

        super().__init__(soc, qpcfg, sequence, qubits)

    def add_sweep_info(self):
        """Find the page and register of the sweeped values, sets start and step"""

        pulse = self.sweeper.pulses[0]
        qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
        ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
        gen_ch = qd_ch if pulse.type is PulseType.DRIVE else ro_ch

        # find page of sweeper pulse channel
        self.sweeper_page = self.ch_page(gen_ch)

        # define start and step values
        start = self.sweeper.values[0]
        step = self.sweeper.values[1] - self.sweeper.values[0]

        # find register of sweeped parameter and assign start and step
        if self.sweeper.parameter == Parameter.frequency:
            self.sweeper_reg = self.sreg(gen_ch, "freq")
            self.cfg["start"] = self.soc.freq2reg(start * HZ_TO_MHZ, gen_ch)
            self.cfg["step"] = self.soc.freq2reg(step * HZ_TO_MHZ, gen_ch)

        elif self.sweeper.parameter == Parameter.amplitude:
            self.sweeper_reg = self.sreg(gen_ch, "gain")
            self.cfg["start"] = int(start * self.max_gain)
            self.cfg["step"] = int(step * self.max_gain)

            if self.cfg["start"] + self.cfg["step"] * self.cfg["expts"] > self.max_gain:
                raise ValueError("Amplitude higher than maximum!")

    def initialize(self):
        """Function called by RAveragerProgram.__init__"""

        self.add_sweep_info()

        self.declare_nqz_zones(self.sequence.qd_pulses)
        if self.is_mux:
            self.declare_gen_mux_ro()
        else:
            self.declare_nqz_zones(self.sequence.ro_pulses)

        self.declare_readout_freq()

        self.pulses_registered = True
        for pulse in self.sequence:
            self.add_pulse_to_register(pulse)

        self.sync_all(self.wait_initialize)

    def is_pulse_sweeped(self, pulse: Pulse) -> bool:
        """Check if a pulse is sweeped

        Args:
            pulse (Pulse): pulse to check
        Returns:
            (bool): True if the pulse is sweeped
        """
        return self.sweeper.pulses[0] == pulse

    def update(self):
        """Update function for sweeper"""
        self.mathi(self.sweeper_page, self.sweeper_reg, self.sweeper_reg, "+", self.cfg["step"])
