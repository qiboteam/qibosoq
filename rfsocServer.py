import json
import signal
import sys

from socketserver import BaseRequestHandler, TCPServer
from qick import QickSoc

from ExecutePulseSequence import ExecutePulseSequence

import ExecuteSweep


def signal_handler(sig, frame):
    """Signal handling for Ctrl-C (closing the server)"""
    print('Server closing')
    sys.exit(0)


# starts the handler
signal.signal(signal.SIGINT, signal_handler)


class MyTCPHandler(BaseRequestHandler):
    """
    The request handler class for our server.
    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    cfg = {}
    soc = QickSoc()

    def handle(self):
        self.server.socket.setblocking(False)
        print('Got connection from', self.client_address)
        # self.request is the TCP socket connected to the client

        json_received = self.request.recv(2048)
        data = json.loads(json_received)

        print(f'Decoded data with opcode {data["opCode"]}')
        print(f'Data: {data}')

        if data['opCode'] == "setup":
            MyTCPHandler.cfg = data
        elif data['opCode'] == "execute":

            MyTCPHandler.cfg["hardware_avg"] = data["nshots"]
            if data["relaxation_time"] is not None:
                MyTCPHandler.cfg["repetition_duration"] = data["relaxation_time"]

            pulses = data["pulses"]
            if self.check_1_ro_pulse(pulses):

                program = ExecutePulseSequence(MyTCPHandler.soc,
                                               MyTCPHandler.cfg,
                                               data)
                avgi, avgq = program.acquire(MyTCPHandler.soc,
                                             load_pulses=True,
                                             progress=False,
                                             debug=False)

                last_pulse = data['pulses'][list(data['pulses'])[-1]]
                jsonDic = {
                        "serial": last_pulse["serial"],
                        "avgi": avgi[0][0],
                        "avgq": avgq[0][0]
                }
            else:
                raise NotImplementedError("Only one readout pulse is supported.")

            print('Sending results')
            self.request.sendall(json.dumps(jsonDic).encode())

        elif data['opCode'] == "sweep":

            MyTCPHandler.cfg["hardware_avg"] = data["nshots"]
            if data["relaxation_time"] is not None:
                MyTCPHandler.cfg["repetition_duration"] = data["relaxation_time"]

            del data['opCode']
            sequence = data["pulses"]
            parameter = data.pop('parameter')

            if self.check_1_ro_pulse(sequence):

                program = ExecuteSweep(MyTCPHandler.soc,
                                       MyTCPHandler.cfg,
                                       parameter,
                                       data['pulses'],
                                       data['range'])
                expt_pts, avg_di, avg_dq = program.acquire(MyTCPHandler.soc,
                                                           load_pulses=True,
                                                           progress=True,
                                                           debug=False)

                last_pulse = sequence[list(sequence)[-1]]
                jsonDic = {
                        "serial": last_pulse["serial"],
                        "avg_di": avg_di[0][0].tolist(),
                        "avg_dq": avg_dq[0][0].tolist()
                }
            else:
                raise NotImplementedError("Only one readout pulse is supported.")

            print('Sending results')
            self.request.sendall(json.dumps(jsonDic).encode())

        else:
            print('Doing nothing')

    def check_1_ro_pulse(self, pulses):
        count_ro = 0
        for i, pulse in enumerate(pulses):
            p = pulses[pulse]
            if p["type"] == "ro":
                count_ro += 1
        return count_ro == 1


if __name__ == "__main__":
    HOST = "192.168.2.72"  # Serverinterface address
    PORT = 6001  # Port to listen on (non-privileged ports are > 1023)
    TCPServer.allow_reuse_address = True
    # Create the server, binding to localhost on port 6000
    with TCPServer((HOST, PORT), MyTCPHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        print("Server Listening")
        server.serve_forever()
