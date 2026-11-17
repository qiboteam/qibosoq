"""Pulses objects."""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import numpy as np


def samples_digest(*samples) -> str:
    """Return a short digest identifying waveform samples."""
    data = np.array(samples, dtype=float)
    return hashlib.sha1(data.tobytes()).hexdigest()[:16]


@dataclass
class Element:
    """Abstract common oject for pulses and measurements."""

    type: str
    """Type of the pulse."""

    frequency: float
    """Frequency of the pulse (MHz)."""
    start_delay: float = field(compare=False)
    """Delay before pulse is triggered (us)."""
    duration: float
    """Duration of the pulse (us)."""

    adc: int
    """ADC to acquire pulse back, for readout pulses."""
    dac: int
    """DAC responsible for firing the pulse."""

    @property
    def waveform_name(self) -> Optional[str]:
        """Return waveform name from parameters."""
        return None

    @property
    def style(self) -> Optional[str]:
        """Return waveform style from parameters."""
        return "arb"


@dataclass
class Measurement(Element):
    """Measurement without pulse."""

    type = "readout"


@dataclass
class Pulse(Element):
    """Abstract Pulse object."""

    amplitude: float
    """Amplitude factor, multiplied by maximum gain of the DAC."""
    relative_phase: int
    """Relative phase (degrees)."""

    name: str
    """Name of the pulse, typically a serial."""
    type: str
    """Can be 'readout', 'drive', 'flux'."""


@dataclass
class Rectangular(Pulse):
    """Rectangular pulse."""

    shape: str = "rectangular"

    @property
    def style(self) -> Optional[str]:
        """Return waveform style from parameters."""
        return "const"


@dataclass
class Gaussian(Pulse):
    """Gaussian pulse."""

    rel_sigma: float
    """Sigma of the gaussian as a fraction of duration."""
    shape: str = "gaussian"

    @property
    def waveform_name(self) -> Optional[str]:
        """Return waveform name from parameters."""
        return f"{self.dac}_gaus_{self.rel_sigma}_{self.duration}"


@dataclass
class Drag(Pulse):
    """Drag pulse."""

    rel_sigma: float
    """Sigma of the drag as a fraction of duration."""
    beta: float
    """Beta parameter for drag pulse.

    It is passed to qick's ``add_DRAG`` as ``alpha``. With the same value,
    the Q component is about 1/pi of the one in qibolab's DRAG envelope, so
    beta must be calibrated on qibosoq rather than copied from qibolab.
    """
    shape: str = "drag"

    @property
    def waveform_name(self) -> Optional[str]:
        """Return waveform name from parameters."""
        return f"{self.dac}_drag_{self.rel_sigma}_{self.duration}_{self.beta}"


@dataclass
class FlatTop(Pulse):
    """FlatTop pulse."""

    rel_sigma: float
    """Sigma of the FlatTop as a fraction of duration."""
    shape: str = "flattop"

    @property
    def waveform_name(self) -> Optional[str]:
        """Return waveform name from parameters."""
        return f"{self.dac}_flattop_{self.rel_sigma}_{self.duration}"

    @property
    def style(self) -> Optional[str]:
        """Return waveform style from parameters."""
        return "flat_top"


@dataclass
class FluxExponential(Pulse):
    """Flux pulse with exponential rising edge to correct distortions."""

    tau: float
    upsilon: float
    weight: float
    shape: str = "fluxexponential"

    def i_values(self, duration: int, max_gain: int):
        """Compute the waveform i values."""
        amp = int(self.amplitude * max_gain)
        time = np.arange(duration)
        i_vals = (
            np.ones(duration) * np.exp(-time / self.upsilon)
        ) + self.weight * np.exp(-time / self.tau)
        return amp * i_vals / (1 + self.weight)


@dataclass
class Hann(Pulse):
    """Hann function."""

    shape: str = "hann"

    @property
    def waveform_name(self) -> Optional[str]:
        """Return waveform name from parameters."""
        return f"{self.dac}_hann_{self.duration}"

    def i_values(self, duration: int, max_gain: int):
        """Compute the full-scale waveform i values.

        The amplitude is applied by the pulse gain, as for the other drive shapes.
        """
        i_vals = np.sin(np.pi * np.arange(duration) / duration) ** 2
        return max_gain * i_vals


@dataclass
class Arbitrary(Pulse):
    """Custom pulse."""

    i_values: List[float]
    q_values: List[float]
    shape: str = "arbitrary"

    @property
    def waveform_name(self) -> Optional[str]:
        """Return waveform name from parameters.

        The samples are part of the name, since qibolab can reuse a pulse id
        with a different envelope.
        """
        digest = samples_digest(self.i_values, self.q_values)
        return f"{self.dac}_arb_{self.duration}_{digest}"


class Shape(Enum):
    """Map shape names to the corresponding objects."""

    RECTANGULAR = Rectangular
    GAUSSIAN = Gaussian
    DRAG = Drag
    HANN = Hann
    FLUXEXPONENTIAL = FluxExponential
    FLATTOP = FlatTop
    ARBITRARY = Arbitrary
