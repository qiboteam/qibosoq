from qick import AveragerProgram


class ExecutePulseSequence(AveragerProgram):
    """This qick AveragerProgram handles a qibo sequence of pulse"""

    def __init__(self, soc, cfg, sequence):
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

            if pulse["frequency"] < self.max_sampling_rate / 2:
                zone = 1
            else:
                zone = 2
            self.channels.append((gen_ch, zone))

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
