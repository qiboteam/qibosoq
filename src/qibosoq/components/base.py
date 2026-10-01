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
    """Time to wait between shots (us). Mapped to 'final_delay' in ASMv2"""
    ro_time_of_flight: float = 200
    """Time to wait between readout pulse and acquisition (us).

    Converted to ADC/tProc clock ticks for tProc v1 in the server; used
    directly (in us) for tProc v2.
    """
    reps: int = 1000
    """Number of shots. Hardware averaging"""
    average: bool = True
    """
       ASMv1: Returns software integrated results if true.
       ASMv2: This field is ignored; averaging is done by setting reps and rounds.
    """
    rounds: int = 1
    """
    Number of times to rerun the program, averaging results in software (aka "Software averaging")
    Will auto set rounds = reps in EXECUTE_PULSE_SEQUENCE_RAW
    """

    # General RFSoC Configuration for ASMv2. refer to AveragerProgramV2 in QICK for more details
    final_wait: float = 0
    """ASMv2: Amount of time (in us) to pause tProc execution at the end of each shot, after the end of the last readout
       Default 0us.
       'None' will disable this behaviour.
    """
    initial_delay: float = 1
    """ASMv2: Amount of time (in us) to add to the timeline before starting to run the loops."""
    reps_innermost: bool = False
    """
       ASMv2: Only applicable when using sweeper (QICK's add_loop function)
       If false, reps will be outermost (sweep N times and take 1 shot at each step).
       Time-varying fluctuations will tend to be averaged out.
       E.g.
        rep1: freq1, freq2, ..., freq N
        rep2: freq1, freq2, ..., freq N
        ...
        rep M: freq1, freq2, ..., freq N
       If true, the 'reps' loop will be innermost (sweep once and take N shots at each step).
       Time-varying fluctuations will tend to appear as wiggles/jumps.
       E.g.
        freq1: M shots
        freq2: M shots
        ...
        freq N:  M shots
    """
    soft_avgs: int = 1
    """Deprecated. Kept only for backward compatibility; removed at the start of
    execute_program and no longer used (see ``rounds``)."""


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
        if self.expts <= 0:
            raise ValueError("Number of experiments must be positive.")

        if isinstance(self.starts, list):
            self.starts = np.array(self.starts, dtype=np.float64)
        if isinstance(self.stops, list):
            self.stops = np.array(self.stops, dtype=np.float64)

        if self.starts.ndim != 1 or self.stops.ndim != 1:
            raise ValueError("Sweeper starts/stops must be one-dimensional arrays.")

        n_parameters = len(self.parameters)
        if n_parameters == 0:
            raise ValueError("Sweeper requires at least one parameter.")

        if len(self.indexes) != n_parameters:
            raise ValueError("Sweeper indexes and parameters must have the same length.")
        if len(self.starts) != n_parameters or len(self.stops) != n_parameters:
            raise ValueError("Sweeper starts/stops and parameters must have the same length.")

        for idx in self.indexes:
            if not isinstance(idx, (int, np.integer)) or idx < 0:
                raise ValueError("Sweeper indexes must be non-negative integers.")

        for idx, par in enumerate(self.parameters):
            if par == Parameter.AMPLITUDE:
                if self.starts[idx] > 1 or self.stops[idx] > 1:
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
