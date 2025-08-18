"""Collection of helper functions for qibosoq clients."""

import json
import re
import socket
from dataclasses import asdict
from typing import List, Tuple

from qibosoq.components.base import Parameter


class QibosoqError(RuntimeError):
    """Exception raised when qibosoq server encounters an error.

    Attributes:
    message -- The error message received from the server (qibosoq)
    """


class RuntimeLoopError(QibosoqError):
    """Exception raised when qibosoq server encounters a readout loop error.

    Attributes:
    message -- The error message received from the server (qibosoq)
    """


class BufferLengthError(QibosoqError):
    """Exception raised when qibosoq server tries to allocate too large pulses.

    Attributes:
    message -- The error message received from the server (qibosoq)
    """


def connect(server_commands: dict, host: str, port: int) -> Tuple[list, list]:
    """Open a connection with the server and executes the commands."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        msg_encoded = bytes(json.dumps(server_commands), "utf-8")

        # send the length of the encoded dictionry before the dict itself
        sock.send(len(msg_encoded).to_bytes(4, "big"))
        sock.send(msg_encoded)

        # receive and decode the results
        received = bytearray()
        while True:
            tmp = sock.recv(4096)
            if not tmp:
                break
            received.extend(tmp)
        results = json.loads(received.decode("utf-8"))
        if isinstance(results, str):
            if "exception in readout loop" in results:
                raise RuntimeLoopError(results)
            buffer_overflow = r"buffer length must be \d+ samples or less"
            if re.search(buffer_overflow, results) is not None:
                raise BufferLengthError(results)
            raise QibosoqError(results)
        return results["i"], results["q"]


def convert_commands(obj_dictionary: dict) -> dict:
    """Convert the contents of a commands dictionary from object to dict."""
    dict_dictionary = {
        "operation_code": obj_dictionary["operation_code"],
        "cfg": asdict(obj_dictionary["cfg"]),
        "sequence": [asdict(element) for element in obj_dictionary["sequence"]],
        "qubits": [asdict(qubit) for qubit in obj_dictionary["qubits"]],
    }
    if "sweepers" in obj_dictionary:
        dict_dictionary["sweepers"] = [
            sweep.serialized for sweep in obj_dictionary["sweepers"]
        ]
        check_valid_swept_seq(obj_dictionary["sweepers"], obj_dictionary["sequence"])

    return dict_dictionary


def check_valid_swept_seq(sweepers: List, sequence: List):
    """Check if the swept sequence is swept.

    In sweepers all the pulses are registered in initialization (before loop)
    this means that if the same DAC has multiple values (pulses) they get overwritten
    """
    for sweeper in sweepers:
        pars = [par for par in sweeper.parameters if par is not Parameter.DELAY]
        if len(pars) > 0:
            idxs = [pulse.dac for pulse in sequence]
            if len(idxs) > len(set(idxs)):
                raise RuntimeError("In sweepers, DAC must be uniquely used.")


def execute(obj_dictionary: dict, host: str, port: int) -> Tuple[list, list]:
    """Convert a dictionary of objects and run experiment."""
    server_commands = convert_commands(obj_dictionary)
    return connect(server_commands, host, port)
