from qick import RAveragerProgram, NDAveragerProgram

from qick.averager_program import QickSweep

class ExecuteSweep(NDAveragerProgram):
    """This qick NDAveragerProgram handles a qibo sequence of pulse and sweepers"""

    def __init__(self, soc, cfg, sequence, sweepers):
        """In this function the most important settings are defined and the sequence is transpiled.

        * set the conversion coefficients to be used for frequency and time values
        * max_gain, adc_trig_offset, max_sampling_rate are imported from cfg (runcard settings)
        * connections are defined (drive and readout channel for each qubit)

        * pulse_sequence, readouts, channels are defined to be filled by convert_sequence()

        * cfg["reps"] is set from hardware_avg
        * super.__init__
        """

        # conversion coefficients
        self.MHz = 0.000001
        self.mu_s = 0.001

        # settings
        self.max_gain = cfg["max_gain"]  # TODO redundancy
        self.adc_trig_offset = cfg["adc_trig_offset"]
        self.max_sampling_rate = cfg["sampling_rate"]

        # connections  (for every qubit here are defined drive and readout lines
        self.connections = {
                '0': {"drive": 1,
                      "readout": 0,
                      "adc_ch": 0},
        }

        self.pulse_sequence = {}
        self.readouts = []
        self.channels = []
        self.sweepers = []

        # fill the self.pulse_sequence and the self.readout_pulses oject
        self.soc = soc
        self.soccfg = soc  # No need for a different soc config object since qick is on board
        self.convert_sequence(sequence["pulses"])

        cfg["reps"] = cfg["hardware_avg"]
        super().__init__(soc, cfg)

    def convert_sequence(self, sequence):
        """In this function we transpile the sequence of pulses in a form better suited for qick

        * Note that all the conversions (in different "standard" units and in registers valued are done here

        Three object are of touched by this function:
        * self.pulse_sequence is a dictionary that contains all the pulse with information regarding the pulse itself.
          To be used in initialize (set_pulse_registers) and in body (executing)

        * self.readouts is a list that contains all the readout information.
          To be used in initialize for declare_readout

        * self.channels is a list that contain channel number and nyquist zone of initialization


        Templates:
        self.pulse_sequence = {
            serial: {
                "channel":
                "type":
                "freq":
                "length":
                "phase":
                "time":
                "gain"
                "waveform":     # readout as a default value

                "shape":    # these only if drive
                "sigma":
                "name":

                "delta":    # these only if drag
                "alpha":

                "adc_trig_offset":      # these only if readout
                "wait": False
                "syncdelay": 100
            }
        }
        self.readouts = {
            0: {
                "adc_ch":
                "gen_ch":
                "length":
                "freq":
            }
        }
        self.channels = [(channel, generation), ...]

        """

        for _, pulse in sequence.items():
            pulse_dic = {}

            pulse_dic["type"] = pulse["type"]
            pulse_dic["time"] = pulse["start"]

            gen_ch, adc_ch = self.from_qubit_to_ch(pulse["qubit"],   # if drive pulse return only gen_ch, otherwise both
                                                   pulse["type"])
            pulse_dic["freq"] = self.soc.freq2reg(pulse["frequency"] * self.MHz,  # TODO maybe differentiate between drive and readout
                                                  gen_ch=gen_ch,
                                                  ro_ch=adc_ch)

            length = pulse["duration"] * self.mu_s
            pulse_dic["length"] = self.soc.us2cycles(length)  # uses tproc clock now
            pulse_dic["phase"] = self.deg2reg(pulse["relative_phase"],  # TODO maybe differentiate between drive and readout
                                              gen_ch=gen_ch)

            pulse_dic["gain"] = int(pulse["amplitude"] * self.max_gain)

            if pulse_dic["type"] == "qd":
                pulse_dic["ch"] = gen_ch

                pulse_dic["waveform"] = pulse["shape"]  # TODO redundancy
                pulse_dic["shape"] = pulse["shape"]
                pulse_dic["name"] = pulse["shape"]
                pulse_dic["style"] = "arb"

                sigma = length / pulse["rel_sigma"]
                pulse_dic["sigma"] = self.soc.us2cycles(sigma)

                if pulse_dic["shape"] == "Drag":
                    pulse_dic["delta"] = pulse_dic["sigma"]  # TODO redundancy
                    pulse_dic["alpha"] = pulse["beta"]

            elif pulse_dic["type"] == "ro":
                pulse_dic["ch"] = gen_ch

                pulse_dic["waveform"] = None    # this could be unsupported
                pulse_dic["adc_trig_offset"] = self.adc_trig_offset
                pulse_dic["wait"] = False
                pulse_dic["syncdelay"] = 100  # clock ticks

                # prepare readout declaration values
                readout = {}
                readout["adc_ch"] = adc_ch
                readout["gen_ch"] = gen_ch
                readout["length"] = length  # TODO not sure it should be the same as the pulse! This is the window for the adc
                readout["freq"] = pulse_dic["freq"]

                self.readouts.append(readout)

            self.pulse_sequence[pulse["serial"]] = pulse_dic  # TODO check if deep copy

            sweep_parameter = self.get_sweeped(pulse)
            if sweep_parameter is not None:
                raise Exception("Not yet implemented")

            if pulse["frequency"] < self.max_sampling_rate / 2:
                zone = 1
            else:
                zone = 2
            self.channels.append((gen_ch, zone))

    def get_sweeped(self, pulse):
        raise Exception("Not yet implemented")

    def from_qubit_to_ch(self, qubit, pulse_type):
        """Helper function for retrieving channel numbers from qubits"""

        drive_ch = self.connections[str(qubit)]["drive"]
        readout_ch = self.connections[str(qubit)]["readout"]
        adc_ch = self.connections[str(qubit)]["adc_ch"]

        if pulse_type == "qd":
            return drive_ch, None
        elif pulse_type == "ro":
            return readout_ch, adc_ch

    def initialize(self):
        """This function gets called automatically by qick super.__init__, it contains:

        * declaration of channels and nyquist zones
        * declaration of readouts (just one per channel, otherwise ignores it)
        * for element in sequence calls the add_pulse_to_register function
          (if first pulse for channel, otherwise it will be done in the body)

        """

        # declare nyquist zones for all used channels
        for channel in self.channels:
            self.declare_gen(ch=channel[0], nqz=channel[1])

        # declare readouts
        channel_already_declared = []
        for readout in self.readouts:
            if readout["adc_ch"] not in channel_already_declared:
                channel_already_declared.append(readout["adc_ch"])
            else:
                print(f"Avoided redecalaration of channel {readout['ch']}")    # TODO raise warning
                continue
            self.declare_readout(ch=readout["adc_ch"],
                                 length=readout["length"],
                                 freq=readout["freq"],
                                 gen_ch=readout["gen_ch"])

        # list of channels where a pulse is already been registered
        first_pulse_registered = []

        for serial, pulse in self.pulse_sequence.items():
            if pulse["ch"] not in first_pulse_registered:
                first_pulse_registered.append(pulse["ch"])
            else:
                continue

            self.add_pulse_to_register(pulse)

        for sweep in self.sweepers:
            self.add_sweep(QickSweep(self,
                                     sweep["register"],
                                     sweep["start"],
                                     sweep["stop"],
                                     sweep["n_points"]))

        self.synci(200)

    def add_pulse_to_register(self, pulse):
        """The task of this function is to call the set_pulse_registers function"""

        if pulse["type"] == "qd":
            if pulse["shape"] == "Gaussian":
                self.add_gauss(ch=pulse["ch"],
                               name=pulse["name"],
                               sigma=pulse["sigma"],
                               length=pulse["length"])

            elif pulse["shape"] == "Drag":
                self.add_DRAG(ch=pulse["ch"],
                              name=pulse["name"],
                              sigma=pulse["sigma"],
                              delta=pulse["delta"],
                              alpha=pulse["alpha"],
                              length=pulse["length"])

            else:
                raise Exception(f'Pulse shape {pulse["shape"]} not recognized!')

            self.set_pulse_registers(ch=pulse["ch"],
                                     style=pulse["style"],
                                     freq=pulse["freq"],
                                     phase=pulse["phase"],
                                     gain=pulse["gain"],
                                     waveform=pulse["waveform"])

        elif pulse["type"] == "ro":

            self.set_pulse_registers(ch=pulse["ch"],
                                     style=pulse["style"],
                                     freq=pulse["freq"],
                                     phase=pulse["phase"],
                                     gain=pulse["gain"],
                                     length=pulse["length"],
                                     waveform=pulse["waveform"])
        else:
            raise Exception(f'Pulse type {pulse["type"]} not recognized!')

    def body(self):
        """Execute sequence of pulses.

        If the pulse is already loaded it just launches it,
        otherwise first calls the add_pulse_to_register function.

        If readout pulse it does a measurment with an adc trigger, in general does not wait.

        At the end of the pulse wait for clock.
        """

        # list of channels where a pulse is already been executed
        first_pulse_executed = []

        for serial, pulse in self.pulse_sequence.items():
            if pulse["ch"] in first_pulse_executed:
                self.add_pulse_to_register(pulse)
            else:
                first_pulse_executed.append(pulse["ch"])

            if pulse["type"] == "qd":
                self.pulse(ch=pulse["ch"], t=pulse["time"])
            elif pulse["type"] == "ro":
                self.measure(pulse_ch=pulse["ch"],
                             adcs=pulse["adc_ch"],
                             adc_trig_offset=pulse["adc_trig_offset"],
                             t=pulse["time"],
                             wait=pulse["wait"],
                             syncdelay=pulse["syncdelay"])
        self.wait_all()
        self.sync_all(self.relax_delay)



class ExecuteSweep(RAveragerProgram):
    def __init__(self, soc, cfg, parameter, sequence, range):

        self.MHz = 0.000001
        self.mu_s = 0.001

        self.soc = soc
        self.cfg = cfg

        self.max_gain = self.cfg["max_gain"]
        self.sequence = sequence

        self.parameter = parameter
        self.start = range['start']
        self.step = range['step']
        self.expt = range['expt']

        # HW configuration
        # TODO maybe not harcoded values are better
        self.ro_channel = 0
        self.ro_input_channel = 0
        self.qd_channel = 1

        # Readout configuration
        # TODO this is ok (?)
        last_pulse = sequence[list(sequence)[-1]]
        if last_pulse['type'] == 'ro':
            self.ro_freq = last_pulse['frequency'] * self.MHz
            ro_duration = last_pulse["duration"] * self.mu_s
            self.ro_length = self.soc.us2cycles(ro_duration,
                                                gen_ch=self.ro_channel)
            self.res_phase = last_pulse["relative_phase"]
            self.ro_gain = int(last_pulse['amplitude'] * self.max_gain)
        else:
            raise NotImplementedError("Last pulse is not Readout.")

        self.add_trig_offset = self.cfg["adc_trig_offset"]

        # Qubit configuration
        self.qubit_freq = sequence['0']['frequency'] * self.MHz
        self.qubit_gain = int(sequence['0']['amplitude'] * self.max_gain)
        self.probe_length = self.soc.us2cycles(sequence['0']['duration'] * self.mu_s,
                                               gen_ch=self.qd_channel)

        # Experiment
        cfg["reps"] = self.cfg["hardware_avg"]
        self.relax_delay = self.cfg["repetition_duration"]
        cfg['expts'] = self.expt
        cfg['start'] = self.start
        cfg['step'] = self.step

        self.delay_before_readout = self.soc.us2cycles(self.relax_delay * self.mu_s)
        super().__init__(soc, cfg)

    def initialize(self):

        self.r_freq = self.freq2reg(self.qubit_freq, gen_ch=self.qd_channel)
        self.f_start = self.freq2reg(self.qubit_freq, gen_ch=self.qd_channel)
        self.f_step = 0
        self.r_gain = self.qubit_gain
        self.g_start = self.qubit_gain
        self.g_step = 0

        self.declare_gen(ch=self.ro_channel, nqz=2)  # Readout
        self.declare_gen(ch=self.qd_channel, nqz=2)  # Qubit

        self.declare_readout(ch=self.ro_input_channel,
                             length=self.ro_length,
                             freq=self.ro_freq,
                             gen_ch=self.ro_channel)


        self.q_rp = self.ch_page(self.qd_channel)  # get register page for qubit_ch
        if self.parameter == "Parameter.frequency":
            self.r_freq = self.sreg(self.qd_channel, "freq")   # get frequency register for qd_ch
            self.f_start = self.freq2reg(self.start * self.MHz, gen_ch=self.qd_channel)  # get start/step frequencies
            self.f_step = self.freq2reg(self.step * self.MHz, gen_ch=self.qd_channel)

        elif self.parameter == "Parameter.amplitude":
            self.r_gain = self.sreg(self.qd_channel, "gain")   # get amplitud register for qd_ch
            self.g_start = int(self.start * self.max_gain)
            self.g_step = int(self.step * self.max_gain)

        else:
            raise Exception('Sweeper only works with Frquency and Gain')

        f_res = self.freq2reg(self.ro_freq,
                              gen_ch=self.ro_channel,
                              ro_ch=self.ro_input_channel)

        for i, pulse in enumerate(self.sequence):
            p = self.sequence[pulse]

            if p["type"] == 'qd':
                # If drive pulse ... (currently only gaussian and drag pulses are supported)

                self.qd_gain = self.g_start
                self.qd_frequency = self.f_start

                duration = self.soc.us2cycles(p["duration"] * self.mu_s, gen_ch=1)
                sigma = self.soc.us2cycles(p["duration"] * self.mu_s / p["rel_sigma"], gen_ch=1)

                if p['shape'] == "Gaussian":

                    self.add_gauss(ch=self.qd_channel,
                                   name="Gaussian",
                                   sigma=sigma,
                                   length=duration)

                    self.set_pulse_registers(ch=self.qd_channel,
                                             style="arb",
                                             freq=self.qd_frequency,
                                             phase=self.deg2reg(p["relative_phase"],
                                                                gen_ch=self.qd_channel),
                                             gain=self.qd_gain,
                                             waveform="Gaussian")

                elif p['shape'] == "Drag":
                    self.add_DRAG(ch=self.qd_channel,
                                  name="Drag",
                                  sigma=sigma,
                                  length=duration,
                                  delta=sigma,
                                  alpha=p["beta"])

                    self.set_pulse_registers(ch=self.qd_channel,
                                             style="arb",
                                             freq=self.qd_frequency,
                                             phase=self.deg2reg(p["relative_phase"],
                                                                gen_ch=self.qd_channel),
                                             gain=self.qd_gain,
                                             waveform="Drag")
                else:
                    raise Exception(f'\n\nPulse shape {p["shape"]} not recognized!\n')

            elif p["type"] == 'ro':
                # If readout pulse ...
                freq = self.freq2reg(p["frequency"] * self.MHz,
                                     gen_ch=self.ro_channel,
                                     ro_ch=self.ro_channel)

                self.set_pulse_registers(ch=self.ro_channel,
                                         style="const",
                                         freq=freq,
                                         phase=int(p["relative_phase"]),               # TODO there is a readout phase and a relative phase of the readout pulse...
                                         gain=int(p["amplitude"]*self.max_gain),       # TODO check if gain is int
                                         length=self.ro_length)
            else:
                raise Exception(f'\n\nPulse type {p["type"]} not recognized!\n')

        self.synci(200)

    def body(self):

        self.pulse(ch=self.qd_channel)  # play probe pulse

        self.sync_all(self.delay_before_readout)

        # trigger measurement, play measurement pulse, wait for qubit to relax
        self.measure(pulse_ch=self.ro_channel,
                     adcs=[self.ro_input_channel],
                     adc_trig_offset=self.add_trig_offset,
                     wait=True,
                     syncdelay=self.soc.us2cycles(self.relax_delay))

    def update(self):
        self.mathi(self.q_rp, self.r_freq, self.r_freq, '+', self.f_step)  # update frequency
        self.mathi(self.q_rp, self.r_gain, self.r_gain, '+', self.g_step)  # update gain list
