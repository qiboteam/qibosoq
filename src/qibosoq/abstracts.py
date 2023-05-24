from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Union


@dataclass
class Config:
    """General RFSoC Configuration to send to the server"""

    # sampling_rate: int = None
    repetition_duration: int = 100_000
    adc_trig_offset: int = 200
    # max_gain: int = 32_000
    reps: int = 1000
    # adc_sampling_frequency: int = None
    # mux_sampling_frequency: int = None


@dataclass
class Qubit:
    bias: float = 0.0
    dac: int = None


# pulses


@dataclass
class Pulse:
    frequency: float  # MHz
    amplitude: float
    relative_phase: int  # TODO check
    start: float
    duration: float

    dac: int
    adc: int

    name: str
    type: str

    shape: str
    rel_sigma: float = None
    sigma: float = None
    beta: float = None


class Parameter(Enum):
    frequency = auto()
    amplitude = auto()
    relative_phase = auto()
    start = auto()

    bias = auto()


@dataclass
class Sweeper:
    """Sweeper object"""

    expts: int = None  # single number of points
    parameter: List[Parameter] = None  # parameter to sweep
    starts: List[Union[int, float]] = None  # list of start values
    stops: List[Union[int, float]] = None  # list of stops values
    indexes: List[int] = None  # list of the indexes of the sweeped pulses or qubits
