"""Pulses objects."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List

import numpy as np


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

    rel_sigma: float
    """Sigma of the gaussian as a fraction of duration."""
    shape: str = "gaussian"


@dataclass
class Drag(Pulse):
    """Drag pulse."""

    rel_sigma: float
    """Sigma of the drag as a fraction of duration."""
    beta: float
    """Beta parameter for drag pulse."""
    shape: str = "drag"


@dataclass
class FluxExponential(Pulse):
    """Flux pulse with exponential rising edge to correct distortions."""

    tau: float
    upsilon: float
    weight: float
    shape: str = "fluxexponential"

    def get_i_values(self, duration: int, max_gain: int):
        """Compute the waveform i values."""
        amp = int(self.amplitude * max_gain)
        time = np.arange(0, duration, 1)
        i_vals = (np.ones(duration) * np.exp(-time / self.upsilon)) + self.weight * np.exp(-time / self.tau)
        return amp * i_vals / (1 + self.weight)


@dataclass
class Arbitrary(Pulse):
    """Custom pulse."""

    i_values: List[float]
    q_values: List[float]
    shape: str = "arbitrary"


class Shape(Enum):
    """Map shape names to the corresponding objects."""

    RECTANGULAR = Rectangular
    GAUSSIAN = Gaussian
    DRAG = Drag
    ARBITRARY = Arbitrary
