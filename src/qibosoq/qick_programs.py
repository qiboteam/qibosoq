""" QickPrograms used by qibosoq to execute sequences and sweeps """

from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import List, Tuple

import numpy as np
from qibolab.instruments.rfsoc import QickProgramConfig
from qibolab.platforms.abstract import Qubit
from qibolab.pulses import Drag, Gaussian, Pulse, PulseSequence, PulseType, Rectangular
from qibolab.sweeper import Parameter, Sweeper
from qick import AveragerProgram, QickProgram, QickSoc, RAveragerProgram

# conversion coefficients (in qibolab we use Hz and ns)
HZ_TO_MHZ = 1e-6
NS_TO_US = 1e-3


class GeneralQickProgram(ABC, QickProgram):
    """Abstract class for QickPrograms"""

    def __init__(self, soc: QickSoc, qpcfg: QickProgramConfig, sequence: PulseSequence, qubits: List[Qubit]):
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
        self.max_gain = qpcfg.max_gain
        self.adc_trig_offset = qpcfg.adc_trig_offset
        self.max_sampling_rate = qpcfg.sampling_rate
        self.reps = qpcfg.reps

        self.relax_delay = self.us2cycles(qpcfg.repetition_duration * NS_TO_US)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        self.pulses_registered = False

        # pylint: disable-next=too-many-function-args
        super().__init__(soc, asdict(qpcfg))

    def declare_nqz_zones(self, sequence: PulseSequence):
        """Declare nqz zone (1-2) for a given PulseSequence

        Args:
            sequence (PulseSequence): sequence of pulses to consider
        """

        ch_already_declared = []
        for pulse in sequence:
            if pulse.type is PulseType.DRIVE:
                gen_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            elif pulse.type is PulseType.READOUT:
                gen_ch = self.qubits[pulse.qubit].readout.ports[0][1]

            freq = pulse.frequency

            if gen_ch not in ch_already_declared:
                ch_already_declared.append(gen_ch)
                zone = 1 if freq < self.max_sampling_rate / 2 else 2
                self.declare_gen(gen_ch, nqz=zone)

    def declare_readout_freq(self):
        """Declare ADCs downconversion frequencies"""

        adc_ch_already_declared = []
        for readout_pulse in self.sequence.ro_pulses:
            adc_ch = self.qubits[readout_pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[readout_pulse.qubit].readout.ports[0][1]
            if adc_ch not in adc_ch_already_declared:
                adc_ch_already_declared.append(adc_ch)
                length = self.soc.us2cycles(readout_pulse.duration * NS_TO_US, gen_ch=ro_ch)

                freq = readout_pulse.frequency * HZ_TO_MHZ

                # in declare_readout frequency in MHz
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
            sigma = (soc_length / pulse.shape.rel_sigma) * np.sqrt(2)

            if is_gaus:
                self.add_gauss(ch=gen_ch, name=name, sigma=sigma, length=soc_length)

            elif is_drag:
                # delta will be divided for the same quantity, we are setting it = 1
                delta = self.soccfg["gens"][gen_ch]["samps_per_clk"] * self.soccfg["gens"][gen_ch]["f_fabric"]

                self.add_DRAG(
                    ch=gen_ch,
                    name=name,
                    sigma=sigma,
                    delta=delta,
                    alpha=-pulse.shape.beta,
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

    def body(self):
        """Execute sequence of pulses.

        For each pulses calls the add_pulse_to_register function (if not already registered)
        before firing it. If the pulse is a readout, it does a measurement and does
        not wait for the end of it. At the end of the sequence wait for meas and clock.
        """

        last_pulse_registered = {}
        for idx in self.gen_chs:
            last_pulse_registered[idx] = None

        for pulse in self.sequence:
            # time follows tproc CLK
            time = self.soc.us2cycles(pulse.start * NS_TO_US)

            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type is PulseType.DRIVE else ro_ch

            if not self.pulses_registered:
                if not self.is_pulse_equal(last_pulse_registered[gen_ch], pulse):
                    self.add_pulse_to_register(pulse)
                    last_pulse_registered[gen_ch] = pulse

            if pulse.type is PulseType.DRIVE:
                self.pulse(ch=gen_ch, t=time)
            elif pulse.type is PulseType.READOUT:
                self.measure(
                    pulse_ch=gen_ch,
                    adcs=[adc_ch],
                    adc_trig_offset=time + self.adc_trig_offset,
                    t=time,
                    wait=False,
                    syncdelay=self.syncdelay,
                )
        self.wait_all()
        self.sync_all(self.relax_delay)

    def is_pulse_equal(self, pulse_a: Pulse, pulse_b: Pulse) -> bool:
        """Check if two pulses are equal, does not check the start time"""
        if pulse_a is None:
            return False
        return (
            pulse_a.frequency == pulse_b.frequency
            and pulse_a.amplitude == pulse_b.amplitude
            and pulse_a.shape == pulse_b.shape
            and pulse_a.relative_phase == pulse_b.relative_phase
            and pulse_a.duration == pulse_b.duration
            and pulse_a.type == pulse_b.type
        )

    def acquire(
        self,
        soc: QickSoc,
        readouts_per_experiment: int = 1,
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

        # if there are no readouts, temporaray set 1 so that qick can execute properly
        reads_per_rep = 1 if readouts_per_experiment == 0 else readouts_per_experiment

        # pylint: disable-next=unexpected-keyword-arg, arguments-renamed
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
        """Abstract initialization"""
        raise NotImplementedError

    @abstractmethod
    def is_pulse_sweeped(self, pulse: Pulse) -> bool:
        """Given a pulse, returns if it is sweeped"""
        raise NotImplementedError


class ExecutePulseSequence(GeneralQickProgram, AveragerProgram):
    """Class to execute arbitrary PulseSequences"""

    def initialize(self):
        """Function called by AveragerProgram.__init__"""

        self.declare_nqz_zones(self.sequence)
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
        self.declare_nqz_zones(self.sequence)
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
