import pathlib

import numpy as np
import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components.base import Config, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Rectangular
from qibosoq.programs.sweepers import ExecuteSweeps, reversed_sweepers


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
def execute_sweeps(soc):
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
    sweepers = (
        Sweeper(
            expts=1000,
            parameters=[
                Parameter.FREQUENCY,
            ],
            starts=np.array([0]),
            stops=np.array([100]),
            indexes=[0],
        ),
        Sweeper(
            expts=1000,
            parameters=[Parameter.AMPLITUDE],
            starts=np.array([0]),
            stops=np.array([1]),
            indexes=[0],
        ),
        Sweeper(
            expts=1000,
            parameters=[Parameter.RELATIVE_PHASE],
            starts=np.array([0]),
            stops=np.array([100]),
            indexes=[0],
        ),
        Sweeper(
            expts=1000,
            parameters=[Parameter.DELAY],
            starts=np.array([0]),
            stops=np.array([1]),
            indexes=[0],
        ),
    )

    qubits = [Qubit()]

    program = ExecuteSweeps(soc, config, sequence, qubits, *sweepers)
    return program


def test_execute_sweeps_init(execute_sweeps):
    assert isinstance(execute_sweeps, ExecuteSweeps)


def test_body(execute_sweeps):
    execute_sweeps.body()


def test_set_bias_sweep(soc):
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
    sweepers = tuple(
        [
            Sweeper(
                expts=100,
                parameters=[Parameter.BIAS],
                starts=np.array([0]),
                stops=np.array([1]),
                indexes=[0],
            )
        ]
    )

    program = ExecuteSweeps(soc, config, sequence, qubits, *sweepers)
    program.set_bias("sweetspot")
    program.set_bias("zero")


def test_reversed_sweepers(execute_sweeps):
    sweepers = Sweeper(
        expts=1000,
        parameters=[Parameter.FREQUENCY],
        starts=np.array([0]),
        stops=np.array([100]),
        indexes=[0],
    )
    converted = reversed_sweepers(sweepers)
    assert isinstance(converted, list)
    assert converted[0] == sweepers

    sweepers = (
        Sweeper(
            expts=1000,
            parameters=[Parameter.FREQUENCY],
            starts=np.array([0]),
            stops=np.array([100]),
            indexes=[0],
        ),
        Sweeper(
            expts=1000,
            parameters=[Parameter.AMPLITUDE],
            starts=np.array([0]),
            stops=np.array([1]),
            indexes=[0],
        ),
        Sweeper(
            expts=1000,
            parameters=[Parameter.RELATIVE_PHASE],
            starts=np.array([0]),
            stops=np.array([100]),
            indexes=[0],
        ),
    )
    converted = reversed_sweepers(sweepers)
    assert isinstance(converted, list)
    for idx, sweeper in enumerate(sweepers):
        assert converted[-(idx + 1)] == sweeper


def test_check_validity_sweep(soc):
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

    sweepers = [
        Sweeper(
            expts=1000,
            parameters=[Parameter.FREQUENCY],
            starts=[0],
            stops=[100],
            indexes=[0],
        )
    ]
    qubits = [Qubit()]
    program = ExecuteSweeps(soc, config, sequence, qubits, *sweepers)

    sweepers = [
        Sweeper(
            expts=1000,
            parameters=[Parameter.BIAS],
            starts=[0],
            stops=[100],
            indexes=[0],
        )
    ]

    with pytest.raises(ValueError):
        program = ExecuteSweeps(soc, config, sequence, qubits, *sweepers)

    sequence_flux = [
        Rectangular(
            frequency=0,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="pulse1",
            type="flux",
            dac=6,
            adc=0,
        ),
    ]
    sweepers = [
        Sweeper(
            expts=1000,
            parameters=[Parameter.BIAS],
            starts=[0],
            stops=[100],
            indexes=[0],
        )
    ]
    with pytest.raises(NotImplementedError):
        program = ExecuteSweeps(soc, config, sequence_flux, qubits, *sweepers)

    qubits_flux = [Qubit(dac=6, bias=0)]
    with pytest.raises(NotImplementedError):
        program = ExecuteSweeps(soc, config, sequence_flux, qubits_flux, *sweepers)

    sweepers = [
        Sweeper(
            expts=1000,
            parameters=[Parameter.AMPLITUDE],
            starts=[0],
            stops=[1],
            indexes=[0],
        )
    ]
    with pytest.raises(NotImplementedError):
        program = ExecuteSweeps(soc, config, sequence_flux, qubits, *sweepers)

    sweepers = [
        Sweeper(
            expts=1000,
            parameters=[Parameter.DURATION],
            starts=[0],
            stops=[1],
            indexes=[0],
        )
    ]
    with pytest.raises(NotImplementedError):
        program = ExecuteSweeps(soc, config, sequence, qubits, *sweepers)

    sweepers = [
        Sweeper(
            expts=1000,
            parameters=[Parameter.BIAS, Parameter.AMPLITUDE],
            starts=[0, 0],
            stops=[1, 1],
            indexes=[0],
        )
    ]
    with pytest.raises(NotImplementedError):
        program = ExecuteSweeps(soc, config, sequence, qubits_flux, *sweepers)
