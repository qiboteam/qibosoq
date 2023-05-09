""" QickPrograms used by qibosoq to execute sequences and sweeps """

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import List, Tuple

import numpy as np
from qibolab.instruments.rfsoc import QickProgramConfig
from qibolab.platforms.abstract import Qubit
from qibolab.pulses import Drag, Gaussian, Pulse, PulseSequence, PulseType, Rectangular
from qibolab.sweeper import Parameter, Sweeper
from qick import AveragerProgram, NDAveragerProgram, QickProgram, QickSoc
from qick.averager_program import QickSweep, merge_sweeps

logger = logging.getLogger("__name__")


# conversion coefficients (in qibolab we use Hz and ns)
HZ_TO_MHZ = 1e-6
NS_TO_US = 1e-3

MUX_SAMPLING_FREQ = 1_536_000_000  # TODO


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
        self.lo_frequency = qpcfg.LO_freq
        self.reps = qpcfg.reps

        # mux settings
        self.mux_sampling_frequency = MUX_SAMPLING_FREQ  # TODO qpcfg.mux_sampling_frequency
        self.is_mux = self.mux_sampling_frequency is not None
        self.readouts_per_experiment = None  # TODO this should be defined for acquire

        self.relax_delay = self.us2cycles(qpcfg.repetition_duration * NS_TO_US)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        self.pulses_registered = False

        if self.is_mux:
            self.multi_ro_pulses = self.create_mux_ro_dict()

        # pylint: disable-next=too-many-function-args
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
                gen_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            elif pulse.type is PulseType.READOUT:
                gen_ch = self.qubits[pulse.qubit].readout.ports[0][1]
                freq = freq - self.lo_frequency

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

                freq = (readout_pulse.frequency - self.lo_frequency) * HZ_TO_MHZ

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
                gain = self.get_start_sweep(pulse)
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
                    freq = self.get_start_sweep(pulse)
                    freq_set = True
            if not freq_set:
                freq = self.soc.freq2reg(pulse.frequency * HZ_TO_MHZ, gen_ch=gen_ch)
        elif pulse.type is PulseType.READOUT:
            freq = pulse.frequency - self.lo_frequency
            freq = self.soc.freq2reg(freq * HZ_TO_MHZ, gen_ch=gen_ch, ro_ch=adc_ch)
        else:
            raise NotImplementedError(f"Pulse type {pulse.type} not supported!")

        # if pulse is drag or gauss first define the i-q shape and then set reg
        if is_drag or is_gaus:
            name = pulse.serial
            sigma = (soc_length / pulse.shape.rel_sigma) * np.sqrt(2)

            if is_gaus:
                self.add_gauss(ch=gen_ch, name=name, sigma=sigma, length=soc_length)

            elif is_drag:
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

        muxed_ro_executed_time = []

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
                    if pulse.start not in muxed_ro_executed_time:
                        self.add_muxed_readout_to_register(self.multi_ro_pulses[pulse.start])
                        muxed_ro_executed_time.append(pulse.start)
                        adcs = [
                            self.qubits[ro_pulse.qubit].feedback.ports[0][1]
                            for ro_pulse in self.multi_ro_pulses[pulse.start]
                        ]
                else:
                    if not self.pulses_registered:
                        self.add_pulse_to_register(pulse)
                    adcs = [adc_ch]

                self.measure(
                    pulse_ch=gen_ch,
                    adcs=adcs,
                    adc_trig_offset=time + self.adc_trig_offset,
                    t=time,
                    wait=False,  # TODO maybe true for mux
                    syncdelay=self.syncdelay,  # maybe != 0 for mux
                )
        self.wait_all()
        self.sync_all(self.relax_delay)

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
        # pylint: disable=unexpected-keyword-arg, arguments-renamed
        if readouts_per_experiment == 0:
            readouts_per_experiment = 1
        if self.readouts_per_experiment:
            readouts_per_experiment = self.readouts_per_experiment
        res = super().acquire(
            soc,
            readouts_per_experiment=readouts_per_experiment,
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

    def declare_gen_mux_ro(self):
        """Declare nqz zone for multiplexed readout"""

        adc_ch_added = []

        mux_freqs = []
        mux_gains = []

        for pulse in self.sequence.ro_pulses:
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]

            if adc_ch not in adc_ch_added:
                adc_ch_added.append(adc_ch)
                freq = (pulse.frequency - self.lo_frequency) * HZ_TO_MHZ
                zone = 1 if freq < self.mux_sampling_frequency / 2 else 2
                mux_freqs.append(freq)
                mux_gains.append(pulse.amplitude)
        self.declare_gen(
            ch=ro_ch,
            nqz=zone,
            mixer_freq=0,  # TODO is this value completly useless?
            mux_freqs=mux_freqs,
            mux_gains=mux_gains,
            ro_ch=adc_ch_added[0],
        )

    def add_muxed_readout_to_register(self, ro_pulses: List[Pulse]):
        """Register multiplexed pulse before firing it"""

        mask = [0, 1, 2]  # TODO remove hardcode

        pulse = ro_pulses[0]
        gen_ch = self.qubits[pulse.qubit].readout.ports[0][1]
        length = self.soc.us2cycles(pulse.duration * NS_TO_US, gen_ch=gen_ch)

        if not isinstance(pulse.shape, Rectangular):
            raise TypeError("Only rectangular pulses can be multiplexed")

        self.set_pulse_registers(ch=gen_ch, style="const", length=length, mask=mask)

    def create_mux_ro_dict(self) -> dict:
        """Creates a dictionary containing grouped readout pulses

        Example of dictionary:
        { 'start_time_0': [pulse1, pulse2],
          'start_time_1': [pulse3]}
        """

        mux_dict = {}
        for pulse in self.sequence.ro_pulses:
            if pulse.start not in mux_dict:
                mux_dict[pulse.start] = []
            mux_dict[pulse.start].append(pulse)
        self.readouts_per_experiment = len(mux_dict)
        return mux_dict

    @abstractmethod
    def initialize(self):
        """Abstract initialization"""
        raise NotImplementedError

    @abstractmethod
    def is_pulse_sweeped(self, pulse: Pulse) -> bool:
        """Given a pulse, returns if it is sweeped"""
        raise NotImplementedError

    @abstractmethod
    def get_start_sweep(self, sweeped_pulse: Pulse) -> Union[int, float]:
        raise NotImplementedError


class FluxProgram(GeneralQickProgram):
    """Abstract class for flux-tunable qubits programs"""

    def set_bias(self, mode: str = "sweetspot"):
        """Set qubits flux lines to a bias level

        Note that this fuction acts only on the qubits used in self.sequence.
        Args:
            mode (str): can be 'sweetspot' or 'zero'
        """

        duration = 48  # minimum len

        for idx in self.qubits:
            qubit = self.qubits[idx]
            if qubit.flux and idx in self.sequence.qubits:
                ch = qubit.flux.ports[0][1]

                if qubit.flux.bias == 0:
                    continue  # if bias is zero, just skip the qubit
                if mode == "sweetspot":
                    value = int(qubit.flux.bias * self.max_gain)
                elif mode == "zero":
                    value = 0
                else:
                    raise NotImplementedError(f"Mode {mode} not supported")

                logger.debug("Setting bias value of %d at %f", idx, value)

                i_wf = np.full(duration, value)
                q_wf = np.zeros(len(i_wf))
                self.add_pulse(ch, f"const_{value}_{ch}", i_wf, q_wf)
                self.set_pulse_registers(
                    ch=ch,
                    waveform=f"const_{value}_{ch}",
                    style="arb",
                    outsel="input",
                    stdysel="last",
                    freq=0,
                    phase=0,
                    gain=self.max_gain,
                )
                self.pulse(ch=ch)
        self.sync_all(50)  # wait all pulses are fired + 50 clks

    def flux_pulse(self, pulse: Pulse, time: int):
        """Fires a fast flux pulse the starts and ends in sweetspot"""

        logger.warning("The flux_pulse method has not been tested properly")

        qubit = self.qubits[pulse.qubit]
        gen_ch = qubit.flux.ports[0][1]
        sweetspot = int(qubit.flux.bias * self.max_gain)

        duration = self.soc.us2cycles(pulse.duration * NS_TO_US, gen_ch=gen_ch)
        samples_per_clk = self._gen_mgrs[gen_ch].samps_per_clk
        duration *= samples_per_clk  # the duration here is expressed in samples

        padding = samples_per_clk
        while True:  # compute padding length
            tot_len = padding + duration
            if tot_len % samples_per_clk == 0 and tot_len > 48:
                break
            else:
                padding += 1

        amp = int(pulse.amplitude * self.max_gain) + sweetspot

        i = np.full(duration, amp)
        i = np.append(i, np.full(padding, sweetspot))
        q = np.zeros(len(i))

        logger.debug("Flux pulse at ch %d, amp %d, len %d, padding %d", gen_ch, amp, len(i), padding)

        self.add_pulse(gen_ch, pulse.serial, i, q)
        self.set_pulse_registers(
            ch=gen_ch,
            waveform=pulse.serial,
            style="arb",
            outsel="input",
            stdysel="last",
            freq=0,
            phase=0,
            gain=self.max_gain,
        )
        self.pulse(ch=gen_ch, t=time)

    def body(self):
        """Body program with flux biases set"""

        self.set_bias("sweetspot")
        super().body()
        self.set_bias("zero")
        self.soc.reset_gens()  # here for security reasons, should not be needed


class ExecutePulseSequence(FluxProgram, AveragerProgram):
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


class ExecuteSingleSweep(FluxProgram, NDAveragerProgram):
    """Class to execute arbitrary PulseSequences with a single sweep"""

    def __init__(
        self, soc: QickSoc, qpcfg: QickProgramConfig, sequence: PulseSequence, qubits: List[Qubit], sweeper: Sweeper
    ):
        """Init function, sets sweepers parameters before calling super.__init__"""

        # sweeper Settings
        self.sweepers = [sweeper]  # TODO make it accept multiple sweepers
        # qpcfg.expts = sweeper.expts  TODO remove

        super().__init__(soc, qpcfg, sequence, qubits)

    def add_sweep_info(self, sweeper: Sweeper):
        sweep_list = []
        for idx, pulse in enumerate(sweeper.pulses):
            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type is PulseType.DRIVE else ro_ch

            sweep_type = SWEEPERS_TYPE[sweeper.parameter]
            self.register = self.get_gen_reg(gen_ch, sweep_type)

            # TODO check conversion coefficients
            if sweeper.parameter is Parameter.frequency:
                starts = sweeper.starts * HZ_TO_MHZ
                steps = sweeper.steps * HZ_TO_MHZ
            elif sweeper.parameter is Parameter.amplitude:
                starts = int(sweeper.starts * self.max_gain)
                steps = int(sweeper.steps * self.max_gain)
            else:
                raise NotImplementedError("Sweep type conversion not implemented")
            new_sweep = QickSweep(
                self,
                self.register,
                sweeper.starts[idx],
                sweeper.starts[idx] + sweeper.expts * sweeper.steps[idx],
                sweeper.expts,
            )
            sweep_list.append(new_sweep)

        self.add_sweep(merge_sweeps(sweep_list))

    def initialize(self):
        """Function called by RAveragerProgram.__init__"""

        self.declare_nqz_zones(self.sequence.qd_pulses)
        if self.is_mux:
            self.declare_gen_mux_ro()
        else:
            self.declare_nqz_zones(self.sequence.ro_pulses)
        self.declare_readout_freq()

        self.pulses_registered = True
        for pulse in self.sequence:
            self.add_pulse_to_register(pulse)

        for sweeper in self.sweepers:
            self.add_sweep_info(sweeper)

        self.sync_all(self.wait_initialize)

    def is_pulse_sweeped(self, pulse: Pulse) -> bool:
        """Check if a pulse is sweeped

        Args:
            pulse (Pulse): pulse to check
        Returns:
            (bool): True if the pulse is sweeped
        """
        for sweep in self.sweepers:
            # this is valid only for pulse sweeps, not bias
            for idx, pulse in enumerate(sweep.pulses):
                if pulse == sweeped_pulse:
                    return True
        return False

    def get_start_sweep(self, sweeped_pulse: Pulse) -> Union[int, float]:
        for sweep in self.sweepers:
            # this is valid only for pulse sweeps, not bias
            for idx, pulse in enumerate(sweep.pulses):
                if pulse == sweeped_pulse:
                    return sweep.starts[idx]


SWEEPERS_TYPE = {
    Parameter.frequency: "freq",
    Parameter.amplitude: "gain",
    Parameter.relative_phase: "phase",
}
