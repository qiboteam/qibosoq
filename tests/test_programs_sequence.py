import copy
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


def load_soc_v2(file):
    return qick.QickConfig(str(pathlib.Path(__file__).parent / file))


@pytest.fixture
def soc_v2_static():
    """Firmware with PYNQ-configured readouts (axis_readout_v2)."""
    return load_soc_v2("qick_config_v2_standard.json")


@pytest.fixture
def soc_v2_dynamic():
    """Firmware with tProc-configured readouts (axis_dyn_readout_v1)."""
    return load_soc_v2("qick_config_v2_dynamic.json")


@pytest.fixture(params=["static", "dynamic"])
def soc_v2(request):
    return request.getfixturevalue(f"soc_v2_{request.param}")


@pytest.fixture
def soc_v2_multiplexed():
    """Firmware with a mux generator (6) and PFB readouts (0-3)."""
    return load_soc_v2("qick_config_v2_multiplexed.json")


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


def test_v2_envelopes_respect_maxv_scale(soc_v2):
    """int4 generators limit the envelopes to 0.9 maxv, as qick's own shapes."""
    for gen in (2, 3):
        soc_v2["gens"][gen]["maxv_scale"] = 0.9
    samples = 64
    kw = dict(cls=Arbitrary, i_values=[1.0] * samples, q_values=[0.0] * samples)
    sequence = [
        v2_pulse("arb", "drive", 3, None, 0, **kw),
        v2_pulse("hann", "drive", 3, None, 0, cls=Hann),
        v2_pulse("gauss", "drive", 3, None, 0, cls=Gaussian, rel_sigma=5),
        v2_pulse("flux0", "flux", 2, None, 0, **kw),
        v2_pulse("readout0", "readout", 6, 0, 0),
    ]
    sequence[3].amplitude = 1.0
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit(dac=2)])

    envs = program.envelopes[3]["envs"]
    gauss_peak = envs["gauss_envelope"]["data"][:, 0].max()
    assert gauss_peak == pytest.approx(soc_v2.get_maxv(3), abs=1)
    assert envs["arb_envelope"]["data"][:, 0].max() == pytest.approx(gauss_peak, abs=1)
    assert envs["hann_envelope"]["data"][:, 0].max() == pytest.approx(
        gauss_peak, rel=0.01
    )
    flux = program.envelopes[2]["envs"]["flux0"]["data"][:, 0]
    assert flux.max() == pytest.approx(soc_v2.get_maxv(2), abs=1)


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


def test_v2_repeated_pulse_names_with_different_envelopes(soc_v2):
    """qibolab keeps the pulse id when replacing amplitude or duration."""
    sequence = [
        v2_pulse("flux0", "flux", 2, None, 0),
        v2_pulse("flux0", "flux", 2, None, 0),
        v2_pulse("rx", "drive", 3, None, 0, 0.04, cls=Gaussian, rel_sigma=5),
        v2_pulse("rx", "drive", 3, None, 0, 0.08, cls=Gaussian, rel_sigma=5),
        v2_pulse("readout0", "readout", 6, 0, 0),
    ]
    sequence[1].amplitude = 0.4
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit(dac=2)])

    def played(name):
        dac = name_dac[name]
        # the waveform address is in clock cycles
        addr = (
            program.pulses[name].waveforms[0].env * soc_v2["gens"][dac]["samps_per_clk"]
        )
        envs = program.envelopes[dac]["envs"].values()
        return next(env["data"][:, 0] for env in envs if env["addr"] == addr)

    name_dac = {"flux0_0": 2, "flux0_1": 2, "rx_2": 3, "rx_3": 3}
    maxv = soc_v2.get_maxv(2)
    assert played("flux0_0").max() == pytest.approx(0.1 * maxv, abs=1)
    assert played("flux0_1").max() == pytest.approx(0.4 * maxv, abs=1)
    assert len(played("rx_3")) == 2 * len(played("rx_2"))


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


def test_v2_static_readout(soc_v2_static, mocker):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0),
        Measurement(
            type="readout", frequency=100, start_delay=0, duration=0.1, dac=6, adc=0
        ),
    ]
    program = ExecutePulseSequenceV2(soc_v2_static, Config(), sequence, [Qubit()])
    readout = program.ro_chs[0]
    assert (readout["freq"], readout["gen_ch"], readout["trigs"]) == (100, 6, 2)
    # the frequency is set by PYNQ, there is no tProc readout config
    assert list(program.pulses) == ["readout0_0"]

    soc = mocker.Mock()
    program.config_readouts(soc)
    ch, regs = soc.configure_readout.call_args.args
    assert ch == 0
    assert regs["f_rounded"] == pytest.approx(100, abs=0.01)


def test_v2_readout_config_only_for_dynamic_readouts(soc_v2):
    sequence = [v2_pulse("readout0", "readout", 6, 0, 0)]
    program = ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit()])
    dynamic = "tproc_ctrl" in soc_v2["readouts"][0]
    assert bool(program.readout_config_names) is dynamic
    assert ("freq" in program.ro_chs[0]) is not dynamic
    # readout pulse, plus the readout config for dynamic readouts
    assert program.asm().count("WPORT_WR") == 1 + dynamic


@pytest.mark.parametrize("field, value", [("frequency", 200), ("duration", 0.2)])
def test_v2_static_readouts_on_one_adc_must_match(soc_v2_static, field, value):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0),
        v2_pulse("readout1", "readout", 6, 0, 0),
    ]
    setattr(sequence[1], field, value)
    with pytest.raises(ValueError):
        ExecutePulseSequenceV2(soc_v2_static, Config(), sequence, [Qubit()])


def test_v2_readouts_on_one_adc_must_share_duration(soc_v2):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0),
        v2_pulse("readout1", "readout", 6, 0, 0, duration=0.2),
    ]
    with pytest.raises(ValueError):
        ExecutePulseSequenceV2(soc_v2, Config(), sequence, [Qubit()])


def test_v2_dynamic_readout_config_per_frequency(soc_v2_dynamic):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0),
        v2_pulse("readout1", "readout", 6, 0, 0),
        v2_pulse("readout2", "readout", 6, 0, 0),
    ]
    sequence[1].frequency = 200
    program = ExecutePulseSequenceV2(soc_v2_dynamic, Config(), sequence, [Qubit()])
    names = program.readout_config_names
    assert names[0] == names[2] != names[1]
    freqs = [program.pulses[names[i]].params["freq"].start for i in range(3)]
    assert freqs == [100, 200, 100]


def test_v2_multiplexed_static_readouts(soc_v2_multiplexed, mocker):
    sequence = [
        v2_pulse("readout0", "readout", 6, 0, 0),
        v2_pulse("readout1", "readout", 6, 1, 0),
    ]
    sequence[1].frequency = 400
    program = ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])
    assert [program.ro_chs[adc]["freq"] for adc in (0, 1)] == [100, 400]
    assert not program.readout_config_names

    soc = mocker.Mock()
    program.config_readouts(soc)
    _, regs, _ = soc.config_mux_readout.call_args.args
    assert [reg["pfb_port"] for reg in regs] == [0, 1]
    freqs = [reg["f_rounded"] for reg in regs]
    assert freqs == pytest.approx([100, 400], abs=0.01)


def mux_readout(adc, frequency, start_delay=0, dac=6, **kw):
    pulse = v2_pulse(f"readout{adc}", "readout", dac, adc, start_delay, **kw)
    pulse.frequency = frequency
    return pulse


@pytest.mark.parametrize("is_multiplexed", [False, True])
def test_v2_mux_detected_per_generator(
    soc_v2_multiplexed, soc_v2_static, is_multiplexed, monkeypatch
):
    """tProc v2 programs ignore the global IS_MULTIPLEXED."""
    monkeypatch.setattr(qibosoq.configuration, "IS_MULTIPLEXED", is_multiplexed)
    sequence = [mux_readout(0, 100), mux_readout(1, 400)]
    mux = ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])
    assert mux.mux_group_pulses == ["mux_ro_6_0_1"]

    sequence = [v2_pulse("readout0", "readout", 6, 0, 0)]
    plain = ExecutePulseSequenceV2(soc_v2_static, Config(), sequence, [Qubit()])
    assert plain.multi_ro_pulses == []
    assert "readout0_0" in plain.pulses


def test_v2_mux_tones_and_masks(soc_v2_multiplexed, mocker):
    sequence = [
        mux_readout(1, 400),
        mux_readout(0, 100),
        v2_pulse("drive0", "drive", 3, None, 0),
        # equal to the second readout, but a separate acquisition
        mux_readout(0, 100),
        mux_readout(0, 100),
    ]
    program = ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])

    # one tone per ADC, in order of appearance
    tones = program.gen_chs[6]["mux_tones"]
    assert [tone["freq_rounded"] for tone in tones] == pytest.approx([400, 100])
    names = program.mux_group_pulses
    assert names == ["mux_ro_6_0_1", "mux_ro_6_1", "mux_ro_6_1"]
    masks = [program.pulses[name].waveforms[0].conf for name in names]
    assert masks == [0b11, 0b10, 0b10]
    assert [program.ro_chs[adc]["trigs"] for adc in (0, 1)] == [3, 1]

    # each tone is demodulated by the PFB output of its ADC
    soc = mocker.Mock()
    program.config_readouts(soc)
    _, regs, _ = soc.config_mux_readout.call_args.args
    ro_freqs = {reg["pfb_port"]: reg["f_rounded"] for reg in regs}
    for tone, adc in zip(tones, (1, 0)):
        port = soc_v2_multiplexed["readouts"][adc]["pfb_port"]
        assert tone["freq_rounded"] == pytest.approx(ro_freqs[port])


def test_v2_normal_and_mux_generators(soc_v2_multiplexed):
    second_mux = copy.deepcopy(soc_v2_multiplexed["gens"][6])
    second_mux.update(fullpath="axis_sg_mux4_v2_7", tproc_ch=7, dac="10")
    soc_v2_multiplexed["gens"].append(second_mux)
    sequence = [
        v2_pulse("drive0", "drive", 3, None, 0),
        mux_readout(0, 100),
        mux_readout(1, 400),
        mux_readout(2, 700, dac=7),
        mux_readout(3, 1000, dac=5),
    ]
    program = ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])
    assert [len(program.gen_chs[gen]["mux_tones"]) for gen in (6, 7)] == [2, 1]
    assert "mux_tones" not in program.gen_chs[5]
    assert program.mux_group_pulses == ["mux_ro_6_0_1", "mux_ro_7_0"]
    assert "readout3_4" in program.pulses
    assert [program.ro_chs[adc]["trigs"] for adc in range(4)] == [1, 1, 1, 1]


def test_v2_mux_tone_limit(soc_v2_multiplexed):
    soc_v2_multiplexed["gens"][6]["n_tones"] = 2
    sequence = [mux_readout(adc, 100 + 300 * adc) for adc in range(3)]
    with pytest.raises(ValueError, match="2 tones"):
        ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])


@pytest.mark.parametrize("field, value", [("frequency", 200), ("amplitude", 0.3)])
def test_v2_mux_tone_is_fixed(soc_v2_multiplexed, field, value):
    sequence = [
        mux_readout(0, 100),
        v2_pulse("drive0", "drive", 3, None, 0),
        mux_readout(0, 100),
    ]
    setattr(sequence[2], field, value)
    with pytest.raises(ValueError):
        ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])


def test_v2_mux_readout_must_be_rectangular(soc_v2_multiplexed):
    sequence = [mux_readout(0, 100, cls=Gaussian, rel_sigma=5)]
    with pytest.raises(TypeError):
        ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])


def test_v2_measurement_with_mux_readouts(soc_v2_multiplexed):
    sequence = [
        mux_readout(0, 100),
        Measurement(
            type="readout", frequency=400, start_delay=0, duration=0.1, dac=6, adc=1
        ),
    ]
    program = ExecutePulseSequenceV2(soc_v2_multiplexed, Config(), sequence, [Qubit()])
    assert program.mux_group_pulses == ["mux_ro_6_0"]
    assert [program.ro_chs[adc]["trigs"] for adc in (0, 1)] == [1, 1]
