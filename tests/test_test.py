import os
import pathlib
from unittest import mock

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


# @pytest.fixture
# def soc():
#    qibosoq.configuration.IS_MULTIPLEXED = True
#
#    def mock():
#        pass
#
#    soc = qick.QickConfig(str(pathlib.Path(__file__).parent / "qick_config_multiplexed.json"))
#    soc.reset_gens = mock
#    return soc


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
        Sweeper(expts=1000, parameter=[Parameter.FREQUENCY], starts=[0], stops=[100], indexes=[0]),
        Sweeper(expts=1000, parameter=[Parameter.AMPLITUDE], starts=[0], stops=[100], indexes=[0]),
        Sweeper(expts=1000, parameter=[Parameter.RELATIVE_PHASE], starts=[0], stops=[100], indexes=[0]),
    )

    qubits = [Qubit()]

    program = ExecuteSweeps(soc, config, sequence, qubits, sweepers)
    return program


def test_execute_sweeps_init(execute_sweeps):
    assert isinstance(execute_sweeps, ExecuteSweeps)


# @pytest.fixture
# def soc():
#    qibosoq.configuration.IS_MULTIPLEXED = True
#
#    def mock():
#        pass
#
#    soc = qick.QickConfig(str(pathlib.Path(__file__).parent / "qick_config_multiplexed.json"))
#    soc.reset_gens = mock
#    return soc
#
# def execute_pulse_sequence(soc):
#    qibosoq.configuration.IS_MULTIPLEXED = True
#    config = Config()
#    sequence = [
#        Pulse(
#            frequency=100,
#            amplitude=0.1,
#            relative_phase=0,
#            start=0,
#            duration=0.04,
#            name="pulse0",
#            type="drive",
#            dac=6,
#            adc=0,
#            shape="rectangular",
#        ),
#        Pulse(
#            frequency=100,
#            amplitude=0.1,
#            relative_phase=0,
#            start=0,
#            duration=0.04,
#            name="pulse1",
#            type="readout",
#            dac=6,
#            adc=0,
#            shape="rectangular",
#        ),
#    ]
#    qubits = [Qubit()]
#
#    program = ExecutePulseSequence(soc, config, sequence, qubits)
#    return program
#
# def test_something_t(soc):
#    qibosoq.configuration.IS_MULTIPLEXED = True
#    program = execute_pulse_sequence(soc)
#
#
##def test_something_f():
##    print('GLOBALS false: ', globals())
##    nsoc = soc(False)
##    program = execute_pulse_sequence(nsoc)
