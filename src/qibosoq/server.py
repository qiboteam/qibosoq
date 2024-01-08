"""Qibosoq server for qibolab-qick integration."""

import json
import logging
import os
import socket
import traceback
from socketserver import BaseRequestHandler, TCPServer
from typing import Dict, List

import numpy as np
from qick import QickSoc

import qibosoq.configuration as cfg
from qibosoq.components.base import Config, OperationCode, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Element, Measurement, Shape
from qibosoq.programs.pulse_sequence import ExecutePulseSequence
from qibosoq.programs.sweepers import ExecuteSweeps

logger = logging.getLogger(cfg.MAIN_LOGGER_NAME)
qick_logger = logging.getLogger(cfg.PROGRAM_LOGGER_NAME)


def load_elements(list_sequence: List[Dict]) -> List[Element]:
    """Convert a list of elements in dict form to a list of Pulse objects."""
    obj_sequence = []
    for element in list_sequence:
        if "amplitude" in element:  # if element is a pulse
            cls = Shape[element["shape"].upper()].value
            converted_pulse = cls(**element)
            obj_sequence.append(converted_pulse)
        else:  # if element is a measurement
            obj_sequence.append(Measurement(**element))
    return obj_sequence


def load_sweeps(list_sweepers: List[Dict]) -> List[Sweeper]:
    """Convert a list of sweepers (in dict form) to a list of Sweeper objects."""
    sweepers = []
    for sweep in list_sweepers:
        converted_sweep = Sweeper(
            expts=sweep["expts"],
            parameters=[Parameter(par) for par in sweep["parameters"]],
            starts=np.array(sweep["starts"]),
            stops=np.array(sweep["stops"]),
            indexes=sweep["indexes"],
        )
        sweepers.append(converted_sweep)
    return sweepers


def execute_program(data: dict, qick_soc: QickSoc) -> dict:
    """Create and execute qick programs.

    Returns:
        (dict): dictionary with two keys (i, q) to lists of values
    """
    opcode = OperationCode(data["operation_code"])
    args = []
    soft_avgs = 1
    if opcode is OperationCode.EXECUTE_PULSE_SEQUENCE:
        programcls = ExecutePulseSequence
    elif opcode is OperationCode.EXECUTE_PULSE_SEQUENCE_RAW:
        programcls = ExecutePulseSequence
        soft_avgs = data["cfg"]["reps"]
        data["cfg"]["reps"] = 1
    elif opcode is OperationCode.EXECUTE_SWEEPS:
        programcls = ExecuteSweeps
        args = load_sweeps(data["sweepers"])
    else:
        raise NotImplementedError(
            f"Operation code {data['operation_code']} not supported"
        )

    program = programcls(
        qick_soc,
        Config(**data["cfg"]),
        load_elements(data["sequence"]),
        [Qubit(**qubit) for qubit in data["qubits"]],
        *args,
    )

    asm_prog = program.asm()
    qick_logger.handlers[0].doRollover()  # type: ignore
    qick_logger.info(asm_prog)

    num_instructions = len(program.prog_list)
    max_mem = qick_soc["tprocs"][0]["pmem_size"]
    if num_instructions > max_mem:
        raise MemoryError(
            f"The tproc has a max memory size of {max_mem}, "
            f"but the program had {num_instructions} instructions"
        )

    if opcode is OperationCode.EXECUTE_PULSE_SEQUENCE_RAW:
        program.soft_avgs = soft_avgs
        results = program.acquire_decimated(  # pylint: disable=E1120
            qick_soc,
            load_pulses=True,
            progress=False,
        )
        toti = [[results[0][0].tolist()]]
        totq = [[results[0][1].tolist()]]
    else:
        toti, totq = program.perform_experiment(
            qick_soc,
            average=data["cfg"]["average"],
        )

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
        except Exception:  # pylint: disable=W0612,W0718
            logger.exception("")
            logger.error("Faling command: %s", data)
            results = traceback.format_exc()
            self.server.qick_soc.reset_gens()

        self.request.sendall(bytes(json.dumps(results), "utf-8"))


def log_initial_info():
    """Log info regarding the loaded configuration."""
    logger.info("Server listening, PID %d", os.getpid())
    mux_str = "Multiplexed" if cfg.IS_MULTIPLEXED else "Not multiplexed"
    logger.info("%s firmware loaded from %s", mux_str, cfg.QICKSOC_LOCATION)


def serve(host, port):
    """Open the TCPServer and wait forever for connections."""
    # initialize QickSoc object (firmware and clocks)
    TCPServer.allow_reuse_address = True
    with TCPServer((host, port), ConnectionHandler) as server:
        server.qick_soc = QickSoc(bitfile=cfg.QICKSOC_LOCATION)
        log_initial_info()
        server.serve_forever()
