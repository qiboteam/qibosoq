"""Base program used by qibosoq to execute sequences and sweeps."""

import logging
from abc import abstractmethod
from dataclasses import asdict
from typing import Dict, List, Tuple, Union

import numpy as np
from qick import QickProgram, QickSoc

import qibosoq.configuration as qibosoq_cfg
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import (
    Arbitrary,
    Drag,
    Element,
    FlatTop,
    Gaussian,
    Hann,
    Measurement,
    Pulse,
    Rectangular,
)

logger = logging.getLogger(qibosoq_cfg.MAIN_LOGGER_NAME)


class BaseProgram(QickProgram):
    """Abstract class for QickPrograms."""

    def __init__(
        self, soc: QickSoc, qpcfg: Config, sequence: List[Element], qubits: List[Qubit]
    ):
        """In this function we define the most important settings.

        In detail:
            * max_gain, ro_time_of_flight, max_sampling_rate, reps are imported from
              qpcfg (runcard settings)
            * relaxdelay (for each execution) is taken from qpcfg (runcard)
            * syncdelay (for each measurement) is defined explicitly
            * wait_initialize is defined explicitly
            * super.__init__ (this will init AveragerProgram or RAveragerProgram)
        """
        self.soc = soc
        self.soccfg = soc  # this is used by qick

        self.sequence = sequence
        self.pulse_sequence = [elem for elem in sequence if isinstance(elem, Pulse)]
        self.qubits = qubits

        # general settings
        self.ro_time_of_flight = qpcfg.ro_time_of_flight

        # mux settings
        self.is_mux = qibosoq_cfg.IS_MULTIPLEXED
        self.readouts_per_experiment = len(
            [elem for elem in self.sequence if elem.type == "readout"]
        )

        # Convert delays into generic clock cycles
        self.relax_delay = self.us2cycles(qpcfg.relaxation_time)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        self.pulses_registered = False
        self.registered_waveforms: Dict[int, list] = {}
        for pulse in self.pulse_sequence:
            if pulse.dac not in self.registered_waveforms:
                self.registered_waveforms[pulse.dac] = []

        if self.is_mux:
            self.multi_ro_pulses = self.group_mux_ro()
            self.readouts_per_experiment = len(self.multi_ro_pulses)

        # pylint: disable-next=too-many-function-args
        super().__init__(soc, asdict(qpcfg))

    def declare_nqz_zones(self, pulse_sequence: List[Pulse]):
        """Declare nqz zone (1-2) for a given PulseSequence.

        Args:
            pulse_sequence (PulseSequence): pulse_sequence of pulses to consider
        """
        ch_already_declared = []
        for pulse in pulse_sequence:
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
        for readout in (elem for elem in self.sequence if elem.type == "readout"):
            adc_ch = readout.adc
            ro_ch = readout.dac
            if adc_ch not in adc_ch_already_declared:
                adc_ch_already_declared.append(adc_ch)
                # Convert acquisition length into ADC clock cycles
                length = self.soc.us2cycles(readout.duration, ro_ch=adc_ch)

                freq = readout.frequency

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
        # Convert pulse length into DAC clock cycles
        soc_length = self.soc.us2cycles(us_length, gen_ch=gen_ch)

        name = pulse.waveform_name

        if name is not None and name not in self.registered_waveforms[gen_ch]:
            if isinstance(pulse, Gaussian):
                sigma = (soc_length / pulse.rel_sigma) * np.sqrt(2)
                self.add_gauss(ch=gen_ch, name=name, sigma=sigma, length=soc_length)
            elif isinstance(pulse, FlatTop):
                soc_length /= 2  # required for unknown reasons
                sigma = (soc_length / pulse.rel_sigma) * np.sqrt(2)
                self.add_gauss(ch=gen_ch, name=name, sigma=sigma, length=soc_length)
            elif isinstance(pulse, Drag):
                delta = (
                    -self.soccfg["gens"][gen_ch]["samps_per_clk"]
                    * self.soccfg["gens"][gen_ch]["f_fabric"]
                    / 2
                )
                sigma = (soc_length / pulse.rel_sigma) * np.sqrt(2)
                self.add_DRAG(
                    ch=gen_ch,
                    name=name,
                    sigma=sigma,
                    delta=delta,
                    alpha=pulse.beta,
                    length=soc_length,
                )

            elif isinstance(pulse, Hann):
                self.add_pulse(gen_ch, name, pulse.i_values(soc_length, max_gain))
            elif isinstance(pulse, Arbitrary):
                self.add_pulse(gen_ch, name, pulse.i_values, pulse.q_values)
            self.registered_waveforms[gen_ch].append(name)

        args = {"waveform": name} if name is not None else {}
        if isinstance(pulse, (Rectangular, FlatTop)):
            args["length"] = soc_length

        self.set_pulse_registers(
            ch=gen_ch,
            style=pulse.style,
            freq=freq,
            phase=phase,
            gain=gain,
            **args,
        )

    def execute_drive_pulse(self, pulse: Pulse, last_pulse_registered: Dict):
        """Register a drive pulse if needed, then trigger the respective DAC.

        A pulse gets register if:
        - it didn't happen in `initialize` (`self.pulses_registered` is False)
        - it is not identical to the last pulse registered

        """
        if not self.pulses_registered and (
            pulse.dac not in last_pulse_registered
            or pulse != last_pulse_registered[pulse.dac]
        ):
            self.add_pulse_to_register(pulse)
            last_pulse_registered[pulse.dac] = pulse

        self.pulse(ch=pulse.dac, t="auto")

    def execute_readout_pulse(
        self,
        elem: Element,
        muxed_pulses_executed: List[Element],
        muxed_ro_executed_indexes: List[int],
    ):
        """Register a readout pulse and perform a measurement."""
        adcs = []
        if self.is_mux:
            if elem in muxed_pulses_executed:
                return

            idx_mux = next(
                idx
                for idx, mux_time in enumerate(self.multi_ro_pulses)
                if elem in mux_time
            )
            self.add_muxed_readout_to_register(self.multi_ro_pulses[idx_mux])
            muxed_ro_executed_indexes.append(idx_mux)
            for ro_pulse in self.multi_ro_pulses[idx_mux]:
                adcs.append(ro_pulse.adc)
                muxed_pulses_executed.append(ro_pulse)
        else:
            if not self.pulses_registered and isinstance(elem, Pulse):
                self.add_pulse_to_register(elem)
            adcs = [elem.adc]

        if isinstance(elem, Pulse):  #
            self.measure(
                pulse_ch=elem.dac,
                adcs=adcs,
                adc_trig_offset=self.ro_time_of_flight,
                wait=False,
                syncdelay=self.syncdelay,
            )
        elif isinstance(elem, Measurement):
            self.trigger(adcs, adc_trig_offset=self.ro_time_of_flight)
            if self.syncdelay is not None:
                self.sync_all(self.syncdelay)

    def perform_experiment(
        self,
        soc: QickSoc,
        average: bool = False,
    ) -> Tuple[list, list]:
        """Call the acquire function, executing the experiment.

        The acquire function is coded in `qick.AveragerProgram` or `qick.NDAveragerProgram`

        Args:
            average (bool): if true return averaged res, otherwise single shots
        """
        readouts_per_experiment = self.readouts_per_experiment
        # if there are no readouts, temporaray set 1 so that qick can execute properly
        reads_per_rep = 1 if readouts_per_experiment == 0 else readouts_per_experiment

        res = self.acquire(  # pylint: disable=E1123,E1120
            soc,
            readouts_per_experiment=reads_per_rep,
        )
        # if there are no actual readouts, return empty lists
        if readouts_per_experiment == 0:
            return [], []
        if average:
            # for sweeps res has 3 parameters, the first is not used
            return np.array(res[-2]).tolist(), np.array(res[-1]).tolist()
        # super().acquire function fill buffers used in collect_shots
        return self.collect_shots()[-2:]

    def collect_shots(self) -> Tuple[list, list]:
        """Read the internal buffers and returns single shots (i,q)."""
        adcs = []  # list of adcs per readouts (not unique values)
        lengths = []  # length of readouts (only one per adcs)
        for elem in (elem for elem in self.sequence if elem.type == "readout"):
            adc_ch = elem.adc
            ro_ch = elem.dac
            if adc_ch not in adcs:
                # Convert acquisition length into ADC clock cycles
                lengths.append(self.soc.us2cycles(elem.duration, ro_ch=adc_ch))
            adcs.append(adc_ch)

        _, adc_count = np.unique(adcs, return_counts=True)
        tot = []

        for idx, count in enumerate(adc_count.astype(int)):
            try:
                # if we are doing sweepers
                # (adc_channels, number_of_readouts, number_of_points, number_of_shots)
                shape = (
                    2,
                    count,
                    int(np.prod(self.sweep_axes)),
                    self.reps,
                )  # type: Union[Tuple[int, int, int], Tuple[int, int, int, int]]
            except AttributeError:
                # if we are not doing sweepers
                # (adc_channels, number_of_readouts, number_of_shots)
                shape = (2, count, self.reps)

            stacked = (
                np.stack((self.di_buf[idx], self.dq_buf[idx]))[:, : np.prod(shape[1:])]
                / np.array(lengths)[:, np.newaxis]
            )

            tot.append(stacked.reshape(shape).tolist())

        return tuple(list(x) for x in zip(*tot))  # type: ignore

    def declare_gen_mux_ro(self):
        """Declare nqz zone for multiplexed readout."""
        adc_ch_added = []

        mux_freqs = []
        mux_gains = []

        ro_ch = None
        zone = 1
        for pulse in (pulse for pulse in self.sequence if pulse.type == "readout"):
            if not isinstance(pulse, Pulse):
                continue
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

    def add_muxed_readout_to_register(self, ro_pulses: List[Rectangular]):
        """Register multiplexed pulse before firing it."""
        # readout amplitude gets divided by len(mask), we are here fixing the values
        mask = [0, 1, 2]

        pulse = ro_pulses[0]
        gen_ch = pulse.dac
        # Convert pulse length into DAC clock cycles
        length = self.soc.us2cycles(pulse.duration, gen_ch=gen_ch)

        if pulse.shape != "rectangular":
            raise TypeError("Only rectangular pulses can be multiplexed")

        self.set_pulse_registers(ch=gen_ch, style="const", length=length, mask=mask)

    def group_mux_ro(self) -> list:
        """Create a list containing readout pulses grouped by start time.

        Example of list:
        [[pulse1, pulse2], [pulse3]]
        """
        mux_list: List[List[Element]] = []
        len_last_readout = 0.0
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
