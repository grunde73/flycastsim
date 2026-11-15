"""The AFTM fly-line weight standard (``aftm-line-standard`` spec)."""
import numpy as np
import pytest

from flycastsim.fem import (
    AFTM_HEAD_GRAINS,
    AFTM_HEAD_LENGTH_M,
    GRAIN_KG,
    bundled_rig_path,
    line_head_mass_grams,
    line_mass_per_length,
    load_component,
)

#: Head masses [g] computed by the private ``_cast1_data`` functions before
#: the table became public; values in range must not change.
HEAD_MASS_BEFORE = {
    1: 3.8879346, 2: 5.183912799999999, 3: 6.479890999999999,
    4: 7.7758692, 5: 9.0718474, 6: 10.367825599999998,
    7: 11.987798349999998, 8: 13.607771099999999, 9: 15.5517384,
    10: 18.1436948, 11: 21.3836403, 12: 24.623585799999997,
    4.5: 8.4238583,
}


def test_aftm_table_values():
    """The table holds the twelve nominal weights of the standard."""
    assert AFTM_HEAD_GRAINS == {
        1: 60, 2: 80, 3: 100, 4: 120, 5: 140, 6: 160,
        7: 185, 8: 210, 9: 240, 10: 280, 11: 330, 12: 380}
    assert AFTM_HEAD_LENGTH_M == 9.144
    assert GRAIN_KG == 64.79891e-6


def test_head_mass_whole_weights():
    """Whole weights give the table value in grams, unchanged from before."""
    assert np.isclose(line_head_mass_grams(5), 9.07, atol=0.05)
    assert np.isclose(line_head_mass_grams(8), 13.61, atol=0.05)
    for weight, grams in HEAD_MASS_BEFORE.items():
        assert abs(line_head_mass_grams(weight) - grams) < 1e-12, weight


def test_head_mass_interpolates():
    """A weight between two whole weights is linearly interpolated."""
    mid = 0.5 * (line_head_mass_grams(4) + line_head_mass_grams(5))
    assert np.isclose(line_head_mass_grams(4.5), mid)


def test_line_mass_per_length():
    """The head mass spread over 30 ft; heavier lines weigh more."""
    assert np.isclose(line_mass_per_length(5) * 1000, 0.99, atol=0.01)
    assert np.isclose(line_mass_per_length(5),
                      line_head_mass_grams(5) * 1e-3 / 9.144)
    masses = [line_mass_per_length(w) for w in (3, 4, 5, 6, 7, 8)]
    assert np.all(np.diff(masses) > 0)


@pytest.mark.parametrize("weight", [0, 0.99, 12.01, 13, float("nan"),
                                    float("inf")])
def test_out_of_range_weight_rejected(weight):
    """Weights outside 1 to 12, or not finite, raise a ValueError."""
    with pytest.raises(ValueError, match="between 1 and 12"):
        line_head_mass_grams(weight)
    with pytest.raises(ValueError, match="between 1 and 12"):
        line_mass_per_length(weight)


def test_component_rejects_out_of_range_weight():
    """Scaling the bundled fly line to a 13-wt raises a ValueError."""
    line_json = bundled_rig_path("cast1").parent / "line.json"
    load_component(line_json, aftm_weight=12)
    with pytest.raises(ValueError, match="between 1 and 12"):
        load_component(line_json, aftm_weight=13)
