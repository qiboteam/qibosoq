import numpy as np
import pytest

from qibosoq.components.base import Parameter, Sweeper
from qibosoq.components.pulses import Hann

PARAMETERS = [
    (Parameter.FREQUENCY, "frequency"),
    (Parameter.AMPLITUDE, "amplitude"),
    (Parameter.RELATIVE_PHASE, "relative_phase"),
    (Parameter.DELAY, "delay"),
    (Parameter.BIAS, "bias"),
]


@pytest.mark.parametrize("par", PARAMETERS)
def test_parameter_variants_single(par):
    var = par[1]
    assert par[0] is Parameter.variants(var)
    var = var.upper()
    assert par[0] is Parameter.variants(var)


def test_parameter_variants():
    var_list = [par[1] for par in PARAMETERS]
    var_tuple = tuple(par[1] for par in PARAMETERS)
    var_set = {par[1] for par in PARAMETERS}

    converted_list = Parameter.variants(var_list)
    assert isinstance(converted_list, list)
    converted_tuple = Parameter.variants(var_tuple)
    assert isinstance(converted_tuple, tuple)
    converted_set = Parameter.variants(var_set)
    assert isinstance(converted_set, set)

    expected = [par[0] for par in PARAMETERS]

    assert converted_list == expected
    assert list(converted_tuple) == expected
    assert sorted(converted_set) == sorted(expected)


def test_sweeper_validation():
    Sweeper(
        expts=10,
        parameters=[Parameter.FREQUENCY],
        indexes=[0],
        starts=np.array([0]),
        stops=np.array([1]),
    )

    with pytest.raises(ValueError, match="Number of experiments must be positive"):
        Sweeper(
            expts=0,
            parameters=[Parameter.FREQUENCY],
            indexes=[0],
            starts=np.array([0]),
            stops=np.array([1]),
        )

    with pytest.raises(ValueError, match="requires at least one parameter"):
        Sweeper(
            expts=10,
            parameters=[],
            indexes=[],
            starts=np.array([]),
            stops=np.array([]),
        )

    with pytest.raises(ValueError, match="same length"):
        Sweeper(
            expts=10,
            parameters=[Parameter.FREQUENCY],
            indexes=[0, 1],
            starts=np.array([0]),
            stops=np.array([1]),
        )

    with pytest.raises(ValueError, match="non-negative integers"):
        Sweeper(
            expts=10,
            parameters=[Parameter.FREQUENCY],
            indexes=[-1],
            starts=np.array([0]),
            stops=np.array([1]),
        )

    with pytest.raises(ValueError, match="Amplitude sweep cannot exceed 1"):
        Sweeper(
            expts=10,
            parameters=[Parameter.AMPLITUDE],
            indexes=[0],
            starts=np.array([1.2]),
            stops=np.array([1]),
        )


def test_hann_envelope_is_full_scale():
    """The amplitude is applied by the pulse gain, not by the envelope."""
    pulse = Hann(
        frequency=100,
        amplitude=0.5,
        relative_phase=0,
        start_delay=0,
        duration=0.1,
        name="hann",
        type="drive",
        dac=0,
        adc=None,
    )
    values = pulse.i_values(100, 32766)
    assert values.max() == pytest.approx(32766)
    assert values[0] == 0


@pytest.mark.parametrize("samples", [3, 7, 49, 112])
def test_hann_sample_count(samples):
    pulse = Hann(
        frequency=100,
        amplitude=0.5,
        relative_phase=0,
        start_delay=0,
        duration=0.1,
        name="hann",
        type="drive",
        dac=0,
        adc=None,
    )
    assert len(pulse.i_values(samples, 1)) == samples
