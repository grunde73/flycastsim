"""Digitized reference data for **Cast #1** of *The Rod & The Cast*.

Source
------
Grunde Løvoll and Jason Borger, *The Rod & The Cast*, first published 2006
(*FlyFisher*, Japan); web version at
``https://www.sexyloops.com/articles/rodcast.shtml`` (local copy under
``data/sexyloops.com/``).  The corresponding high-speed footage is the uploaded
``data/videos/cast01_m1_themovie_adjust_time_fs.mpg`` (caster: Mathias
Lilleheim; rod: T&T Paradigm, 9 ft 5-wt; ~10 m of fly line plus a 9 ft leader out
of the tip; recorded indoors at 500 fps).  The labelled event frames shipped
under ``assets/cast1/`` are taken from a 400-frame PNG dump of that clip
(``data/cast1_frames/``) with **RSP = frame 0317** (clock ~0.63 s) set to
``t = 0``.

All time values are relative to **RSP** (Rod Straight Position), the reference
event the paper sets to ``t = 0``.

The event table (:data:`EVENTS`) and the tip speeds are read directly from
Table 1 of the article (image ``data/sexyloops.com/images/rodcast4.gif``) and
the labelled frames (``rodcast6.jpg``) -- these are exact published values.

The continuous curves (:data:`ANGLE_DEG`, :data:`CHORD_M`) are **approximate
manual digitizations** of Figure 1 / Figure 2 (``rodcast2.gif`` /
``rodcast3.gif``); treat them as indicative shapes, not precise measurements.
"""

from __future__ import annotations

import numpy as np

#: Rig / capture metadata for Cast #1.
RIG = {
    "caster": "Mathias Lilleheim",
    "rod": "T&T Paradigm, 9 ft, 5-wt",
    "rod_length_m": 2.74,        # 9 ft
    "line_out_m": 10.0,          # fly line out of the tip (approx.)
    "leader_length_m": 2.74,     # 9 ft tapered leader
    "line_weight": 5,            # AFTM line weight (5-wt)
    "capture_fps": 500,
    "video": "data/videos/cast01_m1_themovie_adjust_time_fs.mpg",
}

#: AFTM / AFFTA fly-line weight standard: nominal mass [grains] of the first
#: 30 ft (9.144 m) of the line head, indexed by line weight number.  (1 grain =
#: 64.79891 mg.)
AFTM_HEAD_GRAINS = {
    1: 60, 2: 80, 3: 100, 4: 120, 5: 140, 6: 160,
    7: 185, 8: 210, 9: 240, 10: 280, 11: 330, 12: 380,
}

GRAIN_KG = 64.79891e-6               # 1 grain in kilograms

#: Length [m] the AFTM standard mass refers to (the first 30 ft of line head).
AFTM_HEAD_LENGTH_M = 9.144           # 30 ft


def line_head_mass_grams(weight: float) -> float:
    """Standard AFTM head mass [g] (first 30 ft) for an AFTM ``weight``.

    Uses the AFTM grain standard (:data:`AFTM_HEAD_GRAINS`); e.g. a 5-wt is
    ~9.07 g.  Non-integer weights are linearly interpolated.

    Args:
        weight: AFTM fly-line weight number (e.g. ``5``).

    Returns:
        Standard head mass [g].
    """
    weights = np.array(sorted(AFTM_HEAD_GRAINS), dtype=float)
    grains = np.array([AFTM_HEAD_GRAINS[int(w)] for w in weights], dtype=float)
    g = float(np.interp(float(weight), weights, grains))
    return g * GRAIN_KG * 1000.0


def line_mass_per_length(weight: float) -> float:
    """Fly-line mass per unit length [kg/m] for an AFTM ``weight``.

    Derived directly from the AFTM standard: the rated head mass spread over the
    first 30 ft (:data:`AFTM_HEAD_LENGTH_M`).  A 5-wt is therefore ~0.99 g/m.
    This is the *physical* line density (a heavier line loads the rod more); the
    model applies the same density along the whole modelled line + leader.

    Args:
        weight: AFTM fly-line weight number (e.g. ``5``).

    Returns:
        Line mass per unit length [kg/m].
    """
    return line_head_mass_grams(weight) * 1.0e-3 / AFTM_HEAD_LENGTH_M

#: Labelled cast events (exact, from Table 1 / frames). ``t`` is seconds
#: relative to RSP; ``vt`` is the measured rod-tip speed [m/s].
EVENTS = {
    "MAV":   {"t": -0.148, "vt": 15, "label": "Max angular velocity"},
    "MCL":   {"t": -0.093, "vt": 18, "label": "Min chord length"},
    "MAV/2": {"t": -0.081, "vt": 19, "label": "Half max angular velocity"},
    "RSP":   {"t":  0.000, "vt": 24, "label": "Rod straight position"},
    "MCF":   {"t":  0.058, "vt":  5, "label": "Max counter-flex"},
}

#: Tip speed at RSP [m/s] (Table 1).
V_RSP = 24.0

#: Approximate digitization of the rod-butt angle (Figure 1, circles).
#: Columns: time [s] relative to RSP, rod-butt angle [deg].
ANGLE_DEG = np.array([
    [-0.40,  38.0],
    [-0.35,  52.0],
    [-0.30,  63.0],
    [-0.25,  75.0],
    [-0.20,  86.0],
    [-0.15,  97.0],
    [-0.10, 108.0],
    [-0.05, 118.0],
    [ 0.00, 124.0],
    [ 0.05, 128.0],
    [ 0.10, 132.0],
    [ 0.13, 135.0],
])

#: Approximate digitization of the measured chord length (tip-to-handle
#: distance, Figure 1 / Figure 2).  Columns: time [s] relative to RSP,
#: chord length [m].
CHORD_M = np.array([
    [-0.28, 2.43],
    [-0.20, 2.40],
    [-0.15, 2.36],
    [-0.10, 2.30],
    [-0.093, 2.27],   # MCL (minimum)
    [-0.05, 2.38],
    [-0.01, 2.57],    # peak near RSP
    [ 0.00, 2.56],    # RSP
    [ 0.03, 2.49],
    [ 0.058, 2.43],   # MCF (local minimum)
    [ 0.10, 2.47],
    [ 0.15, 2.52],
])


def angle_rad_interp(t: np.ndarray) -> np.ndarray:
    """Interpolate the digitized rod-butt angle (radians) at times ``t`` [s].

    Outside the digitized window the endpoints are held constant.

    .. note::
       This is the Figure-1 digitization, kept as a cross-check.  The handle
       is actually driven by the bundled Cast #1 stroke
       (``load_stroke("cast1")``), whose angles were fitted to the footage
       in the engine's tangent convention.
    """
    t = np.asarray(t, dtype=float)
    deg = np.interp(t, ANGLE_DEG[:, 0], ANGLE_DEG[:, 1])
    return np.deg2rad(deg)


# The Cast #1 stroke drive (rod-butt angle and hand path) is bundled as data:
# ``load_stroke("cast1")`` reads ``flycastsim/data/strokes/cast1/``, whose
# metadata records the original digitised angle points and hand-path values.
