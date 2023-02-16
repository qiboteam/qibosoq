# rfsocServer.py
from socketserver import BaseRequestHandler, TCPServer
import numpy as np
#from pynq import Overlay

import time
from qick import AveragerProgram, QickSoc, RAveragerProgram
import json
######################################################
#
class ProgramExecute(AveragerProgram):
#
######################################################

    def __init__(self, soc, cfg, sequence):    
        MU = 0.000001   
        self.sequence = sequence
        self.soc = soc
        self.cfg = cfg
        self.max_gain = self.cfg["max_gain"]
        #ro_duration = self.cfg["MZ"]["duration"]* 0.001
        #ro_amplitude = self.cfg["MZ"]["amplitude"]


        # HW configuration
        self.ro_channel = 0 #self.cfg["ports"]["o0"]["channel"] 
        self.qd_channel = 1 #self.cfg["ports"]["o1"]["channel"] 
        self.ro_input_channel = 0 #self.cfg["ports"]["i0"]["channel"] 

        # Readout configuration
        self.ro_freq = self.cfg["ro_frequency"]* MU
        ro_duration = self.cfg["ro_duration"]* 0.001
        #ro_amplitude = self.cfg["MZ"]["amplitude"]  
        #self.ro_gain = int( ro_amplitude * self.max_gain)      
        self.ro_length = self.soc.us2cycles(ro_duration , gen_ch=self.ro_channel) # conver pulse lengths to clock ticks
        self.res_phase = self.cfg["resonator_phase"]
        self.add_trig_offset = self.cfg["adc_trig_offset"]

        # Qubit configuration
        #self.qd_freq = self.cfg["RX"]["frequency"] * MU


        # Experiment
        cfg["reps"] = self.cfg["hardware_avg"]
        self.relax_delay = self.cfg["relax_delay"]
        self.delay_before_readout = 0
        super().__init__(soc, cfg)
 

    def initialize(self):

        MU = 0.000001

        self.declare_gen(ch=self.ro_channel, nqz=2) # Readout
        self.declare_gen(ch=self.qd_channel, nqz=2) # Qubit
        self.drive_pulses = False
        # configure the readout lengths and downconversion frequencies
        #for ch in [0, 1]:
        #    self.declare_readout(ch=ch, length=self.ro_length, freq= self.ro_freq , gen_ch=self.ro_channel)
        self.declare_readout(ch=self.ro_input_channel, length=self.ro_length, freq= self.ro_freq , gen_ch=self.ro_channel)

        # add qubit and readout pulses to respective channels

    
        #self.ro_frequency = self.soc.freq2reg(self.ro_freq  , gen_ch=self.ro_channel, ro_ch=0)  
    
        for i, pulse in enumerate(self.sequence):
            p = self.sequence[pulse]
            if p["type"] == 'qd':
                self.drive_pulses = True  
                self.qd_gain = int(p["amplitude"] * self.max_gain)
                duration = self.soc.us2cycles(p["duration"]*0.001, gen_ch=1)  
                sigma = self.soc.us2cycles(p["duration"]*0.001/p["rel_sigma"], gen_ch=1)
                # convert frequencies to dac register value  
                self.qd_frequency = self.soc.freq2reg(p["frequency"], gen_ch=self.qd_channel)
                if p['shape'] == "Gaussian":   
                    self.add_gauss(ch=self.qd_channel, name="Gaussian", sigma=sigma, length=duration )
                    
                    self.set_pulse_registers(
                        ch=self.qd_channel,
                        style="arb",
                        freq= self.qd_frequency ,
                        phase= self.deg2reg(self.res_phase, gen_ch=self.qd_channel), #int(p["relative_phase"]),
                        gain= self.qd_gain,
                        waveform="Gaussian"
                        )

                elif p['shape'] == "Drag":          
                    self.add_DRAG(ch=self.qd_channel, name="Drag", sigma=sigma, 
                        length=duration, delta=sigma, alpha = p["beta"] )
                    
                    self.set_pulse_registers(
                        ch=self.qd_channel,
                        style="arb",
                        freq= self.qd_frequency ,
                        phase= int(p["relative_phase"]),
                        gain= self.qd_gain,
                        waveform="Drag"
                        )       
                print("amplitude, frecuencia drive, duracion y sigma: ",self.qd_gain, self.qd_frequency,  duration, sigma, self.qd_gain)   

            elif p["type"] == 'ro':
                freq=self.freq2reg(p["frequency"], gen_ch=self.ro_channel, ro_ch=0)
                self.delay_before_readout = self.soc.us2cycles(p["start"]*0.001)
                self.set_pulse_registers(
                    ch=self.ro_channel,
                    style="const",
                    freq=freq,                  
                    phase= int(p["relative_phase"]), 
                    gain= int(p["amplitude"]*self.max_gain),
                    length= self.ro_length
                    )

     
        
        self.synci(200)

    def body(self):
        # play drive pulse
        if self.drive_pulses:
            self.pulse(ch=self.qd_channel)
        # align channels and wait some time (defined in the runcard)
        self.sync_all(self.delay_before_readout)

        # trigger measurement, play measurement pulse, wait for qubit to relax
        self.measure(pulse_ch=self.ro_channel, 
            #adcs=[0, 1], 
            adcs=[0],
            adc_trig_offset = self.add_trig_offset,
            wait=True, 
            syncdelay=self.us2cycles(self.cfg["relax_delay"]))


######################################################
#
class ProgramSweepFreq(RAveragerProgram):
#
######################################################
    def __init__(self, soc, cfg, sequence, range): 

 
        MHz = 0.000001  
        mu_s = 0.001
        self.soc = soc
        self.cfg = cfg
        self.max_gain = self.cfg["max_gain"]
        self.start = range['start']* MHz
        self.step = range['step']  *MHz      
        self.expt = range['expt']
        # HW configuration
        self.ro_channel = 0 
        self.qd_channel = 1 
        self.ro_input_channel = 0 

        # Readout configuration
        self.ro_freq = self.cfg["ro_frequency"]* MHz
        ro_duration = self.cfg["ro_duration"]* mu_s     
        self.ro_length = self.soc.us2cycles(ro_duration , gen_ch=self.ro_channel) # conver pulse lengths to clock ticks
        self.res_phase = self.cfg["resonator_phase"]
        self.add_trig_offset = self.cfg["adc_trig_offset"]
        self.ro_gain = self.cfg['ro_gain']

        # Qubit configuration
        self.qubit_gain = int(sequence['0']['amplitude'] * self.max_gain)  
        self.probe_length = sequence['0']['duration'] * mu_s   

 

        # Experiment
        cfg["reps"] = self.cfg["hardware_avg"]
        cfg['expts'] = self.expt
        cfg['start'] = self.start
        cfg['step'] = self.step
        self.relax_delay = self.cfg["relax_delay"]
        self.delay_before_readout = 0
        super().__init__(soc, cfg)

    def initialize(self):
        #cfg=self.cfg
        
        self.declare_gen(ch=self.ro_channel, nqz=2) #Readout
        self.declare_gen(ch=self.qd_channel, nqz=2) #Qubit

        self.declare_readout(ch=self.ro_input_channel, length=self.ro_length, freq= self.ro_freq , gen_ch=self.ro_channel)


        self.q_rp=self.ch_page(self.qd_channel)     # get register page for qubit_ch
        self.r_freq=self.sreg(self.qd_channel, "freq")   # get frequency register for qd_ch    
        
        f_res=self.freq2reg(self.ro_freq, gen_ch=self.ro_channel, ro_ch=self.ro_input_channel) # conver ro_freq to dac register value

        self.f_start =self.freq2reg(self.start, gen_ch= self.qd_channel)  # get start/step frequencies
        self.f_step =self.freq2reg(self.step, gen_ch=self.qd_channel)

        # add qubit and readout pulses to respective channels
        self.set_pulse_registers(ch=self.qd_channel, style="const", freq=self.f_start, phase=0, gain=self.qubit_gain, 
                                 length=  self.probe_length)
        self.set_pulse_registers(ch=self.ro_channel, style="const", freq=f_res, phase=self.res_phase, gain=self.ro_gain, 
                                 length=self.ro_length)
        
        self.sync_all(self.us2cycles(1))
    
    def body(self):
        self.pulse(ch=self.qd_channel)  #play probe pulse
        self.sync_all(self.us2cycles(0.05)) # align channels and wait 50ns

        #trigger measurement, play measurement pulse, wait for qubit to relax
        self.measure(pulse_ch=self.ro_channel, 
             adcs=[self.ro_input_channel],
             adc_trig_offset=self.add_trig_offset,
             wait=True,
             syncdelay=self.us2cycles(self.cfg["relax_delay"]))

    def update(self): 
        self.mathi(self.q_rp, self.r_freq, self.r_freq, '+', self.f_step) # update frequency list index
 


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
            program = ProgramExecute(MyTCPHandler.soc, MyTCPHandler.cfg, sequence)
            avgi, avgq = program.acquire(MyTCPHandler.soc, load_pulses=True, progress=False, debug=False)
            jsonDic = {"avgi": avgi[0][0], "avgq": avgq[0][0]}
            self.request.sendall(json.dumps(jsonDic).encode())
        elif data['opCode'] == "sweep":
            del data['opCode']
            parameter = data.pop('parameter')  
            if parameter == "Parameter.frequency":               
                program = ProgramSweepFreq(MyTCPHandler.soc, MyTCPHandler.cfg, data['pulses'], data['range'])
                expt_pts, avg_di, avg_dq = program.acquire(MyTCPHandler.soc,load_pulses=True,progress=False, debug=False)
                jsonDic =  {"avg_di": avg_di[0][0].tolist(), "avg_dq": avg_dq[0][0].tolist()}
                print(f'Check point 354: {jsonDic}') 
                self.request.sendall(json.dumps(jsonDic).encode())
            elif parameter == 'Parameter.amplitude':
                program = ProgramSweepAmp(MyTCPHandler.soc, MyTCPHandler.cfg, data.values)
            else:
                sequence = data['pulses']
                program = ProgramExecute(MyTCPHandler.soc, MyTCPHandler.cfg, sequence)
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
