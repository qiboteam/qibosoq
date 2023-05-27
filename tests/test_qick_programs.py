import qick

qick.QickSoc = None

from qibosoq.abstracts import Config, Pulse, Qubit
from qibosoq.qick_programs import ExecutePulseSequence, ExecuteSweeps


def test_execute_pulse_sequence():
    soc = {"us2cycles": 0}
    soc = qick.QickConfig("tests/qick_config.json")
    config = Config()
    sequence = []
    qubits = []

    program = ExecutePulseSequence(soc, config, sequence, qubits)
    assert isinstance(program, ExecutePulseSequence)
