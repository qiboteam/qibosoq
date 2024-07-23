
Biases and Pulses
=================

Qibosoq supports the execution of modulated fast pulses, called here just pulses, and continuous DC biases.

Biases
""""""

By bias we mean a DC current that gets turned on before the pulse sequence execution and gets turn off just at the end.
Note that some care may be needed to fire continuous un-modulated pulses since the board itself may have baluns at the outputs.

Biases are controlled via the :class:`qibosoq.components.base.Qubit` object:

.. testcode:: python

    from qibosoq.components.base import Qubit

    qubit = Qubit(
        bias = 0.1,
        dac = 3
    )

The bias parameter is a value relative to the maximum output voltage of the used dac so it's defined in the range [-1, 1].


Pulses
""""""

Differently from the biases, the pulses have a shape, a duration and are modulated.
In ``Qibosoq`` there is a object :class:`qibosoq.components.pulses.Pulse`:

.. testcode:: python

    from qibosoq.components.pulses import Pulse

    pulse = Pulse(
        frequency = 4000,    # float in MHz
        amplitude = 0.5,     # float in [-1, 1]
        relative_phase = 0,  # int in degrees
        start_delay = 0,     # float in us
        duration = 1,        # float in us
        name = "id",         # str
        type = "drive",      # str in {"readout", "drive"}
        dac = 1,             # int
        adc = None,          # optional int
    )


* The ``start_delay`` is the difference in start time between this pulse and the one before it.
  We can consider the execution of a pulse always divided in two moments:

    * wait ``start_delay`` if it's not zero
    * fire the pulse

* The ``name`` parameter can be chosen to be whatever, but should be a unique identifier of the pulse.
* The adc parameter is not needed for drive pulse, but it is for readout pulses. Every readout pulse is composed of a pulse fired through the dac and acquired by the adc, so both are required.


While the :class:`qibosoq.components.pulses.Pulse` object can be used in the client, it cannot be used in execution time.
In fact, the server expect a Pulse with a shape.
The shape objects inherits from :class:`qibosoq.components.pulses.Pulse` and share the same parameter + eventually others (... here are the :class:`qibosoq.components.pulses.Pulse` parameters):

.. code-block:: python

    from qibosoq.components.pulses import Rectangular, Gaussian, Drag, Arbitrary, FlatTop, Hann

    pulse = Rectangular(...)

    pulse = Gaussian(
        ...
        rel_sigma = 5,  # float, sigma values as a fraction of the duration
    )

    pulse = Drag(
        ...
        rel_sigma = 5,  # float, sigma values as a fraction of the duration
        beta = 10,      # float (drag beta parameter)
    )

    pulse = FlatTop(
        ...
        rel_sigma = 5,  # float, sigma values as a fraction of the duration
    )

    pulse = Arbitrary(
        ...
        i_values = [...],  # list of floats
        q_values = [...],      # list of floats
    )

    pulse = Hann(...)

Measurements
""""""""""""

From version ``0.1.1``, ``Qibosoq`` supports the execution of measurements decoupled from pulses. This allows to perform acquisition from an ADC without the need of genereting a pulse from a DAC.

.. testcode:: python

   from qibosoq.components.pulses import Measurement

   meas = Measurement(
        type = "readout",
        frequency = 6400,    # float in MHz
        start_delay = 0,     # float in us
        duration = 1,        # float in us
        dac = 1,             # int
        adc = 0,          # int
   )


The frequency parameter is the one of the signal we want to acquire.
This is required by the downspampling scheme, to perform ADC acquisitions.

The DAC number, that could seem useless, can be used to ensure frequency matching between the ADC and a DAC. Namely, DACs and ADCs have different memory registers and we usually want to esure that have the same frequencies stored so that relative phases do not change during the experiment.
