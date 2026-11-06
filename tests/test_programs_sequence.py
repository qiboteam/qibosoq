import pathlib

import pytest
import qick

qick.QickSoc = None

import qibosoq.configuration
from qibosoq.components.base import Config, Qubit
from qibosoq.components.pulses import Gaussian, Measurement, Rectangular
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
    return qick.QickConfig(str(pathlib.Path(__file__).parent / "qick_config_v2_standard.json"))


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
    for name in ["bias_sweetspot_2", "bias_zero_2", "flux0"]:
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
    assert "readout0" in program.pulses


def test_v2_single_shots_not_implemented(execute_pulse_sequence_v2):
    with pytest.raises(NotImplementedError):
        execute_pulse_sequence_v2.perform_experiment(None, average=False)
