Communication protocol
======================

Originally conceived as a component of ``Qibolab``, ``Qibosoq``, has since evolved into an independent entity, no longer reliant on ``Qibolab`` for its functionality.
Due to is standalone nature, it can now be utilized by any application that adheres to the ``Qibosoq`` communication protocol.

Receiving commands
""""""""""""""""""

The protocol for receiving commands, from the server point of view, is composed of two section:

* an initial handshake
* a single serialized commands dictionary is send

In the initial handshake, qibosoq expects 4 bytes representing, in the big endian byte-ordering, an integer N.
This integer is the size, in bytes, of the command dictionary that the server has to receive just after the handshake.

After the handshake, Qibosoq will wait to receive extacly N bytes.
These bytes represent the commands and are converted back to dictionary form using ``json.loads``.

The dictionary has to contain the following elements:


.. code-block::

    commands = {
        "operation_code": int,
        "cfg": {
            "soft_avgs": int,
            "reps": int,
            "repetition_duration": int,
            "adc_trig_offset": int
        }
        "sequence": list,
        "qubits": list,
        "average": bool,
    }

If the operation code is ``OperationCode.EXECUTE_SWEEPS = 3`` then also another list has to be provided

.. code-block::

    commands = {
        ...
        "sweepers": list
    }

Let's now analyze element by element every key and value contained in the dictionary.


operation_code
--------------

The operation code can be an int from 1 to 3, but it is better to initially have it as a :class:`qibosoq.components.base.OperationCode` instance.
Therefore, it can assume three different values:

#. EXECUTE_PULSE_SEQUENCE: to execute an arbitrary pulse sequence (with a ``AveragerQickProgram``) and a standard integrated acquisition
#. EXECUTE_PULSE_SEQUENCE_RAW: to execute an arbitrary pulse sequence, but with a non integrated acquistion
#. EXECUTE_SWEEPS: to execute experiments that involve sweepers, fast scan of pulse parameters, with a ``NDAveragerQickProgram``

.. code-block:: python

    from qibosoq.components.base import OperationCode

    commands = {
        ...
        "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE
    }


cfg
---

The ``cfg`` key corresponds to another, nested, dictionary.
This can be easily obtained from a :class:`qibosoq.components.base.Config` object.

.. code-block:: python

    from qibosoq.components.base import Config
    from dataclasses import asdict

    cfg = Config(...)
    commands = {
        ...
        "cfg": asdict(cfg),
    }

Just after qibosoq has received all the data, it converts ``cfg`` back into is object form.


sequence
--------

The ``sequence`` key links to list of :class:`qibosoq.components.pulses.Pulse` objects in the form of dictionaries.
Also this dictionary can be obtained with ``asdict``.

.. code-block:: python

    from qibosoq.components.pulses import Rectangular, Drag
    from dataclasses import asdict

    sequence = []
    sequence.append(Rectangular(...))
    sequence.append(Drag(...))

    commands = {
        ...
        "sequence": [asdict(pulse) for pulse in sequence],
    }


Note that ``qibosoq`` will convert these pulses back to the respective shape objects, so a general :class:`qibosoq.components.pulses.Pulse` will raise an error.


qubits
------

The ``qubits`` key links to list of :class:`qibosoq.components.base.Qubit` objects in the form of dictionaries.
Also this dictionary can be obtained with ``asdict``.

.. code-block:: python

    from qibosoq.components.base import Qubit
    from dataclasses import asdict

    qubits = []
    qubits.append(Qubit(...))
    qubits.append(Qubit(...))

    commands = {
        ...
        "qubits": [asdict(qubit) for qubit in qubits],
    }


sweepers
--------

This key is used and requested only if operation_code is ``EXECUTE_SWEEPS`` and is a list of :class:`qibosoq.components.base.Sweeper` objects in dictionary form:

.. code-block:: python

    from qibosoq.components.base import Sweeper
    from dataclasses import asdict

    sweepers= []
    sweepers.append(Sweeper(...))
    sweepers.append(Sweeper(...))

    commands = {
        ...
        "sweepers": [asdict(sweep) for sweep in sweepers],
    }


average
-------

This is just a simple boolean value, that indicates to qibosoq whether or no average the results.


.. code-block:: python

    commands = {
        ...
        "average": True,
    }


Sending results
"""""""""""""""

For every possible ``operation_code``, ``qibosoq`` has to return some values.
These are returned in a json-serialized dictionary:

.. code-block:: python

    results = {"i": list, "q": list}
    to_send = bytes(json.dumps(results), "utf-8")


The value of "i" and "q" are the measured quandrature values.
The shape of "i" ("q") is

* for operation_code ``EXECUTE_PULSE_SEQUENCE`` and ``EXECUTE_PULSE_SEQUENCE_RAW``
    * if ``average`` is false: (adc_channels, number_of_readouts, number_of_shots)
    * if ``average`` is true: (adc_channels, number_of_readouts)
* for operation_code ``EXECUTE_SWEEPS``
    * if ``average`` is false: (adc_channels, number_of_readouts, number_of_points, number_of_shots)
    * if ``average`` is true: (adc_channels, number_of_readouts, number_of_points)

Note that the server can also send a different thing: errors.
When the server encounters an error, in the communication protocol, in the json de-serialization or during the execution, it does not crash but raises an error that get's logged in the server and sent through the open socket so that also the client can see it.
