from qick import AveragerProgram


class ProgramExecute(AveragerProgram):
    """This implementation of qick AveragerProgram handles a qibo sequence of pulse"""

    def __init__(self, soc, cfg, sequence):

        self.MHz = 0.000001
        self.mu_s = 0.001

        self.soc = soc
        self.cfg = cfg

        self.sequence = sequence['pulses']
        self.max_gain = self.cfg["max_gain"]

        # HW configuration
        # TODO maybe not harcoded values are better
        self.ro_channel = 0
        self.ro_input_channel = 0
        self.qd_channel = 1

        # Readout configuration

        # TODO this is ok (?)
        last_pulse = sequence['pulses'][list(sequence['pulses'])[-1]]
        if last_pulse['type'] == 'ro':

            self.ro_freq = last_pulse['frequency'] * self.MHz
            ro_duration = last_pulse["duration"] * self.mu_s
            self.ro_length = self.soc.us2cycles(ro_duration,
                                                gen_ch=self.ro_channel)
            self.res_phase = last_pulse["relative_phase"]
        else:
            raise NotImplementedError("Last pulse is not Readout.")

        self.add_trig_offset = self.cfg["adc_trig_offset"]

        # Experiment
        cfg["reps"] = self.cfg["hardware_avg"]
        self.relax_delay = self.cfg["repetition_duration"]

        self.delay_before_readout = self.soc.us2cycles(self.relax_delay * self.mu_s)
        super().__init__(soc, cfg)

    def initialize(self):

        # declare nyquist zones for qubit and resonator
        self.declare_gen(ch=self.qd_channel, nqz=2)  # Qubit
        self.declare_gen(ch=self.ro_channel, nqz=2)  # Readout

        # declare readout
        self.declare_readout(ch=self.ro_input_channel,
                             length=self.ro_length,
                             freq=self.ro_freq,
                             gen_ch=self.ro_channel)

        self.drive_pulses = False  # becomes True if drives pulses are presents, otherwise stays false

        # For each pulse in sequence add correspondent pulse register in qick
        for i, pulse in enumerate(self.sequence):
            p = self.sequence[pulse]

            if p["type"] == 'qd':
                # If drive pulse ... (currently only gaussian and drag pulses are supported)

                self.drive_pulses = True

                self.qd_gain = int(p["amplitude"] * self.max_gain)
                self.qd_frequency = self.soc.freq2reg(p["frequency"] * self.MHz, gen_ch=self.qd_channel)

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
                freq=self.freq2reg(p["frequency"] * self.MHz,
                                   gen_ch=self.ro_channel,
                                   ro_ch=self.ro_channel)

                self.set_pulse_registers(ch=self.ro_channel,
                                         style="const",
                                         freq=freq,
                                         phase=int(p["relative_phase"]),               # TODO there is a readout phase and a relative phase of the readout pulse...
                                         gain=int(p["amplitude"]*self.max_gain),
                                         length=self.ro_length)
            else:
                raise Exception(f'\n\nPulse type {p["type"]} not recognized!\n')

        self.synci(200)

    def body(self):
        """Execute drive pulses if present, then measure trough readout pulse."""

        if self.drive_pulses:
            self.pulse(ch=self.qd_channel)
            self.sync_all(self.delay_before_readout)

        self.measure(pulse_ch=self.ro_channel,
                     adcs=[0],
                     adc_trig_offset=self.add_trig_offset,
                     wait=True,
                     syncdelay=self.delay_before_readout)
