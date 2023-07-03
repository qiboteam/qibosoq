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
    qubit = Qubit()

    server_commands = {
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
        "cfg": asdict(config),
        "sequence": [asdict(pulse) for pulse in sequence],
        "qubits": [asdict(qubit)],
        "readout_per_experiment": 1,
        "average": True,
    }

    i, q = qibosoq_execute(server_commands)

    print(f"{i} + 1j * {q}")

    > [[...]] + 1j * [[...]]

For multiple readout pulses, on the same dac:

.. code-block:: python

    from dataclasses import asdict
    from qibosoq.components.base import (
        Qubit,
        OperationCode,
        Config
        Sweeper,
        Parameter
    )
    from qibosoq.components.pulses import Rectangular

    pulse_1 = Rectangular(
                frequency = 6400, #MHz
                amplitude = 0.05,
                relative_phase = 0,
                start_delay = 0,
                duration = 0.04,
                name = "readout_pulse_0",
                type = "readout",
                dac = 1,
                adc = 0
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
    qubit = Qubit()

    server_commands = {
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
        "cfg": asdict(config),
        "sequence": [asdict(pulse) for pulse in sequence],
        "qubits": [asdict(qubit)],
        "readout_per_experiment": 2,
        "average": True,
    }

    i, q = qibosoq_execute(server_commands)

    print(f"{i} + 1j * {q}")

    > [[...,...]] + 1j * [[...,...]]

While if the measurement is done on a different adc the result will be slightly different:

.. code-block:: python

    from dataclasses import asdict
    from qibosoq.components.base import (
        Qubit,
        OperationCode,
        Config
        Sweeper,
        Parameter
    )
    from qibosoq.components.pulses import Rectangular

    pulse_1 = Rectangular(
                frequency = 6400, #MHz
                amplitude = 0.05,
                relative_phase = 0,
                start_delay = 0,
                duration = 0.04,
                name = "readout_pulse_0",
                type = "readout",
                dac = 2,
                adc = 1
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
    qubit = Qubit()

    server_commands = {
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
        "cfg": asdict(config),
        "sequence": [asdict(pulse) for pulse in sequence],
        "qubits": [asdict(qubit)],
        "readout_per_experiment": 2,
        "average": True,
    }

    i, q = qibosoq_execute(server_commands)

    print(f"{i} + 1j * {q}")

    > [[...],[...]] + 1j * [[...],[...]]

Execution of a sweeper experiment
"""""""""""""""""""""""""""""""""

A sweeper is a fast scan on a pulse parameter, executed on the FPGA logic to maximize the speed.

.. code-block:: python

    from dataclasses import asdict
    from qibosoq.components.base import (
        Qubit,
        OperationCode,
        Config
        Sweeper,
        Parameter
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
    qubit = Qubit()

    sweeper = Sweeper(
                parameters = [Parameter.AMPLITUDE],
                indexes = [0],
                starts = [0],
                stops = [1],
                expts = 100
    )

    server_commands = {
        "operation_code": OperationCode.EXECUTE_SWEEP,
        "cfg": asdict(config),
        "sequence": [asdict(pulse) for pulse in sequence],
        "qubits": [asdict(qubit)],
        "sweepers": [asdict(sweeper)],
        "readout_per_experiment": 1,
        "average": True,
    }

    i, q = qibosoq_execute(server_commands)

    print(f"{i} + 1j * {q}")

    > [[...,...,...,...]] + 1j * [[...,...,...,...]]


Example of a qubit spectroscopy
"""""""""""""""""""""""""""""""

As a real example, let's perform a qubit spectroscopy experiment.

We first import all the needed ``qibosoq`` components and ``matplotlib`` for plotting:

.. code-block:: python

    from dataclasses import asdict
    import numpy as np
    import matplotlib.pyplot as plt

    from qibosoq.components.base import (
        Qubit,
        OperationCode,
        Config
        Sweeper,
        Parameter
    )
    from qibosoq.components.pulses import Rectangular

In a qubit spectroscopy experiment we send two pulses: the first drives a qubit but has a variable frequency (we will use a sweeper) and the second is a fix readout pulse.

.. code-block:: python

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

Next, we can define the sweeper:

.. code-block:: python

    sweeper = Sweeper(
                parameters = [Parameter.FREQUENCY],
                indexes = [0],
                starts = [4154],
                stops = [4185],
                expts = 150
    )

Now we can define the :class:`qibosoq.components.base.Config` object and our :class:`qibosoq.components.base.Qubit` object:

.. code-block:: python

    config = Config(
        repetition_duration = 10,
        reps = 2000
    )
    qubit = Qubit(
        bias = 0.1,
        dac = 3
    )

And we can execute and plot the results:

.. code-block:: python

    server_commands = {
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
        "cfg": asdict(config),
        "sequence": [asdict(pulse) for pulse in sequence],
        "qubits": [asdict(qubit)],
        "readout_per_experiment": 1,
        "average": True,
    }

    i, q = qibosoq_execute(server_commands)

    frequency = np.linespace(sweeper.starts[0], sweeper.stops[0], expts)
    results = np.array(i[0][0]) + 1j * np.array(q[0][0]))
    plt.plot(frequency, np.abs(results))

.. image:: qubit_spectroscopy.png
