# rfsocServer.py
from socketserver import BaseRequestHandler, TCPServer
import numpy as np
from pynq import Overlay

import time
from qick import AveragerProgram, QickSoc
######################################################
#
class Program(AveragerProgram):
#
######################################################

    def __init__(self, soc, cfg, sequence):       
        self.sequence = sequence
        self.soc = soc
        self.cfg = cfg
        self.ro_channel = self.cfg["res_ch"] 
        self.qd_channel = self.cfg["qubit_ch"]
        # conver pulse lengths to clock ticks
        #TODO: Fix the qd length and gain for every pulse 
        self.qd_length = self.soc.us2cycles(4*self.cfg["sigma"] , gen_ch=self.qd_channel)
        self.ro_length = self.soc.us2cycles(self.cfg["readout_length"] , gen_ch=self.ro_channel) 
        # convert frequencies to dac register value  
        self.qd_frequency = self.soc.freq2reg(self.cfg["f_ge"] , gen_ch=self.qd_channel)
        self.ro_frequency = self.soc.freq2reg(self.cfg["f_res"]  , gen_ch=self.ro_channel, ro_ch=0)  
        #TODO: Use max_gain and a value for the gain between 0 and 1      
        self.qd_gain = self.cfg["pi_gain"]
        self.ro_gain = self.cfg["res_gain"]
        super().__init__(soc, cfg)
 

    def initialize(self):


        self.declare_gen(ch=self.ro_channel, nqz=2) # Readout
        self.declare_gen(ch=self.qd_channel, nqz=2) # Qubit

        # configure the readout lengths and downconversion frequencies
        for ch in [0, 1]:
            self.declare_readout(ch=ch, length=self.ro_length, freq= self.cfg["f_res"] , gen_ch=self.ro_channel)

        # add qubit and readout pulses to respective channels
        print(self.cfg["rabi_length"], self.cfg["sigma"])
        sigma = self.soc.us2cycles(self.cfg["rabi_length"], gen_ch=1)
#        sigma = self.soc.us2cycles(self.cfg["sigma"], gen_ch=1)
        self.add_gauss(ch=self.qd_channel, name="gaussian", sigma=sigma, length=sigma*4)
        for i, pulse in enumerate(self.sequence):
            p = self.sequence[pulse]
            if p["channel"] == 1:
                self.set_pulse_registers(
                    ch=self.qd_channel,
                    style="arb",
                    freq=self.qd_frequency,
                    phase= 0, # int(qd_pulse.phase),
                    gain=self.qd_gain,
#                    length=qd_length,
                    waveform="gaussian"
                    )

                print("Drive Pulse: ",i,  p)   
            elif p["channel"] == 0:
                self.set_pulse_registers(
                    ch=self.ro_channel,
                    style="const",
                    freq=self.ro_frequency,
                    phase= 0, # int(qd_pulse.phase),
                    gain=self.ro_gain,
                    length=self.ro_length,

                    )
                print("Readout Pulse: ",i,  p)   
        


        self.synci(200)

    def body(self):

        delay_before_readout = self.soc.us2cycles(0.05)

        # play drive pulse
        # TODO: Play multiple drive pulses
        self.pulse(ch=self.qd_channel)
        # align channels and wait some time (defined in the runcard)
        self.sync_all(delay_before_readout)

        # trigger measurement, play measurement pulse, wait for qubit to relax

        self.measure(pulse_ch=self.ro_channel, adcs=[0, 1], wait=True, syncdelay=self.cfg["relax_delay"])

###################################################
#
class MyTCPHandler(BaseRequestHandler):
#
###################################################
    """
    The request handler class for our server.
    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    cfg = {}
    soc = QickSoc()
    
 #   def __init__(self, request, client_address, server):
 #       super().__init__(request, client_address, server)

    def handle(self):
        import json 
        sequence = {}
        print('Got connection from', self.client_address)
        # self.request is the TCP socket connected to the client

        jsonReceived = self.request.recv(2048)

        data = json.loads(jsonReceived.decode('utf-8'))

        if data['opCode'] == 'configuration':
            MyTCPHandler.cfg = data
        elif data['opCode'] == "setup":
            self.experiment = data
            self.cfg ={**MyTCPHandler.cfg, **self.experiment}  
            MyTCPHandler.cfg = self.cfg         
        elif data['opCode'] == "execute":
            del data['opCode']
            sequence = data

            program = Program(self.soc, self.cfg, sequence)
            avgi, avgq = program.acquire(self.soc, load_pulses=True, progress=False, debug=False)
            jsonDic = {"avgiRe": avgi[0][0], "avgiIm": avgi[1][0], "avgqRe": avgq[0][0],"avgqIm": avgq[1][0]}

            self.request.sendall(json.dumps(jsonDic).encode())
 
        else:
            print('Doing nothing')   



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
