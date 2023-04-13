import pickle
import signal
import socket
import sys
from datetime import datetime
from socketserver import BaseRequestHandler, TCPServer

from qick import QickSoc

from qibosoq.qick_programs import ExecutePulseSequence, ExecuteSingleSweep


def signal_handler(sig, frame):
    """Signal handling for Ctrl-C (closing the server)"""
    print("Server closing")
    sys.exit(0)


class MyTCPHandler(BaseRequestHandler):
    """Class to handle requesto to the server"""

    def handle(self):
        """This function gets called when a connection to the server is opened"""

        # print a log message when receive a connection
        now = datetime.now()
        print(f'{now.strftime("%d/%m/%Y %H:%M:%S")}\tGot connection from {self.client_address}')

        # set the server in non-blocking mode
        self.server.socket.setblocking(False)

        # receive 4 bytes (integer) with len of the pickled dictionary
        count = int.from_bytes(self.request.recv(4), "big")
        # wait for a message with len count
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


# starts handler for system interruption (ex. Ctrl-C)
signal.signal(signal.SIGINT, signal_handler)
# initialize QickSoc object (firmware and clocks)
global_soc = QickSoc()

if __name__ == "__main__":
    HOST = "192.168.0.72"  # Serverinterface address
    PORT = 6000  # Port to listen on (non-privileged ports are > 1023)
    TCPServer.allow_reuse_address = True

    with TCPServer((HOST, PORT), MyTCPHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        print("Server Listening")
        server.serve_forever()
