"""Digitized reference data for **Cast #1** of *The Rod & The Cast*.

Source
------
Grunde Løvoll and Jason Borger, *The Rod & The Cast*, first published 2006
(*FlyFisher*, Japan); web version at
``https://www.sexyloops.com/articles/rodcast.shtml`` (local copy under
``data/sexyloops.com/``).  The corresponding high-speed footage is the uploaded
``data/videos/cast01_m1_themovie_adjust_time_fs.mpg`` (caster: Mathias
Lilleheim; rod: Sage TCR, 9 ft 5-wt; ~10 m of fly line plus a 9 ft leader out
of the tip; recorded indoors at 500 fps).

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
    "rod": "Sage TCR, 9 ft, 5-wt",
    "rod_length_m": 2.74,        # 9 ft
    "line_out_m": 10.0,          # fly line out of the tip (approx.)
    "leader_length_m": 2.74,     # 9 ft tapered leader
    "capture_fps": 500,
    "video": "data/videos/cast01_m1_themovie_adjust_time_fs.mpg",
}

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
    """
    t = np.asarray(t, dtype=float)
    deg = np.interp(t, ANGLE_DEG[:, 0], ANGLE_DEG[:, 1])
    return np.deg2rad(deg)
