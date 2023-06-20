import pathlib

import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components import Config, Parameter, Pulse, Qubit, Sweeper
from qibosoq.qick_programs import ExecutePulseSequence, ExecuteSweeps


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
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse0",
            type="drive",
            dac=3,
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
    return program


@pytest.fixture
def execute_sweeps(soc):
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
            dac=3,
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
    sweepers = (
        Sweeper(expts=1000, parameters=[Parameter.FREQUENCY], starts=[0], stops=[100], indexes=[0]),
        Sweeper(expts=1000, parameters=[Parameter.AMPLITUDE], starts=[0], stops=[100], indexes=[0]),
        Sweeper(expts=1000, parameters=[Parameter.RELATIVE_PHASE], starts=[0], stops=[100], indexes=[0]),
    )

    qubits = [Qubit()]

    program = ExecuteSweeps(soc, config, sequence, qubits, sweepers)
    return program


def test_execute_sweeps_init(execute_sweeps):
    assert isinstance(execute_sweeps, ExecuteSweeps)


def test_execute_pulsesequence_init(execute_pulse_sequence):
    assert isinstance(execute_pulse_sequence, ExecutePulseSequence)


def test_declare_nqz_zones(execute_pulse_sequence):
    sequence = [
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse0",
            type="drive",
            dac=3,
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
    execute_pulse_sequence.declare_nqz_zones(sequence)


def test_declare_readout_freq(execute_pulse_sequence):
    execute_pulse_sequence.declare_readout_freq()


def test_add_pulse_to_register(execute_pulse_sequence):
    pulse0 = Pulse(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start=0,
        duration=0.04,
        name="pulse0",
        type="drive",
        dac=3,
        adc=0,
        shape="gaussian",
        rel_sigma=5,
    )
    pulse1 = Pulse(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start=0,
        duration=0.04,
        name="pulse1",
        type="drive",
        dac=3,
        adc=0,
        shape="drag",
        rel_sigma=5,
        beta=0.1,
    )
    pulse2 = Pulse(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start=0,
        duration=0.04,
        name="pulse2",
        type="drive",
        dac=3,
        adc=0,
        shape="rectangular",
    )
    pulse3 = Pulse(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start=0,
        duration=0.04,
        name="pulse2",
        type="drive",
        dac=3,
        adc=0,
        shape="test-non-existance",
    )

    execute_pulse_sequence.add_pulse_to_register(pulse0)
    execute_pulse_sequence.add_pulse_to_register(pulse1)
    execute_pulse_sequence.add_pulse_to_register(pulse2)
    with pytest.raises(NotImplementedError):
        execute_pulse_sequence.add_pulse_to_register(pulse3)


def test_body(soc):
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
            dac=3,
            adc=0,
            shape="gaussian",
            rel_sigma=5,
        ),
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse1",
            type="drive",
            dac=3,
            adc=0,
            shape="gaussian",
            rel_sigma=5,
        ),
        Pulse(
            frequency=200,
            amplitude=0.3,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse2",
            type="drive",
            dac=3,
            adc=0,
            shape="rectangular",
        ),
        Pulse(
            frequency=300,
            amplitude=0.2,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse3",
            type="drive",
            dac=3,
            adc=0,
            shape="gaussian",
            rel_sigma=5,
        ),
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
            shape="rectangular",
        ),
    ]
    qubits = [Qubit()]

    program = ExecutePulseSequence(soc, config, sequence, qubits)

    program.body()


def test_set_bias(soc):
    config = Config()
    sequence = [
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
            shape="rectangular",
        ),
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.set_bias("sweetspot")
    program.set_bias("zero")

    with pytest.raises(NotImplementedError):
        program.set_bias("test")


def test_set_bias_sweep(soc):
    config = Config()
    sequence = [
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
            shape="rectangular",
        ),
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]
    sweepers = tuple([Sweeper(expts=100, parameters=[Parameter.BIAS], starts=[0], stops=[1], indexes=[0])])

    program = ExecuteSweeps(soc, config, sequence, qubits, sweepers)
    program.set_bias("sweetspot")
    program.set_bias("zero")


def test_declare_nqz_flux(soc):
    config = Config()
    sequence = [
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
            shape="rectangular",
        ),
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.declare_nqz_flux()


def test_flux_body(soc):
    config = Config()
    sequence = [
        Pulse(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start=0,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
            shape="rectangular",
        ),
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.body()


def test_sweepers_to_reversed_list(execute_sweeps):
    sweepers = Sweeper(expts=1000, parameters=[Parameter.FREQUENCY], starts=[0], stops=[100], indexes=[0])
    converted = execute_sweeps.sweepers_to_reversed_list(sweepers)
    assert isinstance(converted, list)
    assert converted[0] == sweepers

    sweepers = (
        Sweeper(expts=1000, parameters=[Parameter.FREQUENCY], starts=[0], stops=[100], indexes=[0]),
        Sweeper(expts=1000, parameters=[Parameter.AMPLITUDE], starts=[0], stops=[100], indexes=[0]),
        Sweeper(expts=1000, parameters=[Parameter.RELATIVE_PHASE], starts=[0], stops=[100], indexes=[0]),
    )
    converted = execute_sweeps.sweepers_to_reversed_list(sweepers)
    assert isinstance(converted, list)
    for idx, sweeper in enumerate(sweepers):
        assert converted[-(idx + 1)] == sweeper
