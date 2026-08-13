import pathlib

import numpy as np
import pytest
import qick

qick.QickSoc = None
import qibosoq
import qibosoq.server as server
from qibosoq.components.base import OperationCode, Parameter
from qibosoq.components.pulses import Measurement, Rectangular
from qibosoq.log import define_loggers
from qibosoq.server import execute_program, load_elements

qibosoq.configuration.MAIN_LOGGER_FILE = "/tmp/test_log_rfsoc.log"
qibosoq.configuration.PROGRAM_LOGGER_FILE = "/tmp/test_log2_rfsoc.log"

define_loggers()


@pytest.fixture
def soc():
    qibosoq.configuration.IS_MULTIPLEXED = False
    file = "qick_config_standard.json"
    soc = qick.QickConfig(str(pathlib.Path(__file__).parent / file))

    def mock():
        pass

    soc.reset_gens = mock
    return soc


@pytest.fixture
def soc_v2():
    qibosoq.configuration.IS_MULTIPLEXED = False
    file = "qick_config_v2_standard.json"
    soc = qick.QickConfig(str(pathlib.Path(__file__).parent / file))

    def mock():
        pass

    soc.reset_gens = mock
    return soc


def test_load_elements():
    sequence = [
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
        {
            "frequency": 6400,  # MHz
            "start_delay": 0.04,
            "duration": 2,
            "type": "readout",
            "dac": 1,
            "adc": 0,
        },
    ]
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
    meas = Measurement(
        type="readout",
        frequency=6400,
        start_delay=0.04,
        duration=2,
        dac=1,
        adc=0,
    )
    sequence_obj = [pulse_1, pulse_2, meas]

    assert load_elements(sequence) == sequence_obj


def test_execute_program(mocker, soc):
    server.TPROC_VERSION = 1
    res_array = np.array([[0, 0, 0], [1, 1, 1]])
    res = res_array, res_array

    commands = {
        "operation_code": 1,
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
            {"bias": 0.0, "dac": None},
        ],
    }

    mocker.patch(
        "qibosoq.programs.base.BaseProgram.perform_experiment", return_value=res
    )
    execute_program(commands, soc)

    commands["operation_code"] = 2
    mocker.patch(
        "qick.averager_program.AveragerProgram.acquire_decimated",
        return_value=res,
    )
    execute_program(commands, soc)

    commands["sweepers"] = [
        {
            "expts": 10,
            "parameters": [Parameter.AMPLITUDE],
            "starts": [0],
            "stops": [1],
            "indexes": [0],
        },
    ]
    commands["operation_code"] = 3
    execute_program(commands, soc)

    soc["tprocs"][0]["pmem_size"] = 10
    with pytest.raises(MemoryError):
        execute_program(commands, soc)


def test_execute_program_v2(mocker, soc_v2):
    server.TPROC_VERSION = 2
    res_array = np.array([[0, 0, 0], [1, 1, 1]])
    res = res_array.tolist(), res_array.tolist()

    commands = {
        "operation_code": 1,
        "cfg": {
            "reps": 1000,
            "final_delay": 100,
            "final_wait": 0,
            "initial_delay": 1,
            "reps_innermost": False,
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
            {"bias": 0.0, "dac": None},
        ],
    }

    mocker.patch(
        "qibosoq.programs.base.BaseProgramV2.perform_experiment", return_value=res
    )
    execute_program(commands, soc_v2)

    commands["operation_code"] = 2
    mocker.patch(
        "qick.asm_v2.AveragerProgramV2.acquire_decimated",
        return_value=[np.array([[1, 2], [3, 4]])],
    )
    execute_program(commands, soc_v2)

    commands["sweepers"] = [
        {
            "expts": 10,
            "parameters": [Parameter.AMPLITUDE],
            "starts": [0],
            "stops": [1],
            "indexes": [0],
        },
    ]
    commands["operation_code"] = 3
    execute_program(commands, soc_v2)


@pytest.mark.parametrize(
    "sweepers, message",
    [
        (None, "Missing 'sweepers' payload for EXECUTE_SWEEPS."),
        ([], "'sweepers' must be a non-empty list for EXECUTE_SWEEPS."),
        ([{"expts": 10}], "is missing keys"),
        (
            [
                {
                    "expts": 0,
                    "parameters": [Parameter.AMPLITUDE],
                    "starts": [0],
                    "stops": [1],
                    "indexes": [0],
                }
            ],
            "invalid 'expts'",
        ),
        (
            [
                {
                    "expts": 10,
                    "parameters": [Parameter.AMPLITUDE],
                    "starts": [0],
                    "stops": [1],
                    "indexes": [],
                }
            ],
            "cannot have empty fields.",
        ),
        (
            [
                {
                    "expts": 10,
                    "parameters": [Parameter.AMPLITUDE],
                    "starts": [0, 1],
                    "stops": [1],
                    "indexes": [0],
                }
            ],
            "inconsistent field lengths",
        ),
    ],
)
@pytest.mark.parametrize("tproc_version", [1, 2])
def test_execute_program_sweep_payload_validation(sweepers, message, tproc_version):
    server.TPROC_VERSION = tproc_version
    cfg = (
        {
            "relaxation_time": 100,
            "ro_time_of_flight": 200,
            "reps": 1000,
            "soft_avgs": 1,
            "average": True,
        }
        if tproc_version == 1
        else {
            "reps": 1000,
            "final_delay": 100,
            "final_wait": 0,
            "initial_delay": 1,
            "reps_innermost": False,
        }
    )

    commands = {
        "operation_code": OperationCode.EXECUTE_SWEEPS,
        "cfg": cfg,
        "sequence": [
            {
                "shape": "rectangular",
                "frequency": 5400,
                "amplitude": 0.05,
                "relative_phase": 0,
                "start_delay": 0,
                "duration": 0.04,
                "name": "drive_pulse",
                "type": "drive",
                "dac": 0,
                "adc": None,
            }
        ],
        "qubits": [{"bias": 0.0, "dac": None}],
    }

    if sweepers is not None:
        commands["sweepers"] = sweepers

    with pytest.raises(ValueError, match=message):
        execute_program(commands, None)
