"""Various helper objects."""

from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import Iterable, List, Union, overload


@dataclass
class Config:
    """General RFSoC Configuration."""

    repetition_duration: int = 100
    """Time to wait between shots (us)."""
    adc_trig_offset: int = 200
    """Time to wait between readout pulse and acquisition (ADC clock ticks)."""
    reps: int = 1000
    """Number of shots."""
    soft_avgs: int = 1
    """Number of software averages."""


class OperationCode(IntEnum):
    """Available operations."""

    EXECUTE_PULSE_SEQUENCE = auto()
    EXECUTE_PULSE_SEQUENCE_RAW = auto()
    EXECUTE_SWEEPS = auto()


@dataclass
class Qubit:
    """Qubit object, storing flux information."""

    bias: float = 0.0
    """Amplitude factor, for sweetspot."""
    dac: int = None
    """DAC responsible for flux control."""


class Parameter(str, Enum):
    """Available parameters for sweepers."""

    FREQUENCY = "freq"
    AMPLITUDE = "gain"
    RELATIVE_PHASE = "phase"
    DELAY = "t"
    BIAS = "bias"
    DURATION = "duration"

    @overload
    @classmethod
    def variants(cls, parameters: str) -> "Parameter":
        """Convert a string to a Parameter."""

    @overload
    @classmethod
    def variants(cls, parameters: Iterable[str]) -> Iterable["Parameter"]:
        """Convert a iterable of str to an iterable of Parameters."""

    @classmethod
    def variants(cls, parameters):
        """Convert from strings to Parameters."""
        if isinstance(parameters, str):
            return cls[parameters.upper()]
        return type(parameters)(cls[par.upper()] for par in parameters)


@dataclass
class Sweeper:
    """Sweeper object."""

    expts: int = None
    """Number of points of the sweeper."""
    parameters: List[Parameter] = None
    """List of parameter to update."""
    starts: List[Union[int, float]] = None
    """Start value for each parameter to sweep."""
    stops: List[Union[int, float]] = None
    """Stop value for each parameter to sweep."""
    indexes: List[int] = None
    """Index of the parameter to sweep relative to list of pulses or list of qubits."""
