"""Pulses objects."""

from dataclasses import dataclass, field


@dataclass
class Pulse:
    """Abstract Pulse object."""

    frequency: float
    """Freuency of the pulse (MHz)."""
    amplitude: float
    """Amplitude factor, multiplied by maximum gain of the DAC."""
    relative_phase: int
    """Relative phase (degrees)."""
    start: float = field(compare=False)
    """Start time (us)."""
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

    shape: str = "gaussian"

    rel_sigma: float = None
    """Sigma of the drag as a fraction of duration."""
    beta: float = None
    """Beta parameter for drag pulse."""


def pulse_class_from_shape(shape: str):
    """Return the class corresponding to a shape."""
    if shape == "rectangular":
        return Rectangular
    elif shape == "gaussian":
        return Gaussian
    elif shape == "drag":
        return Drag
