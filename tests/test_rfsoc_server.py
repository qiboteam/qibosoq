import pathlib

import numpy as np
import pytest
import qick

qick.QickSoc = None
import qibosoq
from qibosoq.components.base import Parameter
from qibosoq.components.pulses import Rectangular
from qibosoq.log import define_loggers
from qibosoq.rfsoc_server import execute_program, load_pulses

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


def test_load_pulses():
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
    sequence_obj = [pulse_1, pulse_2]

    assert load_pulses(sequence) == sequence_obj


def test_execute_program(mocker, soc):
    res_array = np.array([[0, 0, 0], [1, 1, 1]])
    res = res_array, res_array
    mocker.patch("qibosoq.programs.base.BaseProgram.acquire", return_value=res)

    commands = {
        "operation_code": 1,
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

    mocker.patch("qibosoq.programs.base.BaseProgram.perform_experiment", return_value=res)
    execute_program(commands, soc)

    commands["operation_code"] = 2
    mocker.patch("qibosoq.programs.base.BaseProgram.acquire_decimated", return_value=res)
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
