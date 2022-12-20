# rfsocServer.py
from socketserver import BaseRequestHandler, TCPServer
import numpy as np
#from pynq import Overlay

import time
from qick import AveragerProgram, QickSoc
import json
######################################################
#
class Program(AveragerProgram):
#
######################################################

    def __init__(self, soc, cfg, sequence):    
        MU = 0.000001   
        self.sequence = sequence
        self.soc = soc
        self.cfg = cfg
        self.max_gain = self.cfg["max_gain"]


        # HW configuration
        self.ro_channel = self.cfg["res_ch"] 
        self.qd_channel = self.cfg["qubit_ch"]

        # Readout configuration
        self.cfg["f_res"] = self.cfg["resonator_freq"] * MU
        self.ro_freq = self.cfg["f_res"]
        self.ro_length = self.soc.us2cycles(self.cfg["readout_length"]* 0.001 , gen_ch=self.ro_channel) # conver pulse lengths to clock ticks
        self.res_phase = self.cfg["resonator_phase"]
        self.add_trig_offset = self.cfg["adc_trig_offset"]
        self.ro_gain = int(self.cfg["resonator_gain"] * self.max_gain)
        self.cfg["res_gain"] = self.ro_gain

        # Qubit configuration
        self.cfg["f_ge"]= self.cfg["qubit_freq"] * MU
        self.qd_freq = self.cfg["f_ge"]
        self.qd_length = self.soc.us2cycles(4*self.cfg["sigma"]* 0.001 , gen_ch=self.qd_channel)    # conver pulse lengths to clock ticks    
        self.qd_gain = self.cfg["pi_gain"] * self.max_gain

        # Experiment
        self.cfg["reps"] = self.cfg["hardware_avg"]
        self.relax_delay = self.cfg["relax_delay"]




        super().__init__(soc, cfg)
 

    def initialize(self):
        MU = 0.000001
        self.cfg["f_res"] = self.cfg["resonator_freq"] * MU
        self.cfg["f_ge"]= self.cfg["qubit_freq"] * MU
        self.qd_freq = self.cfg["f_ge"]
        self.ro_freq = self.cfg["f_res"]
        self.declare_gen(ch=self.ro_channel, nqz=2) # Readout
        self.declare_gen(ch=self.qd_channel, nqz=2) # Qubit
        self.drive_pulses = False
        # configure the readout lengths and downconversion frequencies
        for ch in [0, 1]:
            self.declare_readout(ch=ch, length=self.ro_length, freq= self.ro_freq , gen_ch=self.ro_channel)

        # add qubit and readout pulses to respective channels

        # convert frequencies to dac register value  
        self.qd_frequency = self.soc.freq2reg(self.qd_freq, gen_ch=self.qd_channel)
        self.ro_frequency = self.soc.freq2reg(self.ro_freq  , gen_ch=self.ro_channel, ro_ch=0)  
        #print("Readout freq: ",self.ro_freq , "Readout Gain: ", self.ro_gain)
        for i, pulse in enumerate(self.sequence):
            p = self.sequence[pulse]
            if p["channel"] == 1:
                self.drive_pulses = True    
                if p['shape'] == "Gaussian":          
                    sigma = self.soc.us2cycles(p["rel_sigma"]*0.001, gen_ch=1)
                    duration = self.soc.us2cycles(p["duration"]*0.001, gen_ch=1)
                    self.add_gauss(ch=self.qd_channel, name="Gaussian", sigma=sigma, length=duration )
                    
                    self.set_pulse_registers(
                        ch=self.qd_channel,
                        style="arb",
                        freq= self.qd_frequency ,
                        phase= int(p["relative_phase"]),
                        gain= int(p["amplitude"] * self.max_gain),
                        waveform="Gaussian"
                        )

                elif p['shape'] == "Drag":          
                    sigma = self.soc.us2cycles(p["rel_sigma"]*0.001, gen_ch=1)
                    duration = self.soc.us2cycles(p["duration"]*0.001, gen_ch=1)
                    self.add_DRAG(ch=self.qd_channel, name="Drag", sigma=sigma, length=duration,delta=20.0, alpha = p["beta"] )
                    
                    self.set_pulse_registers(
                        ch=self.qd_channel,
                        style="arb",
                        freq= self.qd_frequency ,
                        phase= int(p["relative_phase"]),
                        gain= int(p["amplitude"] * self.max_gain),
                        waveform="Drag"
                        )        
                print("Drive Pulse: ",i,  p)   
                
            elif p["channel"] == 0:
                freq=self.freq2reg(self.ro_freq, gen_ch=self.ro_channel, ro_ch=0) 
                self.set_pulse_registers(
                    ch=self.ro_channel,
                    style="const",
                    freq=self.ro_frequency,                  
                    phase= int(p["relative_phase"]), 
                    gain= int(self.ro_gain),
                    length= self.ro_length
                    )
                print("Readout Pulse: ",i,  p)   
     
        
        self.synci(200)

    def body(self):

        delay_before_readout = self.soc.us2cycles(0.05)

        # play drive pulse
        if self.drive_pulses:
            self.pulse(ch=self.qd_channel)
        # align channels and wait some time (defined in the runcard)
        self.sync_all(delay_before_readout)

        # trigger measurement, play measurement pulse, wait for qubit to relax

        self.measure(pulse_ch=self.ro_channel, 
            adcs=[0, 1], 
            adc_trig_offset = self.add_trig_offset,
            wait=True, 
            syncdelay=self.us2cycles(self.cfg["relax_delay"]))

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
    
    #def __init__(self, request, client_address, server):
    #    super().__init__(request, client_address, server)

    def handle(self):
         
        sequence = {}
        print('Got connection from', self.client_address)
        # self.request is the TCP socket connected to the client

        jsonReceived = self.request.recv(2048)

        data = json.loads(jsonReceived.decode('utf-8'))

        if data['opCode'] == "setup":
            MyTCPHandler.cfg = data     
        elif data['opCode'] == "execute":
            del data['opCode']
            sequence = data
            program = Program(MyTCPHandler.soc, MyTCPHandler.cfg, sequence)
            avgi, avgq = program.acquire(MyTCPHandler.soc, load_pulses=True, progress=False, debug=False)
            jsonDic = {"avgi": avgi[0][0], "avgq": avgq[0][0]}
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
