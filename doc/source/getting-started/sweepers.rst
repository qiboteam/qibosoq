Sweepers
""""""""

``Qibosoq`` supports several sweepers, all executable at the same time in multi-dimentionals scans.
A :class:`qibosoq.components.base.Sweeper` object can be istantiated with:

.. code-block:: python

    from qibosoq.components.base import Sweeper, Parameter

    sweeper = Sweeper(
                parameters = [Parameter.AMPLITUDE, Parameter.AMPLITUDE],
                indexes = [0, 1],
                starts = [0, -1],
                stops = [1, 0.5],
                expts = 100  # number of points for the scan
    )

    server_commands = {
        ...
        sweepers: [asdict(sweeper)]
    }

The parameters attribute contains a list of parameter from :class:`qibosoq.components.base.Parameter` so:
    * FREQUENCY
    * AMPLITUDE
    * RELATIVE_PHASE
    * DELAY
    * BIAS

.. warning::
    In the parameter class there is also a DURATION parameter, but this is not sweepable!

The indexes attribute refers to the index of the pulse to sweep in the ``sequence`` list (or, for BIAS sweepers, the index of the qubit in the ``qubit`` list).

A single sweeper can contain multiple parameters and perform update on different pulses, but note that it's still a 1-dimensional sweeper!
After each execution, every parameter will be updated accordingly to the value in ``starts`` and ``stops``.

To write a multi-dimentional sweeper we have to define multiple sweepers objects:

.. code-block:: python

    from qibosoq.components.base import Sweeper, Parameter

    sweeper_1 = Sweeper(
                parameters = [Parameter.AMPLITUDE],
                indexes = [0],
                starts = [0],
                stops = [1],
                expts = 100  # number of points for the scan
    )

    sweeper2 = Sweeper(
                parameters = [Parameter.AMPLITUDE],
                indexes = [1],
                starts = [-1],
                stops = [0.5],
                expts = 50  # number of points for the scan
    )

    server_commands = {
        ...
        sweepers: [sweeper.serialized, sweeper2.serialized]
    }

This will execute the sequence considering the matrix product of the swept parameters.

The final results (i and q) will have shape:
    * if averaged: (number_of_adc_chs, number_of_readouts, expts_sweeper1, expts_sweeper2...)
    * if not averaged: (number_of_adc_chs, number_of_readouts, expts_sweeper1, expts_sweeper2..., number of shots)

.. warning::
   The ``serialized`` property is required and it's not possible
   to use a simple ``asdict`` because Sweeper objects use, for starts and stops,
   non-json-serializable numpy arrays.
