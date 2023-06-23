"""Qibosoq server for qibolab-qick integration.

Tested on the following FPGA:
    * RFSoc4x2
    * ZCU111
"""

import json
import logging
import os
import socket
import traceback
from socketserver import BaseRequestHandler, TCPServer

from qick import QickSoc

import qibosoq.configuration as cfg
from qibosoq.components import Config, OperationCode, Pulse, Qubit, Sweeper
from qibosoq.programs.pulse_sequence import ExecutePulseSequence
from qibosoq.programs.sweepers import ExecuteSweeps

logger = logging.getLogger(cfg.MAIN_LOGGER_NAME)
qick_logger = logging.getLogger(cfg.PROGRAM_LOGGER_NAME)


def execute_program(data: dict, qick_soc: QickSoc) -> dict:
    """Create and execute qick programs.

    Returns:
        (dict): dictionary with two keys (i, q) to lists of values
    """
    opcode = OperationCode(data["operation_code"])
    args = ()
    if opcode is OperationCode.EXECUTE_PULSE_SEQUENCE:
        programcls = ExecutePulseSequence
    elif opcode is OperationCode.EXECUTE_PULSE_SEQUENCE_RAW:
        programcls = ExecutePulseSequence
        data["cfg"]["soft_avgs"] = data["cfg"]["reps"]
        data["cfg"]["reps"] = 1
    elif opcode is OperationCode.EXECUTE_SWEEPS:
        programcls = ExecuteSweeps
        args = tuple(Sweeper(**sweeper) for sweeper in data["sweepers"])
    else:
        raise NotImplementedError(f"Operation code {data['operation_code']} not supported")

    program = programcls(
        qick_soc,
        Config(**data["cfg"]),
        [Pulse(**pulse) for pulse in data["sequence"]],
        [Qubit(**qubit) for qubit in data["qubits"]],
        *args,
    )

    asm_prog = program.asm()
    qick_logger.handlers[0].doRollover()
    qick_logger.info(asm_prog)

    num_instructions = len(program.prog_list)
    max_mem = qick_soc["tprocs"][0]["pmem_size"]
    if num_instructions > max_mem:
        raise MemoryError(
            f"The tproc has a max memory size of {max_mem}, but the program had {num_instructions} instructions"
        )

    if opcode is OperationCode.EXECUTE_PULSE_SEQUENCE_RAW:
        results = program.acquire_decimated(
            qick_soc,
            load_pulses=True,
            progress=False,
            debug=False,
        )
        toti = [[results[0][0].tolist()]]
        totq = [[results[0][1].tolist()]]
    else:
        toti, totq = program.acquire(
            qick_soc,
            data["readouts_per_experiment"],
            load_pulses=True,
            progress=False,
            debug=False,
            average=data["average"],
        )
        toti = toti.tolist()
        totq = totq.tolist()

    return {"i": toti, "q": totq}


class ConnectionHandler(BaseRequestHandler):
    """Handle requests to the server."""

    def receive_command(self) -> dict:
        """Receive commands from qibolab client.

        The communication protocol is:
        * first the server receives  a 4 bytes integer with the length
        of the message to actually receive
        * waits for the message and decode it
        * returns the unpcikled dictionary
        """
        count = int.from_bytes(self.request.recv(4), "big")
        received = self.request.recv(count, socket.MSG_WAITALL)
        data = json.loads(received)
        return data

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
            results = execute_program(data, self.server.qick_soc)
        except Exception as exception:  # pylint: disable=bare-except, broad-exception-caught
            logger.exception("")
            logger.error("Faling command: %s", data)
            results = traceback.format_exc()
            self.server.qick_soc.reset_gens()

        self.request.sendall(bytes(json.dumps(results), "utf-8"))


def serve(host, port):
    """Open the TCPServer and wait forever for connections."""
    # initialize QickSoc object (firmware and clocks)
    TCPServer.allow_reuse_address = True
    with TCPServer((host, port), ConnectionHandler) as server:
        server.qick_soc = QickSoc(bitfile=cfg.QICKSOC_LOCATION)
        logger.info("Server listening, PID %d", os.getpid())
        server.serve_forever()
