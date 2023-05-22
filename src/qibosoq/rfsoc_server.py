"""Qibosoq server for qibolab-qick integration.

Supports the following FPGA:
    * RFSoc4x2
"""

import logging
import os
import pickle
import socket
from socketserver import BaseRequestHandler, TCPServer

from qick import QickSoc

from qibosoq.qick_programs import ExecutePulseSequence, ExecuteSingleSweep

logger = logging.getLogger("__name__")
qick_logger = logging.getLogger("qick_program")


# initialize QickSoc object (firmware and clocks)
global_soc = QickSoc(bitfile="/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit")


class ConnectionHandler(BaseRequestHandler):
    """Handle requests to the server"""

    def receive_command(self) -> dict:
        """Receive commands from qibolab client

        The communication protocol is:
        * first the server receives  a 4 bytes integer with the length
        of the message to actually receive
        * waits for the message and unpickles it
        * returns the unpcikled dictionary
        """

        count = int.from_bytes(self.request.recv(4), "big")
        received = self.request.recv(count, socket.MSG_WAITALL)
        data = pickle.loads(received)
        return data

    def execute_program(self, data: dict) -> dict:
        """Creates and execute qick programs

        Returns:
            (dict): dictionary with two keys (i, q) to lists of values
        """
        if data["operation_code"] == "execute_pulse_sequence":
            program = ExecutePulseSequence(global_soc, data["cfg"], data["sequence"], data["qubits"])
        elif data["operation_code"] == "execute_single_sweep":
            program = ExecuteSingleSweep(global_soc, data["cfg"], data["sequence"], data["qubits"], data["sweeper"])
        else:
            raise NotImplementedError(f"Operation code {data['operation_code']} not supported")

        qick_logger.handlers[0].doRollover()
        qick_logger.info(program.asm())

        toti, totq = program.acquire(
            global_soc,
            data["readouts_per_experiment"],
            load_pulses=True,
            progress=False,
            debug=False,
            average=data["average"],
        )

        return {"i": toti, "q": totq}

    def handle(self):
        """Handle a connection to the server.

        * Receives command from client
        * Executes qick program
        * Return results
        """

        # set the server in non-blocking mode
        self.server.socket.setblocking(False)

        try:
            data = self.receive_command()
            results = self.execute_program(data)
        except Exception as exception:  # pylint: disable=bare-except, broad-exception-caught
            logger.exception("")
            logger.error("Faling command: %s", data)
            results = exception
            global_soc.reset_gens()

        self.request.sendall(pickle.dumps(results))


def serve(host, port):
    """Open the TCPServer and wait forever for connections"""
    TCPServer.allow_reuse_address = True
    with TCPServer((host, port), ConnectionHandler) as server:
        logger.info("Server listening, PID %d", os.getpid())
        server.serve_forever()
