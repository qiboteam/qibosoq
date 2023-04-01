""" Tests `rfosc_server.py`."""

import pytest
from qibosoq.rfsoc_server import ExecutePulseSequence, ExecuteSingleSweep, MyTCPHandler
from qibolab.instruments.rfsoc import QickProgramConfig
from qibolab.pulses import PulseSequence, PulseType, Rectangular, Pulse, Gaussian, Drag
from qibolab.platforms.abstract import Qubit
from qibolab.designs import ChannelMap
from qibolab.sweeper import Sweeper, Parameter
from qick import QickSoc
from socketserver import BaseRequestHandler, TCPServer
import numpy as np
from time import sleep


class Helper:
    def get_qick_program_config(expts=None):
        cfg = QickProgramConfig(expts)
        return cfg

    def get_pulse_sequence(readouts=1, drives=0, type_drive="gaus"):
        sequence = PulseSequence()
        start = 0
        for _ in range(drives):
            if type_drive == "gaus":
                shape = Gaussian(5)
            elif type_drive == "drag":
                shape = Drag(5, 0.001)
            p0 = Pulse(
                start=start,
                duration=50,
                amplitude=0.1,
                frequency=6_000_000_000,
                relative_phase=0.0,
                shape=shape,
                channel=0,
                type=PulseType.DRIVE,
                qubit=0,
            )
            sequence.add(p0)
            start = p0.finish + 10
        for _ in range(readouts):
            p0 = Pulse(
                start=start,
                duration=50,
                amplitude=0.1,
                frequency=7_000_000_000,
                relative_phase=0.0,
                shape=Rectangular(),
                channel=0,
                type=PulseType.READOUT,
                qubit=0,
            )
            sequence.add(p0)
            start = p0.finish + 10
        return sequence

    def get_qubits():
        channels = ChannelMap()
        channels |= ChannelMap.from_names("L3-18_ro")  # readout (DAC)
        channels |= ChannelMap.from_names("L2-RO")  # feedback (readout DAC)
        channels |= ChannelMap.from_names("L3-18_qd")  # drive

        # Map controllers to qubit channels (HARDCODED)
        channels["L3-18_ro"].ports = [("o0", 0)]  # readout
        channels["L2-RO"].ports = [("i0", 0)]  # feedback
        channels["L3-18_qd"].ports = [("o1", 1)]

        qubits = []
        q0 = Qubit(
                name="q0",
                readout=channels["L3-18_ro"],
                feedback=channels["L2-RO"],
                drive=channels["L3-18_qd"]
        )
        qubits.append(q0)
        return qubits

    def get_sweeper(sequence):
        sweep = Sweeper(
                parameter=Parameter.frequency,
                parameter_range=np.arange(5_000_000_000, 5_000_00_100, 20),
                pulses=sequence[0]
                )
        return sweep


@pytest.fixture
def helpers():
    return Helper


def test_qick_soc_init():
    """Tests QickSoc is initializable"""
    soc = QickSoc()
    assert isinstance(soc, QickSoc)


# tests for the ExecutePulseSequence class
def test_execute_pulse_sequence_init(helpers):
    """Tests ExecutePulseSequence __init__ and initialize function"""
    soc = QickSoc()

    cfg = helpers.get_qick_program_config()
    sequence = helpers.get_pulse_sequence()
    qubits = helpers.get_qubits()

    program = ExecutePulseSequence(soc, cfg, sequence, qubits)

    assert isinstance(program, ExecutePulseSequence)


def test_execute_pulse_sequence_acquire(helpers):
    soc = QickSoc()

    cfg = helpers.get_qick_program_config()
    qubits = helpers.get_qubits()

    for n_ro in [1, 2]:
        sequence = helpers.get_pulse_sequence(readouts=n_ro)
        program = ExecutePulseSequence(soc, cfg, sequence, qubits)
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=n_ro,
                load_pulses=True,
                progress=False,
                debug=False,
                average=False
        )
        assert i.shape == [1, n_ro, 1000]
        assert q.shape == [1, n_ro, 1000]


def test_execute_pulse_sequence_acquire_average(helpers):
    soc = QickSoc()
    cfg = helpers.get_qick_program_config()
    qubits = helpers.get_qubits()

    for n_ro in [1, 2]:
        sequence = helpers.get_pulse_sequence(readouts=n_ro)
        program = ExecutePulseSequence(soc, cfg, sequence, qubits)
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=n_ro,
                load_pulses=True,
                progress=False,
                debug=False,
                average=True
        )
        assert i.shape == [1, n_ro, 1]
        assert q.shape == [1, n_ro, 1]


def test_execute_pulse_sequence_gaus(helpers):
    soc = QickSoc()
    cfg = helpers.get_qick_program_config()
    qubits = helpers.get_qubits()

    sequence = helpers.get_pulse_sequence(readouts=1, drives=1, type_drive="gaus")

    program = ExecutePulseSequence(soc, cfg, sequence, qubits)
    i, q = program.acquire(
            soc=soc,
            readouts_per_experiment=1,
            load_pulses=True,
            progress=False,
            debug=False,
            average=True
    )

    assert i.shape == [1, 1, 1]
    assert q.shape == [1, 1, 1]


def test_execute_pulse_sequence_drag(helpers):
    soc = QickSoc()
    cfg = helpers.get_qick_program_config()
    qubits = helpers.get_qubits()

    sequence = helpers.get_pulse_sequence(readouts=1, drives=1, type_drive="drag")

    program = ExecutePulseSequence(soc, cfg, sequence, qubits)
    i, q = program.acquire(
            soc=soc,
            readouts_per_experiment=1,
            load_pulses=True,
            progress=False,
            debug=False,
            average=True
    )

    assert i.shape == [1, 1, 1]
    assert q.shape == [1, 1, 1]


def test_execute_pulse_sequence_error_amplitude(helpers):
    soc = QickSoc()
    cfg = helpers.get_qick_program_config()
    qubits = helpers.get_qubits()

    sequence = PulseSequence()
    p0 = Pulse(
        start=0,
        duration=50,
        amplitude=1.1,
        frequency=6_000_000_000,
        relative_phase=0.0,
        shape=Rectangular(),
        channel=0,
        type=PulseType.READOUT,
        qubit=0,
    )
    sequence.add(p0)
    program = ExecutePulseSequence(soc, cfg, sequence, qubits)

    with pytest.raises(ValueError):
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=1,
                load_pulses=True,
                progress=False,
                debug=False,
                average=True
        )


def test_execute_pulse_sequence_error_type(helpers):
    soc = QickSoc()
    cfg = helpers.get_qick_program_config()
    qubits = helpers.get_qubits()

    sequence = PulseSequence()
    p0 = Pulse(
        start=0,
        duration=50,
        amplitude=0.1,
        frequency=6_000_000_000,
        relative_phase=0.0,
        shape=Rectangular(),
        channel=0,
        type=PulseType.FLUX,
        qubit=0,
    )
    sequence.add(p0)
    program = ExecutePulseSequence(soc, cfg, sequence, qubits)

    with pytest.raises(NotImplementedError):
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=0,
                load_pulses=True,
                progress=False,
                debug=False,
                average=True
        )


# tests for the ExecuteSingleSweep class
def test_execute_single_sweep_init(helpers):
    """Tests ExecuteSingleSweep __init__ and initialize function"""
    soc = QickSoc()

    qubits = helpers.get_qubits()
    sequence = helpers.get_pulse_sequence(drives=1, readouts=1)
    sweep = helpers.get_sweeper(sequence)
    cfg = helpers.get_qick_program_config()

    program = ExecuteSingleSweep(soc, cfg, sequence, qubits, sweep)

    assert isinstance(program, ExecuteSingleSweep)


def test_execute_single_sweep_acquire(helpers):
    soc = QickSoc()

    qubits = helpers.get_qubits()

    for n_ro in [1, 2]:
        sequence = helpers.get_pulse_sequence(drives=1, readouts=n_ro)
        sweep = helpers.get_sweeper(sequence)
        cfg = helpers.get_qick_program_config()
        program = ExecuteSingleSweep(soc, cfg, sequence, qubits, sweep)
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=n_ro,
                load_pulses=True,
                progress=False,
                debug=False,
                average=False
        )
        assert i.shape == [1, n_ro, cfg.expts, 1000]
        assert q.shape == [1, n_ro, cfg.expts, 1000]


def test_execute_pulse_single_sweep_average(helpers):
    soc = QickSoc()
    qubits = helpers.get_qubits()

    for n_ro in [1, 2]:
        sequence = helpers.get_pulse_sequence(drives=1, readouts=n_ro)
        sweep = helpers.get_sweeper(sequence)
        cfg = helpers.get_qick_program_config()
        program = ExecuteSingleSweep(soc, cfg, sequence, qubits, sweep)
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=n_ro,
                load_pulses=True,
                progress=False,
                debug=False,
                average=True
        )
        assert i.shape == [1, n_ro, cfg.expts, 1]
        assert q.shape == [1, n_ro, cfg.expts, 1]


def test_execute_single_sweep_gaus(helpers):
    soc = QickSoc()
    qubits = helpers.get_qubits()

    sequence = helpers.get_pulse_sequence(readouts=1, drives=1, type_drive="gaus")
    sweep = helpers.get_sweeper(sequence)
    cfg = helpers.get_qick_program_config()

    program = ExecuteSingleSweep(soc, cfg, sequence, qubits, sweep)
    i, q = program.acquire(
            soc=soc,
            readouts_per_experiment=1,
            load_pulses=True,
            progress=False,
            debug=False,
            average=True
    )

    assert i.shape == [1, 1, cfg.expts, 1]
    assert q.shape == [1, 1, cfg.expts, 1]


def test_execute_single_sweep_drag(helpers):
    soc = QickSoc()
    qubits = helpers.get_qubits()

    sequence = helpers.get_pulse_sequence(readouts=1, drives=1, type_drive="drag")
    sweep = helpers.get_sweeper(sequence)
    cfg = helpers.get_qick_program_config()

    program = ExecuteSingleSweep(soc, cfg, sequence, qubits, sweep)
    i, q = program.acquire(
            soc=soc,
            readouts_per_experiment=1,
            load_pulses=True,
            progress=False,
            debug=False,
            average=True
    )

    assert i.shape == [1, 1, cfg.expts, 1]
    assert q.shape == [1, 1, cfg.expts, 1]


def test_execute_single_sweep_error_amplitude(helpers):
    soc = QickSoc()
    qubits = helpers.get_qubits()

    sequence = PulseSequence()
    p0 = Pulse(
        start=0,
        duration=50,
        amplitude=1.1,
        frequency=6_000_000_000,
        relative_phase=0.0,
        shape=Rectangular(),
        channel=0,
        type=PulseType.DRIVE,
        qubit=0,
    )
    sequence.add(p0)
    sweep = helpers.get_sweeper(sequence)
    cfg = helpers.get_qick_program_config(len(sweep.values))

    program = ExecuteSingleSweep(soc, cfg, sequence, qubits, sweep)

    with pytest.raises(ValueError):
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=1,
                load_pulses=True,
                progress=False,
                debug=False,
                average=True
        )


def test_execute_single_sweep_error_type(helpers):
    soc = QickSoc()
    qubits = helpers.get_qubits()

    sequence = PulseSequence()
    p0 = Pulse(
        start=0,
        duration=50,
        amplitude=0.1,
        frequency=6_000_000_000,
        relative_phase=0.0,
        shape=Rectangular(),
        channel=0,
        type=PulseType.FLUX,
        qubit=0,
    )
    sequence.add(p0)
    sweep = helpers.get_sweeper(sequence)
    cfg = helpers.get_qick_program_config(len(sweep.values))

    program = ExecuteSingleSweep(soc, cfg, sequence, qubits, sweep)

    with pytest.raises(NotImplementedError):
        i, q = program.acquire(
                soc=soc,
                readouts_per_experiment=0,
                load_pulses=True,
                progress=False,
                debug=False,
                average=True
        )


# test server
def test_tcpserver_init():
    host = "192.168.0.72"
    port = 6000
    with TCPServer((host, port), MyTCPHandler) as server:
        assert isinstance(server, TCPServer)
