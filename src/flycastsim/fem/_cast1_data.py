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

    .. note::
       This is the Figure-1 digitization, kept as a cross-check.  The handle
       is actually driven by :func:`phi_handle_rad`, which uses angles
       **measured directly from the footage** in the engine's tangent
       convention.
    """
    t = np.asarray(t, dtype=float)
    deg = np.interp(t, ANGLE_DEG[:, 0], ANGLE_DEG[:, 1])
    return np.deg2rad(deg)


#: Rod-butt (handle) tangent angle for the Cast #1 forward stroke, in the
#: engine's convention: angle of the unit tangent ``(cos phi, sin phi)`` of the
#: rod at the handle, with the casting/target direction as ``+x`` (0 deg = level
#: forward, +90 deg = straight up).  The stroke sweeps the rod **up** through the
#: delivery: it starts low and forward (fourth quadrant, ~ -35 deg), rotates up
#: through level, and ends pointing **up and forward** (first quadrant) as the
#: loop forms -- so the rod finishes pointing up, matching the observed Cast #1
#: motion (movie ``cast01_m1``).  The curve is an idealized lift fitted by eye to
#: the footage (RSP = frame 0317 at ~500 fps); treat as indicative.  Columns:
#: time [s] relative to RSP, handle angle [deg].
ANGLE_DEG_VIDEO = np.array([
    [-0.400, -35.0],
    [-0.300, -15.0],
    [-0.200,  12.0],
    [-0.120,  38.0],   # MAV region -- maximum angular velocity
    [-0.060,  60.0],
    [-0.020,  74.0],
    [ 0.000,  80.0],   # RSP -- rod swung up, butt decelerating to the stop
    [ 0.030,  86.0],
    [ 0.060,  89.0],
    [ 0.100,  91.0],
    [ 0.130,  92.0],   # follow-through: rod pointing up (butt stopped)
])


def phi_handle_rad(t: np.ndarray) -> np.ndarray:
    """Handle (rod-butt) tangent angle [rad] at times ``t`` [s], from the video.

    Returns the **absolute** tangent angle of the rod at the handle in the
    engine's convention (see :data:`ANGLE_DEG_VIDEO`), so it can be prescribed
    directly as the handle boundary condition ``phi(0, t)``.  Outside the
    measured window the endpoints are held constant.
    """
    t = np.asarray(t, dtype=float)
    deg = np.interp(t, ANGLE_DEG_VIDEO[:, 0], ANGLE_DEG_VIDEO[:, 1])
    return np.deg2rad(deg)

