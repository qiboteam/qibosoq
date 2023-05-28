"""Various helper objects"""

from dataclasses import dataclass
from enum import IntEnum, auto
from typing import List, Union


@dataclass
class Config:
    """General RFSoC Configuration"""

    repetition_duration: int = 100
    """Time to wait between shots (us)"""
    adc_trig_offset: int = 200
    """Time to wait between readout pulse and acquisition (ADC clock ticks)"""
    reps: int = 1000
    """Number of shots"""


class OperationCode(IntEnum):
    """Available operations"""

    EXECUTE_PULSE_SEQUENCE = auto()
    EXECUTE_SWEEPS = auto()


@dataclass
class Qubit:
    """Qubit object, storing flux information"""

    bias: float = 0.0
    """Amplitude factor, for sweetspot"""
    dac: int = None
    """DAC responsible for flux control"""


@dataclass
class Pulse:
    """Abstract Pulse object"""

    frequency: float
    """Freuency of the pulse (MHz)"""
    amplitude: float
    """Amplitude factor, multiplied by maximum gain of the DAC"""
    relative_phase: int
    """Relative phase (degrees)"""
    start: float
    """Start time (us)"""
    duration: float
    """Duration of the pulse (us)"""

    name: str
    """Name of the pulse, typically a serial"""
    type: str
    """Can be 'readout', 'drive', 'flux'"""

    dac: int
    """DAC responsible for firing the pulse"""
    adc: int
    """ADC to acquire pulse back, for readout pulses"""

    shape: str
    """Can be 'rectangular', 'gaussian', 'drag'"""
    rel_sigma: float = None
    """Sigma for gaussians and drags, fraction of duration"""
    beta: float = None
    """Beta for drag pulses"""


class Parameter(IntEnum):
    """Available parameters for sweepers"""

    FREQUENCY = auto()
    AMPLITUDE = auto()
    RELATIVE_PHASE = auto()
    START = auto()
    BIAS = auto()


@dataclass
class Sweeper:
    """Sweeper object"""

    expts: int = None
    """Number of points of the sweeper"""
    parameter: List[Parameter] = None
    """List of parameter to update"""
    starts: List[Union[int, float]] = None
    """Start value for each parameter to sweep"""
    stops: List[Union[int, float]] = None
    """Stop value for each parameter to sweep"""
    indexes: List[int] = None
    """Index of the parameter to sweep relative to list of pulses or list of qubits"""