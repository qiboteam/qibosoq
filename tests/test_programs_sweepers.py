import pathlib

import numpy as np
import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components.base import Config, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Rectangular
from qibosoq.programs.sweepers import ExecuteSweeps, ExecuteSweepsV2, reversed_sweepers


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
            indexes=[0, 0],
        )
    ]
    with pytest.raises(NotImplementedError):
        program = ExecuteSweeps(soc, config, sequence, qubits_flux, *sweepers)

    with pytest.raises(ValueError):
        Sweeper(
            expts=1000,
            parameters=[Parameter.AMPLITUDE],
            starts=[0],
            stops=[2],
            indexes=[0],
        )


@pytest.fixture
def soc_v2():
    qibosoq.configuration.IS_MULTIPLEXED = False
    return qick.QickConfig(
        str(pathlib.Path(__file__).parent / "qick_config_v2_standard.json")
    )


def v2_sequence():
    return [
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="drive0",
            type="drive",
            dac=3,
            adc=None,
        ),
        Rectangular(
            frequency=100,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0.04,
            duration=0.04,
            name="readout0",
            type="readout",
            dac=6,
            adc=0,
        ),
    ]


@pytest.mark.parametrize(
    "parameter, starts, stops, index",
    [
        (Parameter.FREQUENCY, 90, 110, 0),
        (Parameter.FREQUENCY, 90, 110, 1),
        (Parameter.AMPLITUDE, 0, 0.5, 0),
        (Parameter.AMPLITUDE, 0, 0.5, 1),
        (Parameter.RELATIVE_PHASE, 0, 90, 0),
        (Parameter.DELAY, 0, 1, 1),
    ],
)
def test_execute_sweeps_v2(soc_v2, parameter, starts, stops, index):
    sweeper = Sweeper(
        expts=5,
        parameters=[parameter],
        starts=[starts],
        stops=[stops],
        indexes=[index],
    )
    program = ExecuteSweepsV2(soc_v2, Config(), v2_sequence(), [Qubit()], sweeper)
    assert [loop[0] for loop in program.loops] == ["reps", "sweep_0"]
    if parameter is Parameter.FREQUENCY and index == 1:
        # a readout frequency sweep must also move the down-conversion frequency
        assert 0 in program.ro_freq_sweeps


def test_execute_sweeps_v2_bias(soc_v2):
    sweeper = Sweeper(
        expts=5, parameters=[Parameter.BIAS], starts=[0], stops=[0.5], indexes=[0]
    )
    program = ExecuteSweepsV2(
        soc_v2, Config(), v2_sequence(), [Qubit(bias=0.1, dac=2)], sweeper
    )
    assert "bias_sweetspot_2" in program.pulses


def test_execute_sweeps_v2_loop_order(soc_v2):
    sweepers = [
        Sweeper(
            expts=3,
            parameters=[Parameter.AMPLITUDE],
            starts=[0],
            stops=[0.5],
            indexes=[0],
        ),
        Sweeper(
            expts=4,
            parameters=[Parameter.FREQUENCY],
            starts=[90],
            stops=[110],
            indexes=[0],
        ),
    ]
    program = ExecuteSweepsV2(soc_v2, Config(), v2_sequence(), [Qubit()], *sweepers)
    # first sweeper is the outermost loop, as in tProc v1
    assert [loop[:2] for loop in program.loops] == [
        ("reps", 1000),
        ("sweep_0", 3),
        ("sweep_1", 4),
    ]


def test_execute_sweeps_v2_validation(soc_v2):
    duration = Sweeper(
        expts=5, parameters=[Parameter.DURATION], starts=[0], stops=[1], indexes=[0]
    )
    with pytest.raises(NotImplementedError):
        ExecuteSweepsV2(soc_v2, Config(), v2_sequence(), [Qubit()], duration)

    bias = Sweeper(
        expts=5, parameters=[Parameter.BIAS], starts=[0], stops=[0.5], indexes=[0]
    )
    with pytest.raises(ValueError):
        ExecuteSweepsV2(soc_v2, Config(), v2_sequence(), [Qubit()], bias)


@pytest.mark.parametrize("reps_innermost", [False, True])
def test_execute_sweeps_v2_single_shots(soc_v2, reps_innermost):
    sweepers = [
        Sweeper(
            expts=3, parameters=[Parameter.AMPLITUDE], starts=[0], stops=[0.5],
            indexes=[0],
        ),
        Sweeper(
            expts=4, parameters=[Parameter.FREQUENCY], starts=[90], stops=[110],
            indexes=[0],
        ),
    ]
    reps = 2
    config = Config(reps=reps, reps_innermost=reps_innermost)
    program = ExecuteSweepsV2(soc_v2, config, v2_sequence(), [Qubit()], *sweepers)

    loop_dims = [loop[1] for loop in program.loops]
    raw = np.arange(np.prod(loop_dims) * 2, dtype=float).reshape(*loop_dims, 1, 2)
    program.acquire = lambda soc, rounds=1, progress=True: setattr(
        program, "acc_buf", [raw]
    )

    toti, totq = program.perform_experiment(None, average=False)

    ro_ch, ro = next(iter(program.ro_chs.items()))
    offset = program._ro_offset(ro_ch, ro.get("ro_config"))
    # one adc, (readouts, sweep points, shots), as in tProc v1
    assert np.array(toti).shape == (1, 1, 3 * 4, reps)
    for p0 in range(3):
        for p1 in range(4):
            for shot in range(reps):
                index = (p0, p1, shot) if reps_innermost else (shot, p0, p1)
                expected = raw[index][0] / ro["length"] - offset
                assert toti[0][0][p0 * 4 + p1][shot] == pytest.approx(expected[0])
                assert totq[0][0][p0 * 4 + p1][shot] == pytest.approx(expected[1])


def test_execute_sweeps_single_shots(soc):
    sweepers = [
        Sweeper(
            expts=3, parameters=[Parameter.AMPLITUDE], starts=[0], stops=[0.5],
            indexes=[0],
        ),
        Sweeper(
            expts=4, parameters=[Parameter.RELATIVE_PHASE], starts=[0], stops=[90],
            indexes=[0],
        ),
    ]
    reps = 2
    sequence = v2_sequence()
    sequence[0].adc = 0
    program = ExecuteSweeps(soc, Config(reps=reps), sequence, [Qubit()], *sweepers)

    # tProc v1 raw buffer: (reps, *sweeps, readouts, 2), first sweeper outermost
    raw = np.arange(reps * 3 * 4 * 2, dtype=float).reshape(reps, 3, 4, 1, 2)
    program.acc_buf = [raw]
    toti, totq = program.collect_shots()

    length = soc.us2cycles(sequence[1].duration, ro_ch=0)
    # one adc, (readouts, sweep points, shots)
    assert np.array(toti).shape == (1, 1, 3 * 4, reps)
    for p0 in range(3):
        for p1 in range(4):
            for shot in range(reps):
                expected = raw[shot, p0, p1, 0] / length
                assert toti[0][0][p0 * 4 + p1][shot] == pytest.approx(expected[0])
                assert totq[0][0][p0 * 4 + p1][shot] == pytest.approx(expected[1])
