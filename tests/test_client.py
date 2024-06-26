import json

import numpy as np
import pytest

from qibosoq.client import (
    BufferLengthError,
    QibosoqError,
    RuntimeLoopError,
    connect,
    convert_commands,
    execute,
)
from qibosoq.components.base import Config, OperationCode, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Rectangular

return_active = True
recv_result = None


def mock_recv(obj, par):
    global return_active
    if return_active:
        res = {"i": [[[1, 2, 3]]], "q": [[[1, 2, 3]]]}
        res = json.dumps(res).encode("utf-8")

        return_active = False
        return res
    return_active = True
    return False


def mock_recv_with_result(obj, par):
    """Mock recv by providing a return string."""
    global return_active
    global recv_result
    if return_active:
        return_active = False
        return json.dumps(recv_result).encode("utf-8")
    return_active = True
    return False


def mock_connect(obj, pars):
    if not isinstance(pars[0], str):
        raise ValueError("Host type is not string.")
    if not isinstance(pars[1], int):
        raise ValueError("Port type is not int.")


def mock_send(obj, pars):
    if not isinstance(pars, bytes):
        raise ValueError("Sent message is not in bytes.")


@pytest.fixture
def server_commands():
    pulse_1 = Rectangular(
        frequency=5400,  # MHz
        amplitude=0.05,
        relative_phase=0,
        start_delay=0,
        duration=0.04,
        name="drive_pulse",
        type="drive",
        dac=0,
        adc=None,
    )
    pulse_2 = Rectangular(
        frequency=6400,  # MHz
        amplitude=0.05,
        relative_phase=0,
        start_delay=0.04,
        duration=2,
        name="readout_pulse",
        type="readout",
        dac=1,
        adc=0,
    )
    sequence = [pulse_1, pulse_2]
    config = Config()
    qubit = Qubit()

    server_commands = {
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
        "cfg": config,
        "sequence": sequence,
        "qubits": [qubit],
    }
    return server_commands


@pytest.fixture
def targ_server_commands():
    targ = {
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
        "cfg": {
            "relaxation_time": 100,
            "ro_time_of_flight": 200,
            "reps": 1000,
            "soft_avgs": 1,
            "average": True,
        },
        "sequence": [
            {
                "shape": "rectangular",
                "frequency": 5400,  # MHz
                "amplitude": 0.05,
                "relative_phase": 0,
                "start_delay": 0,
                "duration": 0.04,
                "name": "drive_pulse",
                "type": "drive",
                "dac": 0,
                "adc": None,
            },
            {
                "shape": "rectangular",
                "frequency": 6400,  # MHz
                "amplitude": 0.05,
                "relative_phase": 0,
                "start_delay": 0.04,
                "duration": 2,
                "name": "readout_pulse",
                "type": "readout",
                "dac": 1,
                "adc": 0,
            },
        ],
        "qubits": [
            {"bias": None, "dac": None},
        ],
    }
    return targ


def test_convert_commands(server_commands, targ_server_commands):
    converted = convert_commands(server_commands)
    assert targ_server_commands == converted

    server_commands["sweepers"] = [
        Sweeper(
            expts=10,
            parameters=[Parameter.AMPLITUDE],
            starts=np.array([0]),
            stops=np.array([1]),
            indexes=[0],
        )
    ]
    targ_server_commands["sweepers"] = [
        {
            "expts": 10,
            "parameters": [Parameter.AMPLITUDE],
            "starts": [0],
            "stops": [1],
            "indexes": [0],
        },
    ]
    converted = convert_commands(server_commands)
    assert targ_server_commands == converted


def test_execute(mocker, server_commands):
    mocker.patch("socket.socket.connect", new_callable=lambda: mock_connect)
    mocker.patch("socket.socket.send", new_callable=lambda: mock_send)
    mocker.patch("socket.socket.recv", new_callable=lambda: mock_recv)

    results = execute(server_commands, "0.0.0.0", 1000)

    targ = ([[[1, 2, 3]]], [[[1, 2, 3]]])
    assert results == targ


def test_connect(mocker, server_commands):
    mocker.patch("socket.socket.connect", new_callable=lambda: mock_connect)
    mocker.patch("socket.socket.send", new_callable=lambda: mock_send)
    mocker.patch("socket.socket.recv", new_callable=lambda: mock_recv)

    converted = convert_commands(server_commands)
    results = connect(converted, "0.0.0.0", 1000)

    targ = ([[[1, 2, 3]]], [[[1, 2, 3]]])
    assert results == targ


def test_exceptions(mocker, server_commands):
    global recv_result

    mocker.patch("socket.socket.connect", new_callable=lambda: mock_connect)
    mocker.patch("socket.socket.send", new_callable=lambda: mock_send)
    mocker.patch("socket.socket.recv", new_callable=lambda: mock_recv_with_result)

    converted = convert_commands(server_commands)

    recv_result = "This is an example error containing an exception in readout loop. This are just words."
    with pytest.raises(RuntimeLoopError):
        _ = connect(converted, "0.0.0.0", 1000)

    recv_result = "This is an example error containing buffer length must be 6553 samples or less. This are just words."
    with pytest.raises(BufferLengthError):
        _ = connect(converted, "0.0.0.0", 1000)

    recv_result = "This is an example error"
    with pytest.raises(QibosoqError):
        _ = connect(converted, "0.0.0.0", 1000)
