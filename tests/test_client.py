import json

import pytest

from qibosoq.client import connect, convert_commands, execute
from qibosoq.components.base import Config, OperationCode, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Rectangular

return_active = True


def mock_recv(obj, par):
    global return_active
    if return_active:
        res = {"i": [[[1, 2, 3]]], "q": [[[1, 2, 3]]]}
        res = json.dumps(res).encode("utf-8")

        return_active = False
        return res
    else:
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
            "repetition_duration": 100,
            "adc_trig_offset": 200,
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
                "bias": None,
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
                "bias": None,
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
            starts=[0],
            stops=[1],
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
