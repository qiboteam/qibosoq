"""Various helper objects."""

from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import Iterable, List, Optional, overload

import numpy as np
import numpy.typing as npt


@dataclass
class Config:
    """General RFSoC Configuration."""

    relaxation_time: float = 100
    """Time to wait between shots (us)."""
    ro_time_of_flight: int = 200
    """Time to wait between readout pulse and acquisition (ADC clock ticks)."""
    reps: int = 1000
    """Number of shots."""
    soft_avgs: int = 1
    """Number of software averages."""
    average: bool = True
    """Returns integrated results if true."""


class OperationCode(IntEnum):
    """Available operations."""

    EXECUTE_PULSE_SEQUENCE = auto()
    EXECUTE_PULSE_SEQUENCE_RAW = auto()
    EXECUTE_SWEEPS = auto()


@dataclass
class Qubit:
    """Qubit object, storing flux information."""

    bias: Optional[float] = None
    """Amplitude factor, for sweetspot."""
    dac: Optional[int] = None
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
    def variants(cls, parameters: str) -> "Parameter":  # type: ignore
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

    expts: int
    """Number of points of the sweeper."""
    parameters: List[Parameter]
    """List of parameter to update."""
    indexes: List[int]
    """Index of the parameter to sweep relative to list of pulses or list of qubits."""
    starts: npt.NDArray[np.float64]
    """Start value for each parameter to sweep."""
    stops: npt.NDArray[np.float64]
    """Stop value for each parameter to sweep."""

    def __post_init__(self):
        """Convert starts and stops in np.arrays if needed."""
        if isinstance(self.starts, list):
            self.starts = np.array(self.starts, dtype=np.float64)
        if isinstance(self.stops, list):
            self.stops = np.array(self.stops, dtype=np.float64)

        for idx, par in enumerate(self.parameters):
            if par == Parameter.AMPLITUDE:
                if self.stops[idx] > 1:
                    raise ValueError("Amplitude sweep cannot exceed 1.")

    @property
    def serialized(self) -> dict:
        """Convert a Sweeper object into a dictionary.

        In particular, takes care of the convertion arrays -> lists.
        """
        return {
            "expts": self.expts,
            "parameters": self.parameters,
            "indexes": self.indexes,
            "starts": self.starts.tolist(),
            "stops": self.stops.tolist(),
        }
