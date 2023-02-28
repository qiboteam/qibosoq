from qick import RAveragerProgram, NDAveragerProgram


class ProgramSweep(RAveragerProgram):
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
