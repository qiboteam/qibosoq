import pathlib

import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import Rectangular
from qibosoq.programs.pulse_sequence import ExecutePulseSequence


@pytest.fixture(params=[False, True])
def soc(request):
    qibosoq.configuration.IS_MULTIPLEXED = request.param
    if qibosoq.configuration.IS_MULTIPLEXED:
        file = "qick_config_multiplexed.json"
    else:
        file = "qick_config_standard.json"
    soc = qick.QickConfig(str(pathlib.Path(__file__).parent / file))

    def mock():
        pass

    soc.reset_gens = mock
    return soc


@pytest.fixture
def execute_pulse_sequence(soc):
    config = Config()
    sequence = [
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse0",
            type="drive",
            dac=3,
            adc=0,
        ),
        Rectangular(
            frequency=0,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse_flux",
            type="flux",
            dac=1,
            adc=0,
        ),
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse1",
            type="readout",
            dac=6,
            adc=0,
        ),
    ]
    qubits = [Qubit()]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    return program


def test_set_bias(soc):
    config = Config()
    sequence = [
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
        ),
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.set_bias("sweetspot")
    program.set_bias("zero")

    with pytest.raises(NotImplementedError):
        program.set_bias("test")


def test_declare_nqz_flux(soc):
    config = Config()
    sequence = [
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
        ),
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.declare_nqz_flux()


def test_find_qubit_sweetspot(soc):
    config = Config()
    sequence = [
        Rectangular(
            frequency=0,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse1",
            type="flux",
            dac=1,
            adc=0,
        ),
    ]
    qubits = [Qubit()]
    program = ExecutePulseSequence(soc, config, sequence, qubits)
    assert program.find_qubit_sweetspot(sequence[0]) == 0

    qubits = [Qubit(bias=None)]
    program = ExecutePulseSequence(soc, config, sequence, qubits)
    assert program.find_qubit_sweetspot(sequence[0]) == 0

    qubits = [Qubit(dac=None)]
    program = ExecutePulseSequence(soc, config, sequence, qubits)
    assert program.find_qubit_sweetspot(sequence[0]) == 0

    qubits = [Qubit(dac=1, bias=0.5)]
    program = ExecutePulseSequence(soc, config, sequence, qubits)
    assert program.find_qubit_sweetspot(sequence[0]) == 0.5


def test_flux_body(soc):
    config = Config()
    sequence = [
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
        ),
        Rectangular(
            frequency=0,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse_flux",
            type="flux",
            dac=1,
            adc=0,
        ),
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.body()
