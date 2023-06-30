Examples
========

Let's now do some examples of how to use ``Qibosoq``.
Note that, for these examples to be run, the Qibosoq server needs to be running and reachable from the client.

A standard program will be executed with something like:

.. code-block:: python

    import json
    import socket

    HOST = "192.168.0.200"
    PORT = 6000

    def qibosoq_execute(server_commands):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((HOST, PORT))
            msg_encoded = bytes(json.dumps(server_commands), "utf-8")

            sock.send(len(msg_encoded).to_bytes(4, "big"))
            sock.send(msg_encoded)

            received = bytearray()
            while True:
                tmp = sock.recv(4096)
                if not tmp:
                    break
                received.append(tmp)

            results = json.loads(received.decode("utf-8"))
            return results["i"], results["q"]

    server_commands = {...}
    i_values, q_values = connect_qibosoq(server_commands)

Execution of a sequence of pulses
"""""""""""""""""""""""""""""""""

To send a simple pulse sequence, we just needed to define all the server_commands to be sent with the ``qibosoq_execute`` function:

.. code-block:: python

    from dataclasses import asdict
    from qibosoq.components.base import (
        Qubit,
        OperationCode,
        Config
    )
    from qibosoq.components.pulses import Rectangular

    pulse_1 = Rectangular(
                frequency = 5400, #MHz
                amplitude = 0.05,
                relative_phase = 0,
                start_delay = 0,
                duration = 0.04,
                name = "drive_pulse",
                type = "drive",
                dac = 0,
                adc = None
    )

    pulse_2 = Rectangular(
                frequency = 6400, #MHz
                amplitude = 0.05,
                relative_phase = 0,
                start_delay = 0.04,
                duration = 2,
                name = "readout_pulse",
                type = "readout",
                dac = 1,
                adc = 0
    )

    sequence = [pulse_1, pulse_2]
    config = Config()
    qubits = [Qubit()]

    server_commands = {
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
        "cfg": asdict(config),
        "sequence": [asdict(pulse) for pulse in sequence],
        "qubits": [asdict(qubit) for qubit in qubits],
        "readout_per_experiment": 1,
        "average": True,
    }

    i, q = qibosoq_execute(server_commands)

    print(f"Measured value: {i} + 1j * {q}")

Execution of a sweeper experiment
"""""""""""""""""""""""""""""""""

Example of a qubit spectroscopy
"""""""""""""""""""""""""""""""
