import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components import Config, Pulse, Qubit
from qibosoq.qick_programs import ExecutePulseSequence, ExecuteSweeps

qibosoq.configuration.IS_MULTIPLEXED = False


@pytest.fixture
def soc():
    def mock():
        pass

    soc = qick.QickConfig("tests/qick_config.json")
    soc.reset_gens = mock
    return soc


def test_execute_pulse_sequence__init__(soc):
    config = Config()
    sequence = [
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse0",
            type="drive",
            dac=6,
            adc=0,
            shape="rectangular",
        ),
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse1",
            type="readout",
            dac=6,
            adc=0,
            shape="rectangular",
        ),
    ]
    qubits = [Qubit()]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    assert isinstance(program, ExecutePulseSequence)
