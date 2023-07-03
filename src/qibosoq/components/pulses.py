"""Pulses objects."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


@dataclass
class Pulse:
    """Abstract Pulse object."""

    frequency: float
    """Frequency of the pulse (MHz)."""
    amplitude: float
    """Amplitude factor, multiplied by maximum gain of the DAC."""
    relative_phase: int
    """Relative phase (degrees)."""
    start_delay: float = field(compare=False)
    """Delay before pulse is triggered (us)."""
    duration: float
    """Duration of the pulse (us)."""

    name: str
    """Name of the pulse, typically a serial."""
    type: str
    """Can be 'readout', 'drive', 'flux'."""

    dac: int
    """DAC responsible for firing the pulse."""
    adc: int
    """ADC to acquire pulse back, for readout pulses."""


@dataclass
class Rectangular(Pulse):
    """Rectangular pulse."""

    shape: str = "rectangular"


@dataclass
class Gaussian(Pulse):
    """Gaussian pulse."""

    shape: str = "gaussian"

    rel_sigma: float = None
    """Sigma of the gaussian as a fraction of duration."""


@dataclass
class Drag(Pulse):
    """Drag pulse."""

    shape: str = "drag"

    rel_sigma: float = None
    """Sigma of the drag as a fraction of duration."""
    beta: float = None
    """Beta parameter for drag pulse."""


@dataclass
class Arbitrary(Pulse):
    """Custom pulse."""

    shape: str = "arbitrary"

    i_values: List[float] = field(default_factory=List)
    q_values: List[float] = field(default_factory=List)


class Shape(Enum):
    """Map shape names to the corresponding objects."""

    rectangular = Rectangular
    gaussian = Gaussian
    drag = Drag
    arbitrary = Arbitrary
