"""The AFTM fly-line weight standard.

The AFTM (American Fishing Tackle Manufacturers Association, now AFFTA)
line-weight standard rates a fly line by the mass of its **head**, the first
30 ft (9.144 m) of line, excluding any level tip.  This module holds the
**nominal** head masses for weights 1 to 12, in grains (1 grain =
64.79891 mg), and the head and line masses derived from them.  The
standard also allows a tolerance band around each nominal value, which is not
modelled here.

The fly-line component loader uses these values to scale a line's mass
profile to a chosen weight (``mass_mode == "scaled_by_aftm"``, see
:func:`flycastsim.fem.load_component`).
"""

from __future__ import annotations

import math

import numpy as np

#: Nominal AFTM head mass [grains] of the first 30 ft of line, by line weight.
AFTM_HEAD_GRAINS = {
    1: 60, 2: 80, 3: 100, 4: 120, 5: 140, 6: 160,
    7: 185, 8: 210, 9: 240, 10: 280, 11: 330, 12: 380,
}

#: One grain in kilograms.
GRAIN_KG = 64.79891e-6

#: Length [m] the AFTM head mass refers to (the first 30 ft of line head).
AFTM_HEAD_LENGTH_M = 9.144

_WEIGHTS = np.array(sorted(AFTM_HEAD_GRAINS), dtype=float)
_GRAINS = np.array([AFTM_HEAD_GRAINS[int(w)] for w in _WEIGHTS], dtype=float)


def _check_weight(weight: float) -> float:
    """Return ``weight`` as a float, or raise if it is outside the table."""
    w = float(weight)
    lo, hi = float(_WEIGHTS[0]), float(_WEIGHTS[-1])
    if not math.isfinite(w) or not lo <= w <= hi:
        raise ValueError(f"AFTM line weight must be between {lo:g} and "
                         f"{hi:g}, got {weight!r}")
    return w


def line_head_mass_grams(weight: float) -> float:
    """Nominal AFTM head mass [g] (first 30 ft) for a line ``weight``.

    E.g. a 5-wt is ~9.07 g.  Weights between two whole weights are linearly
    interpolated.

    Args:
        weight: AFTM fly-line weight, from 1 to 12 (e.g. ``5``).

    Returns:
        Nominal head mass [g].

    Raises:
        ValueError: ``weight`` is below 1, above 12 or not finite.
    """
    g = float(np.interp(_check_weight(weight), _WEIGHTS, _GRAINS))
    return g * GRAIN_KG * 1000.0


def line_mass_per_length(weight: float) -> float:
    """Fly-line mass per unit length [kg/m] for a line ``weight``.

    The nominal head mass spread evenly over the 30 ft head
    (:data:`AFTM_HEAD_LENGTH_M`); a 5-wt is therefore ~0.99 g/m.

    Args:
        weight: AFTM fly-line weight, from 1 to 12 (e.g. ``5``).

    Returns:
        Line mass per unit length [kg/m].

    Raises:
        ValueError: ``weight`` is below 1, above 12 or not finite.
    """
    return line_head_mass_grams(weight) * 1.0e-3 / AFTM_HEAD_LENGTH_M
