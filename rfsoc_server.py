""" RFSoC FPGA driver.
This driver needs the library Qick installed
Supports the following FPGA:
 *   RFSoC 4x2
"""

import math
import pickle
import signal
import socket
import sys
from socketserver import BaseRequestHandler, TCPServer
from typing import List, Tuple

import numpy as np
from qibolab.platforms.abstract import Qubit
from qibolab.pulses import Drag, Gaussian, Pulse, PulseSequence, PulseType, Rectangular
from qibolab.sweeper import Parameter, Sweeper
from qick import AveragerProgram, QickSoc, RAveragerProgram


def signal_handler(sig, frame):
    """Signal handling for Ctrl-C (closing the server)"""
    print("Server closing")
    sys.exit(0)


class ExecutePulseSequence(AveragerProgram):
    """This qick AveragerProgram handles a qibo sequence of pulses"""

    def __init__(self, soc: QickSoc, cfg: dict, sequence: PulseSequence, qubits: List[Qubit]):
        """In this function we define the most important settings.
        In detail:
            * set the conversion coefficients to be used for frequency and
              time values
            * max_gain, adc_trig_offset, max_sampling_rate are imported from
              cfg (runcard settings)
            * relaxdelay (for each execution) is taken from cfg (runcard)
            * syncdelay (for each measurement) is defined explicitly
            * wait_initialize is defined explicitly
            * super.__init__
        """

        self.soc = soc
        # No need for a different soc config object since qick is on board
        self.soccfg = soc
        # fill the self.pulse_sequence and the self.readout_pulses oject
        self.sequence = sequence
        self.qubits = qubits

        # conversion coefficients (in runcard we have Hz and ns)
        self.MHz = 0.000001
        self.us = 0.001

        # general settings
        self.max_gain = cfg["max_gain"]
        self.adc_trig_offset = cfg["adc_trig_offset"]
        self.max_sampling_rate = cfg["sampling_rate"]

        # TODO maybe better elsewhere
        # relax_delay is the time waited at the end of the program (for ADC)
        # syncdelay is the time waited at the end of every measure (overall t)
        # wait_initialize is the time waited at the end of initialize
        # all of these are converted using tproc CLK
        self.relax_delay = self.us2cycles(cfg["repetition_duration"] * self.us)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        super().__init__(soc, cfg)

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
            average (bool): if true return averaged res, otherwise single shots
        """
        if average:
            return super().acquire(
                soc,
                readouts_per_experiment=readouts_per_experiment,
                load_pulses=load_pulses,
                progress=progress,
                debug=debug,
            )
        else:
            # super().acquire function fill buffers used in collect_shots
            super().acquire(
                soc,
                readouts_per_experiment=readouts_per_experiment,
                load_pulses=load_pulses,
                progress=progress,
                debug=debug,
            )
            return self.collect_shots()

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
                lengths.append(self.soc.us2cycles(pulse.duration * self.us, gen_ch=ro_ch))
            adcs.append(adc_ch)

        adcs, adc_count = np.unique(adcs, return_counts=True)

        for idx, adc_ch in enumerate(adcs):
            count = adc_count[adc_ch]
            i_val = self.di_buf[idx].reshape((count, self.cfg["reps"])) / lengths[idx]
            q_val = self.dq_buf[idx].reshape((count, self.cfg["reps"])) / lengths[idx]

            tot_i.append(i_val)
            tot_q.append(q_val)
        return tot_i, tot_q

    def initialize(self):
        """This function gets called automatically by qick super.__init__,
        it contains:
        * declaration of channels and nyquist zones
        * declaration of readouts (just one per channel, otherwise ignores it)
        * for element in sequence calls the add_pulse_to_register function
          (if first pulse for channel, otherwise it will be done in the body)
        """

        # declare nyquist zones for all used channels
        ch_already_declared = []
        for pulse in self.sequence:
            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

            if gen_ch not in ch_already_declared:
                ch_already_declared.append(gen_ch)

                if pulse.frequency < self.max_sampling_rate / 2:
                    self.declare_gen(gen_ch, nqz=1)
                else:
                    self.declare_gen(gen_ch, nqz=2)

        # declare readouts
        ro_ch_already_declared = []
        for readout_pulse in self.sequence.ro_pulses:
            adc_ch = self.qubits[readout_pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[readout_pulse.qubit].readout.ports[0][1]
            if adc_ch not in ro_ch_already_declared:
                ro_ch_already_declared.append(adc_ch)
                length = self.soc.us2cycles(readout_pulse.duration * self.us, gen_ch=ro_ch)
                freq = readout_pulse.frequency * self.MHz
                # in declare_readout frequency in MHz
                self.declare_readout(ch=adc_ch, length=length, freq=freq, gen_ch=ro_ch)

        # register first pulses of all channels
        """
        first_pulse_registered = []
        for pulse in self.sequence:
            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]

            gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

            if gen_ch not in first_pulse_registered:
                first_pulse_registered.append(gen_ch)
                self.add_pulse_to_register(pulse, True)
        """

        # sync all channels and wait some time
        self.sync_all(self.wait_initialize)

    def add_pulse_to_register(self, pulse: Pulse, first=False):
        """This function calls the set_pulse_registers function"""

        # find channels relevant for this pulse
        qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
        adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
        ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
        gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

        # convert amplitude in gain and check is valid
        gain = int(pulse.amplitude * self.max_gain)
        if abs(gain) > self.max_gain:
            raise Exception("Amp must be in [-1,1], was: {pulse.amplitude}")

        # phase converted from rad (qibolab) to deg (qick) and then to reg vals
        phase = self.deg2reg(np.degrees(pulse.relative_phase), gen_ch=gen_ch)

        # pulse length converted with DAC CLK
        us_length = pulse.duration * self.us
        soc_length = self.soc.us2cycles(us_length, gen_ch=gen_ch)

        is_drag = isinstance(pulse.shape, Drag)
        is_gaus = isinstance(pulse.shape, Gaussian)
        is_rect = isinstance(pulse.shape, Rectangular)

        # pulse freq converted with frequency matching
        if pulse.type == PulseType.DRIVE:
            freq = self.soc.freq2reg(pulse.frequency * self.MHz, gen_ch=gen_ch)
        elif pulse.type == PulseType.READOUT:
            freq = self.soc.freq2reg(pulse.frequency * self.MHz, gen_ch=gen_ch, ro_ch=adc_ch)
        else:
            raise Exception(f"Pulse type {pulse.type} not recognized!")

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
                    delta=sigma,  # TODO: check if correct
                    alpha=pulse.beta,
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
        If the pulse is already loaded in the register just launch it,
        otherwise first calls the add_pulse_to_register function.
        If readout it does a measurement with an adc trigger, it does not wait.
        At the end of the pulse wait for clock.
        """

        for pulse in self.sequence:
            # time follows tproc CLK
            time = self.soc.us2cycles(pulse.start * self.us)

            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

            self.add_pulse_to_register(pulse)

            if pulse.type == PulseType.DRIVE:
                self.pulse(ch=gen_ch, t=time)
            elif pulse.type == PulseType.READOUT:
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


class ExecuteSingleSweep(RAveragerProgram):
    """This qick AveragerProgram handles a qibo sequence of pulses"""

    def __init__(self, soc: QickSoc, cfg: dict, sequence: PulseSequence, qubits: List[Qubit], sweeper: Sweeper):
        """In this function we define the most important settings.
        In detail:
            * set the conversion coefficients to be used for frequency and time
            * max_gain, adc_trig_offset, max_sampling_rate are imported from
              cfg (runcard settings)
            * relaxdelay (for each execution) is taken from cfg (runcard )
            * syncdelay (for each measurement) is defined explicitly
            * wait_initialize is defined explicitly
            * the cfg["expts"] (number of sweeped values) is set
            * super.__init__
        """

        self.soc = soc
        # No need for a different soc config object since qick is on board
        self.soccfg = soc
        # fill the self.pulse_sequence and the self.readout_pulses oject
        self.sequence = sequence
        self.qubits = qubits

        # conversion coefficients (in runcard we have Hz and ns)
        self.MHz = 0.000001
        self.us = 0.001

        # settings
        self.max_gain = cfg["max_gain"]
        self.adc_trig_offset = cfg["adc_trig_offset"]
        self.max_sampling_rate = cfg["sampling_rate"]

        # TODO maybe better elsewhere
        # relax_delay is the time waited at the end of the program (for ADC)
        # syncdelay is the time waited at the end of every measure
        # wait_initialize is the time waited at the end of initialize
        # all of these are converted using tproc CLK
        self.relax_delay = self.us2cycles(cfg["repetition_duration"] * self.us)
        self.syncdelay = self.us2cycles(0)
        self.wait_initialize = self.us2cycles(2.0)

        # sweeper Settings
        self.sweeper = sweeper
        self.sweeper_reg = None
        self.sweeper_page = None
        cfg["expts"] = len(sweeper.values)

        super().__init__(soc, cfg)

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
            average (bool): if true return averaged res, otherwise single shots
        """
        if average:
            _, i_val, q_val = super().acquire(
                soc,
                readouts_per_experiment=readouts_per_experiment,
                load_pulses=load_pulses,
                progress=progress,
                debug=debug,
            )
            return i_val, q_val
        else:
            # super().acquire function fill buffers used in collect_shots
            super().acquire(
                soc,
                readouts_per_experiment=readouts_per_experiment,
                load_pulses=load_pulses,
                progress=progress,
                debug=debug,
            )
            return self.collect_shots()

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
                lengths.append(self.soc.us2cycles(pulse.duration * self.us, gen_ch=ro_ch))
            adcs.append(adc_ch)

        adcs, adc_count = np.unique(adcs, return_counts=True)

        for idx, adc_ch in enumerate(adcs):
            count = adc_count[adc_ch]
            i_val = self.di_buf[idx].reshape((count, self.cfg["expts"], self.cfg["reps"])) / lengths[idx]
            q_val = self.dq_buf[idx].reshape((count, self.cfg["expts"], self.cfg["reps"])) / lengths[idx]

            tot_i.append(i_val)
            tot_q.append(q_val)
        return tot_i, tot_q

    def initialize(self):
        """This function gets called automatically by qick super.__init__,
        it contains:
        * declaration of sweeper register settings
        * declaration of channels and nyquist zones
        * declaration of readouts (just one per channel, otherwise ignores it)
        * for element in sequence calls the add_pulse_to_register function
          (if first pulse for channel, otherwise it will be done in the body)
        """

        # find channels of sweeper pulse
        pulse = self.sweeper.pulses[0]
        qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
        adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
        ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
        gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

        # find page of sweeper pulse channel
        self.sweeper_page = self.ch_page(gen_ch)

        # define start and step values
        start = self.sweeper.values[0]
        step = self.sweeper.values[1] - self.sweeper.values[0]

        # find register of sweeped parameter and assign start and step
        if self.sweeper.parameter == Parameter.frequency:
            self.sweeper_reg = self.sreg(gen_ch, "freq")
            self.cfg["start"] = self.soc.freq2reg(start * self.MHz, gen_ch)
            self.cfg["step"] = self.soc.freq2reg(step * self.MHz, gen_ch)

            # TODO: should stop if nyquist zone changes in the sweep

        elif self.sweeper.parameter == Parameter.amplitude:
            self.sweeper_reg = self.sreg(gen_ch, "gain")
            self.cfg["start"] = int(start * self.max_gain)
            self.cfg["step"] = int(step * self.max_gain)

            if self.cfg["start"] + self.cfg["step"] * self.cfg["expts"] > self.max_gain:
                raise Exception("Amplitude higher than maximum!")

        # declare nyquist zones for all used channels
        ch_already_declared = []
        for pulse in self.sequence:
            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

            if gen_ch not in ch_already_declared:
                ch_already_declared.append(gen_ch)

                if pulse.frequency < self.max_sampling_rate / 2:
                    self.declare_gen(gen_ch, nqz=1)
                else:
                    self.declare_gen(gen_ch, nqz=2)

        # declare readouts
        ro_ch_already_declared = []
        for readout_pulse in self.sequence.ro_pulses:
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            if adc_ch not in ro_ch_already_declared:
                ro_ch_already_declared.append(adc_ch)
                length = self.soc.us2cycles(readout_pulse.duration * self.us, gen_ch=ro_ch)
                freq = readout_pulse.frequency * self.MHz
                # for declare_readout freqs in MHz and not in register values
                self.declare_readout(ch=adc_ch, length=length, freq=freq, gen_ch=ro_ch)

        # register first pulses of all channels
        """
        first_pulse_registered = []
        for pulse in self.sequence:
            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

            if gen_ch not in first_pulse_registered:
                first_pulse_registered.append(gen_ch)
                self.add_pulse_to_register(pulse)
        """

        # sync all channels and wait some time
        self.sync_all(self.wait_initialize)

    def add_pulse_to_register(self, pulse):
        """This function calls the set_pulse_registers function"""

        is_sweeped = self.sweeper.pulses[0] == pulse

        # find channels relevant for this pulse
        qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
        adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
        ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
        gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

        # assign gain parameter
        if is_sweeped and self.sweeper.parameter == Parameter.amplitude:
            gain = self.cfg["start"]
        else:
            gain = int(pulse.amplitude * self.max_gain)

        if abs(gain) > self.max_gain:
            raise Exception("Amp must be in [-1,1], was: {pulse.amplitude}")

        # phase converted from rad (qibolab) to deg (qick) and to register vals
        phase = self.deg2reg(math.degrees(pulse.relative_phase), gen_ch=gen_ch)

        # pulse length converted with DAC CLK
        us_length = pulse.duration * self.us
        soc_length = self.soc.us2cycles(us_length, gen_ch=gen_ch)

        is_drag = isinstance(pulse.shape, Drag)
        is_gaus = isinstance(pulse.shape, Gaussian)
        is_rect = isinstance(pulse.shape, Rectangular)

        # pulse freq converted with frequency matching
        if pulse.type == PulseType.DRIVE:
            if is_sweeped and self.sweeper.parameter == Parameter.frequency:
                freq = self.cfg["start"]
            else:
                freq = self.soc.freq2reg(pulse.frequency * self.MHz, gen_ch=gen_ch)

        elif pulse.type == PulseType.READOUT:
            freq = self.soc.freq2reg(pulse.frequency * self.MHz, gen_ch=gen_ch, ro_ch=adc_ch)
        else:
            raise Exception(f"Pulse type {pulse.type} not recognized!")

        # if pulse is drag or gaus first define the i-q shape and then set regs
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
                    delta=sigma,  # TODO: check if correct
                    alpha=pulse.beta,
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

    def update(self):
        """Update function for sweeper"""
        self.mathi(self.sweeper_page, self.sweeper_reg, self.sweeper_reg, "+", self.cfg["step"])

    def body(self):
        """Execute sequence of pulses.
        If the pulse is already loaded in the register just launch it,
        otherwise first calls the add_pulse_to_register function.
        If readout it does a measurement with an adc trigger, it does not wait.
        At the end of the pulse wait for clock and call update function.
        """

        for pulse in self.sequence:
            # time follows tproc CLK
            time = self.soc.us2cycles(pulse.start * self.us)

            qd_ch = self.qubits[pulse.qubit].drive.ports[0][1]
            adc_ch = self.qubits[pulse.qubit].feedback.ports[0][1]
            ro_ch = self.qubits[pulse.qubit].readout.ports[0][1]
            gen_ch = qd_ch if pulse.type == PulseType.DRIVE else ro_ch

            self.add_pulse_to_register(pulse)

            if pulse.type == PulseType.DRIVE:
                self.pulse(ch=gen_ch, t=time)
            elif pulse.type == PulseType.READOUT:
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


class MyTCPHandler(BaseRequestHandler):
    def handle(self):
        self.server.socket.setblocking(False)

        count = pickle.loads(self.request.recv(15))
        received = self.request.recv(count, socket.MSG_WAITALL)
        """
        received = bytearray()
        while count != 0:
            minimum = min(1200, count)
            rec = self.request.recv(minimum)
            print(f"\tLen rec: {len(rec)}")
            received.extend(rec)
            count = count - minimum
        """

        data = pickle.loads(received)

        if data["operation_code"] == "execute_pulse_sequence":
            program = ExecutePulseSequence(global_soc, data["cfg"], data["sequence"], data["qubits"])
            toti, totq = program.acquire(
                global_soc,
                data["readouts_per_experiment"],
                load_pulses=True,
                progress=False,
                debug=False,
                average=data["average"],
            )
        elif data["operation_code"] == "execute_single_sweep":
            program = ExecuteSingleSweep(global_soc, data["cfg"], data["sequence"], data["qubits"], data["sweeper"])
            toti, totq = program.acquire(
                global_soc,
                data["readouts_per_experiment"],
                load_pulses=True,
                progress=False,
                debug=False,
                average=data["average"],
            )

        results = {"i": toti, "q": totq}
        self.request.sendall(pickle.dumps(results))


# starts the handler
signal.signal(signal.SIGINT, signal_handler)
global_soc = QickSoc()

if __name__ == "__main__":
    HOST = "192.168.0.72"  # Serverinterface address
    PORT = 6000  # Port to listen on (non-privileged ports are > 1023)
    TCPServer.allow_reuse_address = True
    # Create the server, binding to localhost on port 6000
    with TCPServer((HOST, PORT), MyTCPHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        print("Server Listening")
        server.serve_forever()
