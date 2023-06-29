import pytest

from qibosoq.components.base import Parameter

PARAMETERS = [
    (Parameter.FREQUENCY, "frequency"),
    (Parameter.AMPLITUDE, "amplitude"),
    (Parameter.RELATIVE_PHASE, "relative_phase"),
    (Parameter.START, "start"),
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
