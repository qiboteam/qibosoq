"""Photon counting experiment."""

# following
# JOHANN BOCKSEVERIN
# superconducting qubit readout
# in theory, experiment and simulation

import numpy as np

from qibosoq.client import execute
from qibosoq.components.base import Config, OperationCode, Parameter, Qubit, Sweeper
from qibosoq.components.pulses import Rectangular

HOST = "192.168.0.200"
PORT = 6000

# readout pulse
RO_FREQUENCY = 5400  # MHz
RO_DURATION = 1  # microsecond
RO_AMPLITUDE = 0.1

SW_INIT_AMP = 0
SW_STOP_AMP = 1
SW_STEP_AMP = 0.1

# drive pulse
DR_FREQUENCY = 5400  # MHz
DR_DURATION = 1  # microsecond
DR_AMPLITUDE = 0.1

SW_INIT_FR = 100
SW_STOP_FR = 200
SW_STEP_FR = 1

# channels
DR_DAC = 0
RO_DAC = 1
RO_ADC = 0

# general
NSHOTS = 1000
RELAX_TIME = 100  # clock ticks?

pulse_1 = Rectangular(
    frequency=RO_FREQUENCY,
    amplitude=1,
    relative_phase=0,
    start_delay=0,
    duration=RO_DURATION,
    name="fill_pulse",
    type="drive",
    dac=RO_DAC,
    adc=None,
)

pulse_2 = Rectangular(
    frequency=DR_FREQUENCY,
    amplitude=DR_AMPLITUDE,
    relative_phase=0,
    start_delay=RO_DURATION,
    duration=DR_DURATION,
    name="drive_pulse",
    type="drive",
    dac=DR_DAC,
    adc=None,
)

pulse_3 = Rectangular(
    frequency=RO_FREQUENCY,
    amplitude=RO_AMPLITUDE,
    relative_phase=0,
    start_delay=0,
    duration=RO_DURATION,
    name="measurement",
    type="readout",
    dac=RO_DAC,
    adc=RO_ADC,
)

sequence = [pulse_1, pulse_2, pulse_3]

amp_expts = (SW_STOP_AMP - SW_INIT_AMP) // SW_STOP_AMP
sweeper_ro = Sweeper(
    parameters=[Parameter.AMPLITUDE],
    indexes=[0],
    starts=[SW_INIT_AMP],
    stops=[SW_STOP_AMP],
    expts=amp_expts,
)
fr_expts = (SW_STOP_FR - SW_INIT_FR) // SW_STOP_FR
sweeper_spec = Sweeper(
    parameters=[Parameter.FREQUENCY],
    indexes=[1],
    starts=[SW_INIT_FR],
    stops=[SW_STOP_FR],
    expts=fr_expts,
)

config = Config(relaxation_time=RELAX_TIME, reps=NSHOTS)
qubit = Qubit()

server_commands = {
    "operation_code": OperationCode.EXECUTE_SWEEPS,
    "cfg": config,
    "sequence": sequence,
    "qubits": [qubit],
    "sweepers": [sweeper_ro, sweeper_spec],
}

i, q = execute(server_commands, HOST, PORT)

for l in (i, q):
    l = np.array(l)
    l.reshape((amp_expts, fr_expts))

np.savetxt("i_values.txt", i)
np.savetxt("q_values.txt", q)

# l'analisi è:
# si calcola la differenza di frequenza del qubit fra ampiezza zero e ampiezza usata
# si divide deltaf per il chi trovato in precedenza
# il risultato è il mean photon number

# conoscendo n, xhi e k (del risonatore) si può anche trovare la driving
# strength del risonatore
