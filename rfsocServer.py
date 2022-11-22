# rfsocServer.py
from socketserver import BaseRequestHandler, TCPServer
import numpy as np
from pynq import Overlay

import time
from qick import AveragerProgram, QickSoc

class Program(AveragerProgram):
    def __init__(self, soc, cfg, sequence):
        self.sequence = sequence
        self.soc = soc
        super().__init__(soc, cfg)
        # TODO: Move all cfg declarations in __init__

    def initialize(self):
        ro_channel = self.cfg["res_ch"] #self.cfg["resonator_channel"]
        qd_channel = self.cfg["qubit_ch"] #self.cfg["qubit_channel"]

        self.declare_gen(ch=ro_channel, nqz=2) # Readout
        self.declare_gen(ch=qd_channel, nqz=2) # Qubit

        # assume one drive and one ro pulse
        #qd_pulse = self.sequence.qd_pulses[0]
        #ro_pulse = self.sequence.ro_pulses[0]
        #assert qd_pulse.channel == qd_channel
        #assert ro_pulse.channel == ro_channel

        # conver pulse lengths to clock ticks
#        qd_length = self.soc.us2cycles(qd_pulse.duration * 1e-3, gen_ch=qd_channel)
#        ro_length = self.soc.us2cycles(ro_pulse.duration * 1e-3, gen_ch=ro_channel)
# 
# 

        qd_length = self.soc.us2cycles(0.04 , gen_ch=qd_channel)
        ro_length = self.soc.us2cycles(3.0 , gen_ch=ro_channel)
        # configure the readout lengths and downconversion frequencies
        for ch in [0, 1]:
#            self.declare_readout(ch=ch, length=ro_length, freq=ro_pulse.frequency * 1e-6, gen_ch=ro_channel)
            self.declare_readout(ch=ch, length=ro_length, freq= self.cfg["f_res"] , gen_ch=ro_channel)
        # convert frequencies to dac register value
        # TODO: Why are frequencies converted after declaring the readout?
#        qd_frequency = self.freq2reg(qd_pulse.frequency * 1e-6, gen_ch=qd_channel)
#        ro_frequency = self.freq2reg(ro_pulse.frequency * 1e-6, gen_ch=ro_channel, ro_ch=0)
        qd_frequency = self.freq2reg(self.cfg["f_ge"] , gen_ch=qd_channel)
        ro_frequency = self.freq2reg(self.cfg["f_res"]  , gen_ch=ro_channel, ro_ch=0)
        # calculate pulse gain from amplitude
        max_gain = 30000 #self.cfg["max_gain"]
 #       qd_gain = int(qd_pulse.amplitude * max_gain)
#        ro_gain = int(ro_pulse.amplitude * max_gain)
        qd_gain = int(0.56 * max_gain)
        ro_gain = int(0.02 * max_gain)
        # add qubit and readout pulses to respective channels
        # TODO: Register multiple drive pulses
        # TODO: Register proper shapes and phases to pulses
        self.set_pulse_registers(
            ch=qd_channel,
            style="const",
            freq=qd_frequency,
            phase= 0, # int(qd_pulse.phase),
            gain=qd_gain,
            length=qd_length,
            )
        self.set_pulse_registers(
            ch=ro_channel,
            style="const",
            freq=ro_frequency,
            phase= 0, #int(ro_pulse.phase),
            gain=ro_gain,
            length=ro_length,
            )

        self.synci(200)

    def body(self):
        ro_channel = self.cfg["res_ch"]
        qd_channel = self.cfg["qubit_ch"]
        delay_before_readout = 0.05 # self.cfg["delay_before_readout"]
        delay_before_readout = self.us2cycles(delay_before_readout )

        # play drive pulse
        # TODO: Play multiple drive pulses
        self.pulse(ch=qd_channel)
        # align channels and wait some time (defined in the runcard)
        self.sync_all(delay_before_readout)

        # trigger measurement, play measurement pulse, wait for qubit to relax
        syncdelay = self.us2cycles(self.cfg["relax_delay"] * 1e-3)
        self.measure(pulse_ch=ro_channel, adcs=[0, 1], wait=True, syncdelay=syncdelay)

class MyTCPHandler(BaseRequestHandler):
    """
    The request handler class for our server.
    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """
    dac_nchanels = 2
    dac_sample_size = 2
    soc = QickSoc()
    soccfg = soc
    hw_cfg={"res_ch":0,
        "qubit_ch":1
       }
    readout_cfg={
        "readout_length":soccfg.us2cycles(3.0, gen_ch=0), # [Clock ticks]
        "f_res": 7271.25 , #99.775 +0.18, # [MHz]
        "res_phase": 3097210280, #96.73,
        "adc_trig_offset": 250, # [Clock ticks]
        "res_gain":400,
        "threshold": 0
        }
    qubit_cfg={
        "sigma":soccfg.us2cycles(0.025, gen_ch=1),
        "pi_gain": 17000,
        "pi2_gain":17000//2, 
        "f_ge":8014.6,
        "relax_delay":500
    }
    expt_cfg={
        "qubit_gain":4000,
            "start":4, "step":4, "expts":50, "reps": 1000,
        }
    cfg={**hw_cfg,**readout_cfg,**qubit_cfg,**expt_cfg} #combine configs   
    """
    def __init__(self, request, client_address, server):
    super().__init__(request, client_address, server)
    self.waveform = np.zeros((self.dac_nchannels, 
    self.dac_sample_size), 
    dtype="i2")
    self.adc_waveform = np.random.rand(self.dac_sample_size, 1)
    """ 

    def handle(self):
        import json 

        print('Got connection from', self.client_address)
        # self.request is the TCP socket connected to the client
        #self.data = self.request.recv(1024).strip()
        #waveform = np
        jsonReceived = self.request.recv(1024)

        data = jsonReceived.decode('utf-8')
        data = json.loads(data)
        self.op = data["opcode"]
        print("OpCode: ", self.op)

        self.length = data["length"]
        sequence = {"pulse1": 1, "pulse2": 2}
        self.cfg["pulse_length"]=self.length
        program = Program(self.soc, self.cfg, sequence)
        avgi, avgq = program.acquire(self.soc, load_pulses=True, progress=False, debug=False)
        print("shape: ", avgi.shape)
        jsonDic = {"avgiRe": avgi[0][0], "avgiIm": avgi[1][0], "avgqRe": avgq[0][0],"avgqIm": avgq[1][0]}

        self.request.sendall(json.dumps(jsonDic).encode())
        print("Enviando avgi,avgq",avgi,avgq )     



if __name__ == "__main__":
    HOST = "192.168.2.72" # Serverinterface address 
    PORT = 6000 # Port to listen on (non-privileged ports are > 1023)
    TCPServer.allow_reuse_address = True
    # Create the server, binding to localhost on port 6000
    with TCPServer((HOST, PORT), MyTCPHandler) as server:
            # Activate the server; this will keep running until you
            # interrupt the program with Ctrl-C
        print("Server Listening")
        server.serve_forever()
