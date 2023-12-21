import pathlib

import numpy as np
import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import Arbitrary, Drag, FlatTop, Gaussian, Rectangular
from qibosoq.programs.base import BaseProgram
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


def test_declare_nqz_zones(execute_pulse_sequence):
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
    execute_pulse_sequence.declare_nqz_zones(sequence)


def test_declare_readout_freq(execute_pulse_sequence):
    execute_pulse_sequence.declare_readout_freq()


def test_add_pulse_to_register(execute_pulse_sequence):
    pulse0 = Gaussian(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start_delay=0,
        duration=0.04,
        name="pulse0",
        type="drive",
        dac=3,
        adc=None,
        rel_sigma=5,
    )
    pulse1 = Drag(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start_delay=0,
        duration=0.04,
        name="pulse1",
        type="drive",
        dac=3,
        adc=None,
        rel_sigma=5,
        beta=0.1,
    )
    pulse2 = Rectangular(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start_delay=0,
        duration=0.04,
        name="pulse2",
        type="drive",
        dac=3,
        adc=None,
    )
    pulse3 = Arbitrary(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start_delay=0,
        duration=0.04,
        name="pulse3",
        type="drive",
        dac=3,
        adc=None,
        i_values=[0.2] * 64,
        q_values=[0.2] * 64,
    )
    pulse4 = FlatTop(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start_delay=0,
        duration=0.04,
        name="pulse2",
        type="drive",
        dac=3,
        adc=None,
        rel_sigma=2,
    )

    execute_pulse_sequence.add_pulse_to_register(pulse0)
    execute_pulse_sequence.add_pulse_to_register(pulse1)
    execute_pulse_sequence.add_pulse_to_register(pulse2)
    execute_pulse_sequence.add_pulse_to_register(pulse3)
    execute_pulse_sequence.add_pulse_to_register(pulse4)


def test_body(soc):
    config = Config()
    sequence = [
        Gaussian(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse0",
            type="drive",
            dac=3,
            adc=0,
            rel_sigma=5,
        ),
        Gaussian(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse1",
            type="drive",
            dac=3,
            adc=0,
            rel_sigma=5,
        ),
        Rectangular(
            frequency=200,
            amplitude=0.3,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse2",
            type="drive",
            dac=3,
            adc=0,
        ),
        Gaussian(
            frequency=300,
            amplitude=0.2,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse3",
            type="drive",
            dac=3,
            adc=0,
            rel_sigma=5,
        ),
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0.4,
            duration=0.04,
            name="pulse4",
            type="readout",
            dac=6,
            adc=0,
        ),
    ]
    qubits = [Qubit()]

    program = ExecutePulseSequence(soc, config, sequence, qubits)

    program.body()


def test_initialize(soc):
    with pytest.raises(Exception):
        test = BaseProgram(soc, {}, [], [])


def test_execute_readout_pulse(soc):
    config = Config()
    sequence = [
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=1,
            name="pulse1",
            type="readout",
            dac=6,
            adc=0,
        ),
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0.5,
            duration=0.04,
            name="pulse2",
            type="readout",
            dac=6,
            adc=0,
        ),
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=3,
            duration=0.04,
            name="pulse3",
            type="readout",
            dac=6,
            adc=0,
        ),
    ]
    qubits = [Qubit()]

    program = ExecutePulseSequence(soc, config, sequence, qubits)

    muxed_pulse_executed = []
    muxed_ro_executed_indexes = []

    program.execute_readout_pulse(sequence[0], muxed_pulse_executed, muxed_ro_executed_indexes)
    if program.is_mux:
        assert len(muxed_pulse_executed) == 2
        assert muxed_ro_executed_indexes == [0]
    program.execute_readout_pulse(sequence[1], muxed_pulse_executed, muxed_ro_executed_indexes)
    if program.is_mux:
        assert len(muxed_pulse_executed) == 2
        assert muxed_ro_executed_indexes == [0]
    program.execute_readout_pulse(sequence[2], muxed_pulse_executed, muxed_ro_executed_indexes)
    if program.is_mux:
        assert len(muxed_pulse_executed) == 3
        assert muxed_ro_executed_indexes == [0, 1]


@pytest.mark.parametrize("avg", [True, False])
def test_acquire(mocker, soc, avg):
    mocker.patch("qick.AveragerProgram.acquire", return_values=[1, 2, 3])

    config = Config()
    sequence = [
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
    program.di_buf = [np.zeros(1000)]
    program.dq_buf = [np.zeros(1000)]
    program.perform_experiment(program.soc, average=avg)

    program.expts = 10
    program.di_buf = [np.zeros(1000 * 10)]
    program.dq_buf = [np.zeros(1000 * 10)]
    program.perform_experiment(program.soc, average=avg)

    sequence = [
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse1",
            type="drive",
            dac=2,
            adc=None,
        ),
    ]
    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.perform_experiment(program.soc, average=avg)
