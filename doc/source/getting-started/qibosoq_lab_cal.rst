Qibosoq - Qibolab - Qibocal
===========================

In these examples, we will see how to perform some basic qubit calibration experiments using the three levels of abstraction provided by the Qibo ecosystem:

- Qibosoq: basic pulse level and direct RFSoC connection
- Qibolab: higher pulse level and integrated control of the complete setup
- Qibocal: experiment level


Preparation pre-experiments
"""""""""""""""""""""""""""

For all the control modes, we are suppossing to have a qibosoq server running on board.

Qibosoq
-------

For a control through Qibosoq, no particular preparation is required.

In any case, for every experiment, we have to start the script with:

.. code-block:: python

  import json
  import socket
  import numpy as np
  import matplotlib.pyplot as plt

  from qibosoq.client import execute
  from qibosoq.components.base import (
      Qubit,
      OperationCode,
      Config
  )

  HOST = "192.168.0.200"
  PORT = 6000


Qibolab
-------

For Qibolab, we first need to setup the platform. This includes writing the ``platform.py`` and the ``platform.yml`` files. For more detailed instructions to write these experiments, please refer to the Qibolab documentation [ADD LINK].

In this section we will provide a base platform that includes only a RFSoC4x2 board (with o additional instruments) that controls a single qubit.

The path of these two files will have to be exported in an enviroment variable with:


.. code-block:: bash

  export QIBOLAB_PLATFORMS=<path-to-create-file>


File ``platform.py``:

.. code-block:: python

  import pathlib

  from qibolab.channels import Channel, ChannelMap
  from qibolab.instruments.rfsoc import RFSoC
  from qibolab.platform import Platform
  from qibolab.serialize import load_qubits, load_runcard, load_settings

  NAME = "my_platform"  # name of the platform
  ADDRESS = "192.168.0.200"  # ip adress of the RFSoC
  PORT = 6000  # port of the controller

  # path to runcard file with calibration parameter
  RUNCARD = pathlib.Path(__file__).parent / "platform.yml"


  def create(runcard_path=RUNCARD):
      # Instantiate controller instruments
      controller = RFSoC(NAME, ADDRESS, PORT)

      # Create channel objects and port assignment
      channels = ChannelMap()
      channels |= Channel("readout", port=controller[1])  # QICK DAC number
      channels |= Channel("feedback", port=controller[0])  # QICK ADC number
      channels |= Channel("drive", port=controller[0])  # QICK DAC number

      # create qubit objects
      runcard = load_runcard(runcard_path)
      qubits, pairs = load_qubits(runcard)
      # assign channels to qubits
      qubits[0].readout = channels["readout"]
      qubits[0].feedback = channels["feedback"]
      qubits[0].drive = channels["drive"]

      instruments = {controller.name: controller}
      settings = load_settings(runcard)
      return Platform(NAME, qubits, pairs, instruments, settings, resonator_type="3D")


File ``platform.yml``:

.. code-block:: yaml

  nqubits: 1
  qubits: [0]
  topology: []
  settings: {nshots: 1024, relaxation_time: 70000, sampling_rate: 9830400000}

  native_gates:
      single_qubit:
          0:
              RX:  # pi-pulse for X gate
                  duration: 40
                  amplitude: 0.5
                  frequency: 5_500_000_000
                  shape: Gaussian(3)
                  type: qd
                  start: 0
                  phase: 0

              MZ:  # measurement pulse
                  duration: 2000
                  amplitude: 0.02
                  frequency: 7_370_000_000
                  shape: Rectangular()
                  type: ro
                  start: 0
                  phase: 0

      two_qubits: {}
  characterization:
      single_qubit:
          0:
              readout_frequency: 7370000000
              drive_frequency: 5500000000
              anharmonicity: 0
              Ec: 0
              Ej: 0
              g: 0
              T1: 0.0
              T2: 0.0
              threshold: 0.0
              iq_angle: 0.0
              mean_gnd_states: [0.0, 0.0]
              mean_exc_states: [0.0, 0.0]


Every experiment, will then start with:

.. code-block:: python

  from qibolab import create_platform
  from qibolab import AcquisitionType, AveragingMode, ExecutionParameters

  from qibolab.pulses import (
      DrivePulse,
      ReadoutPulse,
      PulseSequence,
  )

  # Define platform and load specific runcard
  platform = create_platform("platform")

Qibocal
-------

For Qibocal, we first need to setup Qibolab as presented in the last section.
Note then that, for Qibocal "programs" we need a new file ``actions.yml`` that will contain all the parameters required for the experiments: this file will be presented for all the different experiments.
For Qibosoq and Qibolab "programs", a standard Python script or a Jupyter Notebook will suffice.


Time Of Flight
""""""""""""""

Qibosoq
-------

.. code-block:: python

  from qibosoq.components.pulses import Rectangular

  pulse = Rectangular(
            frequency = 7400, #MHz
            amplitude = 0.5,
            relative_phase = 0,
            start_delay = 0,
            duration = 1,
            name = "readout_pulse",
            type = "readout",
            dac = 1,
            adc = 0
  )

  sequence = [pulse]
  config = Config(
            repetition_duration=0.05,
            adc_trig_offset=0,
            reps=1,
            soft_avgs=1000,
            average=False
  )
  qubit = Qubit()

  server_commands = {
      "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE_RAW,
      "cfg": config,
      "sequence": sequence,
      "qubits": [qubit],
  }

  i, q = execute(server_commands, HOST, PORT)

  plt.plot(np.abs(np.array(i) + 1j * np.array(q))


Qibolab
-------

.. code-block:: python

  from qibolab.pulses import Rectangular

  # Define PulseSequence
  sequence = PulseSequence()

  # Add some pulses to the pulse sequence
  sequence.add(
      ReadoutPulse(
          start=0,
          frequency=7_400_000_000,
          amplitude=0.5,
          duration=1000,
          phase=0,
          shape=Rectangular(),
      )
  )

  options=ExecutionParameters(
      nshots=1000,
      relaxation_time=50,
      acquisition_type=AcquisitionType.RAW,
      averaging_mode=AveragingMode.CYCLIC,
  )
  results = platform.execute_pulse_sequence(ps, options=options)

  plt.plot(results[sequence[0].serial].magnitude)

Qibocal
-------

File ``actions.yml``.

.. code-block:: yaml

  platform: platform
  qubits: [0]
  actions:

    - id: time of flight
      priority: 0
      operation: time_of_flight_readout
      parameters:
        nshots: 1000
        readout_amplitude: 0.5






Resonator Spectroscopy
""""""""""""""""""""""

Qubit Spectroscopy
""""""""""""""""""

Rabi Oscillations
"""""""""""""""""

T1
""

Single Shot
"""""""""""

Randomized Benchmarking
"""""""""""""""""""""""
