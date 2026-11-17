import pathlib

import numpy as np
import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import (
    Arbitrary,
    Drag,
    Gaussian,
    Hann,
    Measurement,
    Rectangular,
)
from qibosoq.programs.pulse_sequence import ExecutePulseSequence, ExecutePulseSequenceV2


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


@pytest.fixture
def soc_v2():
    qibosoq.configuration.IS_MULTIPLEXED = False
    return qick.QickConfig(
        str(pathlib.Path(__file__).parent / "qick_config_v2_standard.json")
    )


@pytest.fixture
def soc_v2_multiplexed():
    qibosoq.configuration.IS_MULTIPLEXED = True
    return qick.QickConfig(
        str(pathlib.Path(__file__).parent / "qick_config_v2_multiplexed.json")
    )


@pytest.fixture
def execute_pulse_sequence_v2(soc_v2):
    config = Config()
    sequence = [
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
    qubits = [Qubit()]
    return ExecutePulseSequenceV2(soc_v2, config, sequence, qubits)


def test_execute_pulsesequence_init(execute_pulse_sequence):
    assert isinstance(execute_pulse_sequence, ExecutePulseSequence)


def test_execute_pulsesequence_v2_init(execute_pulse_sequence_v2):
    assert isinstance(execute_pulse_sequence_v2, ExecutePulseSequenceV2)


def test_execute_pulsesequence_v2_readout_triggers(execute_pulse_sequence_v2):
    asm = execute_pulse_sequence_v2.asm()
    assert "TRIG" in asm


def test_execute_pulsesequence_v2_handles_measurement(soc_v2):
    config = Config()
    sequence = [
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
        Measurement(
            type="readout",
            frequency=100,
            start_delay=0.08,
            duration=0.04,
            dac=6,
            adc=0,
        ),
    ]
    program = ExecutePulseSequenceV2(soc_v2, config, sequence, [Qubit()])
    asm = program.asm()
    # each readout emits TRIG set+clr, so pulse+measurement gives at least 4 TRIG ops
    assert asm.count("TRIG") >= 4


def test_execute_pulsesequence_v2_multiplexed_readout_group(soc_v2_multiplexed):
    config = Config()
    sequence = [
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
        Rectangular(
            frequency=120,
            amplitude=0.1,
            relative_phase=0,
            start_delay=0,
            duration=0.04,
            name="readout1",
            type="readout",
            dac=6,
            adc=1,
        ),
    ]
    program = ExecutePulseSequenceV2(soc_v2_multiplexed, config, sequence, [Qubit()])
    asm = program.asm()
    assert "TRIG" in asm


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
    ]
    qubits = [Qubit(10, 0), Qubit(0, None), Qubit(0, 2)]

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    program.body()


def v2_pulse(name, type, dac, adc, start_delay, duration=0.1, cls=Rectangular, **kw):
    return cls(
        frequency=100,
        amplitude=0.1,
        relative_phase=0,
        start_delay=start_delay,
        duration=duration,
        name=name,
        type=type,
        dac=dac,
        adc=adc,
        **kw,
    )


def test_v2_bias_and_flux_pulses_hold_their_value(soc_v2):
    sequence = [
        v2_pulse("flux0", "flux", 2, None, 0),
        v2_pulse("readout0", "readout", 6, 0, 0.1),
    ]
    program = ExecutePulseSequenceV2(
        soc_v2, Config(), sequence, [Qubit(bias=0.3, dac=2)]
    )
    for name in ["bias_sweetspot_2", "bias_zero_2", "flux0_0"]:
        assert program.pulses[name].params["stdysel"] == "last"


def test_v2_back_to_back_readouts_do_not_overlap(soc_v2, caplog):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0, duration=1.0),
        v2_pulse("readout1", "readout", 6, 0, 0, duration=1.0),
    ]
    with caplog.at_level("WARNING"):
        ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit()])
    assert "conflict" not in caplog.text


def test_v2_gaussian_readout(soc_v2):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0, cls=Gaussian, rel_sigma=5),
    ]
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit()])
    assert "readout0_0" in program.pulses


def envelope_std(samples):
    weights = samples / samples.sum()
    x = np.arange(len(samples))
    mean = (weights * x).sum()
    return np.sqrt((weights * (x - mean) ** 2).sum())


@pytest.mark.parametrize("cls,kw", [(Gaussian, {}), (Drag, {"beta": 0.0})])
def test_v2_gaussian_sigma(soc_v2, cls, kw):
    duration, rel_sigma = 0.1, 5
    sequence = [
        v2_pulse(
            "drive0", "drive", 3, None, 0, duration, cls, rel_sigma=rel_sigma, **kw
        ),
        v2_pulse("readout0", "readout", 6, 0, duration),
    ]
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit()])
    data = program.envelopes[3]["envs"]["drive0_envelope"]["data"][:, 0]

    sigma = duration / rel_sigma * soc_v2["gens"][3]["fs"]
    x = np.arange(len(data))
    expected = np.exp(-((x - (len(data) - 1) / 2) ** 2) / (2 * sigma**2))
    assert envelope_std(data.astype(float)) == pytest.approx(
        envelope_std(expected), rel=0.02
    )


def test_v2_hann_amplitude_applied_once(soc_v2):
    sequence = [
        v2_pulse("hann", "drive", 3, None, 0, cls=Hann),
        v2_pulse("gauss", "drive", 3, None, 0, cls=Gaussian, rel_sigma=5),
        v2_pulse("readout0", "readout", 6, 0, 0),
    ]
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit()])
    envs = program.envelopes[3]["envs"]
    hann_peak = envs["hann_envelope"]["data"][:, 0].max()
    gauss_peak = envs["gauss_envelope"]["data"][:, 0].max()
    assert hann_peak == pytest.approx(gauss_peak, rel=0.01)
    gains = [
        program.pulses[name].waveforms[0].gain.start for name in ("hann_0", "gauss_1")
    ]
    assert gains[0] == gains[1]


def test_v2_arbitrary_envelopes_in_dac_units(soc_v2):
    """qibolab sends envelopes normalized to 1."""
    samples = 64
    kw = dict(cls=Arbitrary, i_values=[1.0] * samples, q_values=[0.0] * samples)
    sequence = [
        v2_pulse("drive0", "drive", 3, None, 0, **kw),
        v2_pulse("flux0", "flux", 2, None, 0, **kw),
        v2_pulse("readout0", "readout", 6, 0, 0),
    ]
    sequence[1].amplitude = 0.5
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit(dac=2)])

    drive = program.envelopes[3]["envs"]["drive0_envelope"]["data"][:, 0]
    assert drive.max() == pytest.approx(soc_v2["gens"][3]["maxv"], abs=1)
    # flux pulses play at full gain, the amplitude is in the samples
    flux = program.envelopes[2]["envs"]["flux0"]["data"][:samples, 0]
    assert flux.max() == pytest.approx(0.5 * soc_v2["gens"][2]["maxv"], abs=1)


def test_v2_readouts_on_dacs_in_different_zones(soc_v2):
    sequence = [
        v2_pulse("readout0", "readout", 5, 0, 0),
        v2_pulse("readout1", "readout", 6, 1, 0),
    ]
    sequence[0].frequency = 3000
    sequence[1].frequency = 5000
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit()])
    assert program.gen_chs[5]["nqz"] == 1
    assert program.gen_chs[6]["nqz"] == 2


def test_v2_repeated_pulse_names(soc_v2):
    """qibolab can reuse a pulse id within a sequence, e.g. a duplicated rx90."""
    sequence = [
        v2_pulse("flux0", "flux", 2, None, 0),
        v2_pulse("flux0", "flux", 2, None, 0),
        v2_pulse("rx90", "drive", 3, None, 0, cls=Gaussian, rel_sigma=5),
        v2_pulse("rx90", "drive", 3, None, 0, cls=Gaussian, rel_sigma=5),
        v2_pulse("readout0", "readout", 6, 0, 0),
    ]
    sequence[3].relative_phase = 90
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit(dac=2)])

    assert {"flux0_0", "flux0_1", "rx90_2", "rx90_3"} <= set(program.pulses)
    # envelopes are shared, the pulse parameters are not
    assert list(program.envelopes[3]["envs"]) == ["rx90_envelope"]
    assert list(program.envelopes[2]["envs"]) == ["flux0"]
    phases = [program.pulses[f"rx90_{i}"].waveforms[0].phase for i in (2, 3)]
    assert phases[0] != phases[1]


def test_v2_time_of_flight_in_ticks(soc_v2):
    sequence = [v2_pulse("readout0", "readout", 6, 0, 0)]
    program = ExecutePulseSequenceV2(
        soc_v2, Config(ro_time_of_flight=200), sequence, [Qubit()]
    )
    assert program.ro_time_of_flight == pytest.approx(soc_v2.cycles2us(200))


def fake_acquire(program, raw):
    """Replace acquire() with one that fills the raw buffer and records rounds."""

    def acquire(soc, rounds=1, progress=True):
        program.acquired_rounds = rounds
        program.acc_buf = [raw]
        return [raw.mean(axis=program.avg_level)]

    program.acquire = acquire


def normalized(program, raw):
    ro_ch, ro = next(iter(program.ro_chs.items()))
    return raw / ro["length"] - program._ro_offset(ro_ch, ro.get("ro_config"))


def test_v2_single_shots(soc_v2):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0),
        v2_pulse("readout1", "readout", 6, 0, 0),
    ]
    reps = 5
    program = ExecutePulseSequenceV2(
        soc_v2, Config(reps=reps, rounds=3), sequence, [Qubit()]
    )
    raw = np.arange(reps * 2 * 2, dtype=float).reshape(reps, 2, 2)
    fake_acquire(program, raw)

    toti, totq = program.perform_experiment(None, average=False)

    assert program.acquired_rounds == 3
    expected = normalized(program, raw)
    # one adc, (readouts, shots), as in tProc v1
    assert np.array(toti).shape == (1, 2, reps)
    for read in range(2):
        for shot in range(reps):
            assert toti[0][read][shot] == pytest.approx(expected[shot, read, 0])
            assert totq[0][read][shot] == pytest.approx(expected[shot, read, 1])
