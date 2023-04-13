"""Qibosoq server for qibolab-qick integration.

Supports the following FPGA:
    * RFSoc4x2
"""

import pickle
import signal
import socket
import sys
from datetime import datetime
from socketserver import BaseRequestHandler, TCPServer

from qick import QickSoc

from qibosoq.qick_programs import ExecutePulseSequence, ExecuteSingleSweep

# initialize QickSoc object (firmware and clocks)
global_soc = QickSoc()
# starts handler for system interruption (ex. Ctrl-C)
signal.signal(signal.SIGINT, signal_handler)


class MyTCPHandler(BaseRequestHandler):
    """Class to handle requests to the server"""

    def handle(self):
        """Gets called when a connection to the server is opened.

        Logs the time of the connection and the client IP.
        The communication protocol is:
        * first the server receives  a 4 bytes integer with the length
        of the message to actually receive
        * waits for the message and unpickles it
        * execute the program depending on the op_code
        * returns a pickled dictionary of results to the client
        """
        # print a log message when receive a connection
        now = datetime.now()
        print(f'{now.strftime("%d/%m/%Y %H:%M:%S")}\tGot connection from {self.client_address}')

        # set the server in non-blocking mode
        self.server.socket.setblocking(False)

        count = int.from_bytes(self.request.recv(4), "big")
        received = self.request.recv(count, socket.MSG_WAITALL)
        data = pickle.loads(received)

        if data["operation_code"] == "execute_pulse_sequence":
            program = ExecutePulseSequence(global_soc, data["cfg"], data["sequence"], data["qubits"])
        elif data["operation_code"] == "execute_single_sweep":
            program = ExecuteSingleSweep(global_soc, data["cfg"], data["sequence"], data["qubits"], data["sweeper"])
        else:
            raise NotImplementedError(f"Operation code {data['operation_code']} not supported")

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


def signal_handler(sig, frame):
    """Signal handling for Ctrl-C (closing the server)"""
    print("Server closing")
    sys.exit(0)
