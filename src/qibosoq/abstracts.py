"""Various heleper objects"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Union


@dataclass
class Config:
    """General RFSoC Configuration"""

    repetition_duration: int = 100  # relaxation time in us
    adc_trig_offset: int = 200  # adc clock
    reps: int = 1000


@dataclass
class Qubit:
    """Qubit object, storing flux information"""

    bias: float = 0.0  # ampltitude factor
    dac: int = None  # dac connected to flux


@dataclass
class Pulse:
    """Abstract Pulse object"""

    frequency: float  # MHz
    amplitude: float  # ampltitude factor
    relative_phase: int  # degrees
    start: float  # us
    duration: float  # us

    name: str  # name of the pulse, typically a serial
    type: str  # 'readout', 'drive', 'flux'

    dac: int  # dac for pulse
    adc: int  # adc for readout pulse

    shape: str  # 'rectangular', 'gaussian', 'drag'
    rel_sigma: float = None
    beta: float = None


class Parameter(Enum):
    """Available parameters for sweepers"""

    frequency = auto()
    amplitude = auto()
    relative_phase = auto()
    start = auto()

    bias = auto()


@dataclass
class Sweeper:
    """Sweeper object"""

    expts: int = None  # single number of points
    parameter: List[Parameter] = None  # parameters to sweep
    starts: List[Union[int, float]] = None  # list of start values
    stops: List[Union[int, float]] = None  # list of stops values
    indexes: List[int] = None  # list of the indexes of the sweeped pulses or qubits
