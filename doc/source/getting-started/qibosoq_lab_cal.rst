Qibosoq - Qibolab - Qibocal
===========================

In these examples, we will see how to perform some basic qubit calibration experiments using the three levels of abstraction provided by the Qibo ecosystem:

- Qibosoq: basic pulse level and direct RFSoC connection
- Qibolab: higher pulse level and integrated control of the complete setup
- Qibocal: experiment level

With these three packages, we perform the exact same experiments, showcasing how to implement the same program with different complexity levels.
In particular, Qibosoq is the most base language and requires explicit definition of all the pulses, sweepers and experiment parameters. Qibolab is slightly more intuitive, but still requires to define all the experiment. Qibocal, on the other hand, leverages experiments already coded.

For these experiments we are considering to not yet have the final calibration parameters, but for the sake of clarity, the following parameters are final ones of the calibration:

Lines:

- Drive line DAC: 0
- Readout line DAC: 1
- Feedback line ADC: 0

Qubit parameters:

- Qubit frequency: 5_755_000_000 Hz
- Pi-pulse duration: 43 ns
- Pi-pulse amplitude: 0.02
- Pi-pulse shape: Gaussian(3)

Resonator parameters:

- Resonator frequency: 6_953_000_000 Hz
- Measurement duration: 1000 ns
- Measurement amplitude: 0.1
- Measurement shape: Rectangular()

Experiments parameters:

- Relaxation time: 50_000 ns

Preparation pre-experiments
"""""""""""""""""""""""""""

For all the control modes, we are supposing to have a Qibosoq server running on board.

Qibosoq
-------

For control through Qibosoq, no particular preparation is required.

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

For Qibolab, we first need to setup the platform. This includes writing the ``my_platform.py`` and the ``my_platform.yml`` files. For more detailed instructions to write these experiments, please refer to the Qibolab documentation [ADD LINK].

In this section we will provide a base platform that includes only a RFSoC4x2 board (with o additional instruments) that controls a single qubit.

The path of these two files will have to be exported in an environment variable with:


.. code-block:: bash

  export QIBOLAB_PLATFORMS=<path-to-platform-files>


File ``my_platform.py``:

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


File ``my_platform.yml`` (note that this file is just a starting one, with the parameters not completely calibrated):

.. code-block:: yaml

  nqubits: 1
  qubits: [0]
  topology: []
  settings: {nshots: 1024, relaxation_time: 50_000}

  native_gates:
      single_qubit:
          0:
              RX:  # pi-pulse for X gate
                  duration: 40
                  amplitude: 0.1
                  frequency: 5_700_000_000
                  shape: Gaussian(3)
                  type: qd
                  start: 0
                  phase: 0

              MZ:  # measurement pulse
                  duration: 1000
                  amplitude: 0.1
                  frequency: 7_000_000_000
                  shape: Rectangular()
                  type: ro
                  start: 0
                  phase: 0

      two_qubits: {}
  characterization:
      single_qubit:
          0:
              readout_frequency: 7000000000
              drive_frequency: 5700000000
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
  from qibosoq.components.pulses import Rectangular

  HOST = "192.168.0.200"
  PORT = 6000

  pulse = Rectangular(
            frequency = 7000, #MHz
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
            repetition_duration=50, # us
            adc_trig_offset=0,
            reps=1,
            soft_avgs=1000,
            average=True
  )
  qubit = Qubit()

  server_commands = {
      "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE_RAW,
      "cfg": config,
      "sequence": sequence,
      "qubits": [qubit],
  }

  i, q = execute(server_commands, HOST, PORT)

  plt.plot(np.abs(np.array(i[0][0]) + 1j * np.array(q[0][0]))


Qibolab
-------

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

  # Define PulseSequence
  sequence = PulseSequence()

  readout_pulse = platform.create_MZ_pulse(qubit=0, start=0)
  readout_pulse.amplitude = 0.5
  sequence.add(readout_pulse)

  options=ExecutionParameters(
      nshots=1000,
      relaxation_time=50_000, # ns
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

Qibosoq
-------

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
  from qibosoq.components.pulses import Rectangular

  HOST = "192.168.0.200"
  PORT = 6000

  frequencies = np.arange(6800, 7200, 1)

  pulse = Rectangular(
            frequency = 7000, #MHz
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
            repetition_duration=50,
            adc_trig_offset=200,
            reps=1000,
            average=True
  )
  qubit = Qubit()

  server_commands = {
      "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
      "cfg": config,
      "sequence": sequence,
      "qubits": [qubit],
  }

  results = []
  for freq in frequencies:
      server_commands["sequence"][0].frequency = freq
      i, q = execute(server_commands, HOST, PORT)
      results.append(np.abs(np.array(i[0][0]) + 1j * np.array(q[0][0])))

  plt.plot(results)


Qibolab
-------

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

  # Define PulseSequence
  sequence = PulseSequence()

  # Add some pulses to the pulse sequence
  readout_pulse = platform.create_MZ_pulse(qubit=0, start=0)
  readout_pulse.amplitude = 0.5
  sequence.add(readout_pulse)

  options=ExecutionParameters(
      nshots=1000,
      relaxation_time=50,
      acquisition_type=AcquisitionType.INTEGRATION,
      averaging_mode=AveragingMode.CYCLIC,
  )
  sweeper = Sweeper(
      parameter=Parameter.frequency,
      values=np.arange(-2e8, +2e8, 1e6),
      pulses=[readout_pulse],
      type=SweeperType.OFFSET,
  )

  results = platform.sweep(sequence, options, sweeper)

  frequencies = np.arange(-2e8, +2e8, 1e6) + readout_pulse.frequency
  plt.plot(frequencies, amplitudes)

Qibocal
-------

File ``actions.yml``.

.. code-block:: yaml

  platform: platform
  qubits: [0]
  actions:

    - id: resonator high power
      priority: 0
      operation: resonator_spectroscopy
      parameters:
        power_level: high
        freq_width: 400_000_000
        freq_step: 1_000_000
        amplitude: 0.5
        nshots: 1000


Qubit Spectroscopy
""""""""""""""""""

Qibosoq
-------

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
  from qibosoq.components.pulses import Rectangular

  HOST = "192.168.0.200"
  PORT = 6000

  pulse_1 = Rectangular(
              frequency = 5400, #MHz
              amplitude = 0.1,
              relative_phase = 0,
              start_delay = 0,
              duration = 2,
              name = "drive_pulse",
              type = "drive",
              dac = 0,
              adc = None
  )

  pulse_2 = Rectangular(
              frequency = 6953, #MHz
              amplitude = 0.1,
              relative_phase = 0,
              start_delay = 2,
              duration = 1,
              name = "readout_pulse",
              type = "readout",
              dac = 1,
              adc = 0
  )

  sequence = [pulse_1, pulse_2]

  sweeper = Sweeper(
              parameters = [Parameter.FREQUENCY],
              indexes = [0],
              starts = [5400],
              stops = [6000],
              expts = 600
  )

  config = Config(
      repetition_duration = 50,
      reps = 1000
  )
  qubit = Qubit()

  server_commands = {
      "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
      "cfg": config,
      "sequence": sequence,
      "qubits": [qubit],
      "sweepers": [sweeper],
  }

  i, q = execute(server_commands, HOST, PORT)

  frequency = np.linespace(sweeper.starts[0], sweeper.stops[0], expts)
  results = np.array(i[0][0]) + 1j * np.array(q[0][0]))
  plt.plot(frequency, np.abs(results))


Qibolab
-------

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

  sequence = PulseSequence()
  drive_pulse = platform.create_RX_pulse(qubit=0, start=0)
  drive_pulse.duration = 2000
  drive_pulse.amplitude = 0.1
  readout_pulse = platform.create_MZ_pulse(qubit=0, start=drive_pulse.finish)
  sequence.add(drive_pulse)
  sequence.add(readout_pulse)

  # allocate frequency sweeper
  sweeper = Sweeper(
      parameter=Parameter.frequency,
      values=np.arange(-3e8, +3e8, 1e6),
      pulses=[drive_pulse],
      type=SweeperType.OFFSET,
  )
  options = ExecutionParameters(
      nshots=1000,
      relaxation_time=50,
      averaging_mode=AveragingMode.CYCLIC,
      acquisition_type=AcquisitionType.INTEGRATION,
  )

  results = platform.sweep(sequence, options, sweeper)

  amplitudes = results[readout_pulse.serial].magnitude
  frequencies = np.arange(-3e8, +3e8, 1e6) + drive_pulse.frequency

  plt.plot(frequencies, plt.amplitudes)


Qibocal
-------

File ``actions.yml``.

.. code-block:: yaml

  platform: platform
  qubits: [0]
  actions:

    - id: qubit spectroscopy
      priority: 0
      operation: qubit_spectroscopy
      parameters:
        drive_amplitude: 0.01
        drive_duration: 2000
        freq_width: 600_000_000
        freq_step: 1_000_000
        nshots: 1000

Rabi Oscillations (amplitude)
"""""""""""""""""""""""""""""

Qibosoq
-------

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
  from qibosoq.components.pulses import Rectangular, Gaussian

  HOST = "192.168.0.200"
  PORT = 6000

  pulse_1 = Gaussian(
              frequency = 5755, #MHz
              amplitude = 0.01,
              relative_phase = 0,
              start_delay = 0,
              duration = 0.043,
              rel_sigma = 3,
              name = "drive_pulse",
              type = "drive",
              dac = 0,
              adc = None
  )

  pulse_2 = Rectangular(
              frequency = 6953, #MHz
              amplitude = 0.1,
              relative_phase = 0,
              start_delay = 0.043,
              duration = 1,
              name = "readout_pulse",
              type = "readout",
              dac = 1,
              adc = 0
  )

  sequence = [pulse_1, pulse_2]

  sweeper = Sweeper(
              parameters = [Parameter.AMPLITUDE],
              indexes = [0],
              starts = [0],
              stops = [1],
              expts = 100
  )

  config = Config(
      repetition_duration = 50,
      reps = 1000
  )
  qubit = Qubit()

  server_commands = {
      "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
      "cfg": config,
      "sequence": sequence,
      "qubits": [qubit],
      "sweepers": [sweeper],
  }

  i, q = execute(server_commands, HOST, PORT)

  amplitudes = np.linespace(sweeper.starts[0], sweeper.stops[0], expts)
  results = np.array(i[0][0]) + 1j * np.array(q[0][0]))
  plt.plot(amplitudes, np.abs(results))


Qibolab
-------

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

  sequence = PulseSequence()
  drive_pulse = platform.create_RX_pulse(qubit=0, start=0)
  readout_pulse = platform.create_MZ_pulse(qubit=0, start=drive_pulse.finish)
  sequence.add(drive_pulse)
  sequence.add(readout_pulse)

  # allocate frequency sweeper
  sweeper = Sweeper(
      parameter=Parameter.amplitude,
      values=np.arange(0, 1, 0.01),
      pulses=[drive_pulse],
      type=SweeperType.ABSOLUTE,
  )
  options = ExecutionParameters(
      nshots=1000,
      relaxation_time=50,
      averaging_mode=AveragingMode.CYCLIC,
      acquisition_type=AcquisitionType.INTEGRATION,
  )

  results = platform.sweep(sequence, options, sweeper)

  magnitudes = results[readout_pulse.serial].magnitude
  amplitudes = np.arange(0, 1, 0.01)

  plt.plot(magnitudes, amplitudes)

Qibocal
-------

File ``actions.yml``.

.. code-block:: yaml

  platform: platform
  qubits: [0]
  actions:

  - id: rabi
    priority: 0
    operation: rabi_amplitude
    # main: single shot classification
    parameters:
      min_amp_factor: 0.0
      max_amp_factor: 10
      step_amp_factor: 0.1
      pulse_length: 43

T1
""

Qibosoq
-------

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
  from qibosoq.components.pulses import Rectangular, Gaussian

  HOST = "192.168.0.200"
  PORT = 6000

  pulse_1 = Gaussian(
              frequency = 5755, #MHz
              amplitude = 0.02,
              relative_phase = 0,
              start_delay = 0,
              duration = 0.043,
              rel_sigma = 3,
              name = "drive_pulse",
              type = "drive",
              dac = 0,
              adc = None
  )

  pulse_2 = Rectangular(
              frequency = 6953, #MHz
              amplitude = 0.1,
              relative_phase = 0,
              start_delay = 0.043,
              duration = 1,
              name = "readout_pulse",
              type = "readout",
              dac = 1,
              adc = 0
  )

  sequence = [pulse_1, pulse_2]

  sweeper = Sweeper(
              parameters = [Parameter.DELAY],
              indexes = [1],
              starts = [0.043],
              stops = [100.043],
              expts = 100
  )

  config = Config(
      repetition_duration = 50,
      reps = 1000
  )
  qubit = Qubit()

  server_commands = {
      "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
      "cfg": config,
      "sequence": sequence,
      "qubits": [qubit],
      "sweepers": [sweeper],
  }

  i, q = execute(server_commands, HOST, PORT)

  delays = np.linespace(sweeper.starts[0], sweeper.stops[0], expts)
  results = np.array(i[0][0]) + 1j * np.array(q[0][0]))
  plt.plot(delays, np.abs(results))

Qibolab
-------

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

  sequence = PulseSequence()
  drive_pulse = platform.create_RX_pulse(qubit=0, start=0)
  readout_pulse = platform.create_MZ_pulse(qubit=0, start=drive_pulse.finish)
  sequence.add(drive_pulse)
  sequence.add(readout_pulse)

  # allocate frequency sweeper
  sweeper = Sweeper(
      parameter=Parameter.START,
      values=np.arange(0, 100_000, 1000).astype(int),
      pulses=[readout_pulse],
      type=SweeperType.OFFSET,
  )
  options = ExecutionParameters(
      nshots=1000,
      relaxation_time=50,
      averaging_mode=AveragingMode.CYCLIC,
      acquisition_type=AcquisitionType.INTEGRATION,
  )

  results = platform.sweep(sequence, options, sweeper)

  magnitudes = results[readout_pulse.serial].magnitude
  start_times = np.arange(0, 100_000, 1000)

  plt.plot(start_times, magnitudes)

Qibocal
-------

File ``actions.yml``.

.. code-block:: yaml

  platform: platform
  qubits: [0]
  actions:

  - id: t1
    priority: 0
    operation: t1
    #main: ramsey
    parameters:
      delay_before_readout_start: 0
      delay_before_readout_end: 100_000
      delay_before_readout_step: 1000

Classification experiment
"""""""""""""""""""""""""

Qibosoq
-------

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
  from qibosoq.components.pulses import Rectangular, Gaussian

  HOST = "192.168.0.200"
  PORT = 6000

  pulse_1 = Gaussian(
              frequency = 5755, #MHz
              amplitude = 0.02,
              relative_phase = 0,
              start_delay = 0,
              duration = 0.043,
              rel_sigma = 3,
              name = "drive_pulse",
              type = "drive",
              dac = 0,
              adc = None
  )

  pulse_2 = Rectangular(
              frequency = 6953, #MHz
              amplitude = 0.1,
              relative_phase = 0,
              start_delay = 0.043,
              duration = 1,
              name = "readout_pulse",
              type = "readout",
              dac = 1,
              adc = 0
  )

  sequence = [pulse_1, pulse_2]

  config = Config(
      repetition_duration = 50,
      reps = 10000,
      average = False
  )
  qubit = Qubit()

  server_commands = {
      "operation_code": OperationCode.EXECUTE_PULSE_SEQUENCE,
      "cfg": config,
      "sequence": sequence,
      "qubits": [qubit],
  }

  i, q = execute(server_commands, HOST, PORT)

  plt.scatter(i, q)

Qibolab
-------

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

  sequence = PulseSequence()
  drive_pulse = platform.create_RX_pulse(qubit=0, start=0)
  readout_pulse = platform.create_MZ_pulse(qubit=0, start=drive_pulse.finish)
  sequence.add(drive_pulse)
  sequence.add(readout_pulse)

  options = ExecutionParameters(
      nshots=10000,
      relaxation_time=50,
      averaging_mode=AveragingMode.SINGLESHOT,
      acquisition_type=AcquisitionType.INTEGRATION,
  )

  results = platform.sweep(sequence, options, sweeper)

  plt.plot(results.i, results.q)

Qibocal
-------

File ``actions.yml``.

.. code-block:: yaml

  platform: platform
  qubits: [0]
  actions:

  - id: single shot classification
    priority: 0
    operation: single_shot_classification
    parameters:
      nshots: 10000

Randomized Benchmarking
"""""""""""""""""""""""

Qibosoq
-------

Qibolab
-------

Qibocal
-------
