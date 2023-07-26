"""Collection of helper functions for qibosoq clients."""

import json
import socket
from dataclasses import asdict
from typing import Tuple


class QibosoqError(RuntimeError):
    """Exception raised when qibosoq server encounters an error.

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
            raise QibosoqError(results)
        return results["i"], results["q"]


def convert_commands(obj_dictionary: dict) -> dict:
    """Convert the contents of a commands dictionary from object to dict."""
    dict_dictionary = {
        "operation_code": obj_dictionary["operation_code"],
        "cfg": asdict(obj_dictionary["cfg"]),
        "sequence": [asdict(pulse) for pulse in obj_dictionary["sequence"]],
        "qubits": [asdict(qubit) for qubit in obj_dictionary["qubits"]],
    }
    if "sweepers" in obj_dictionary:
        dict_dictionary["sweepers"] = [sweep.serialized for sweep in obj_dictionary["sweepers"]]
    return dict_dictionary


def execute(obj_dictionary: dict, host: str, port: int) -> Tuple[list, list]:
    """Convert a dictionary of objects and run experiment."""
    server_commands = convert_commands(obj_dictionary)
    return connect(server_commands, host, port)
