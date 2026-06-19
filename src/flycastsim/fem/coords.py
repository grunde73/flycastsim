"""Physical-coordinate reconstruction from the solution fields.

The engine solves for the tangent angle ``phi(s)`` (and velocities), not for
positions directly.  The physical coordinates of the rod/line are recovered
at each time step by integrating the unit tangent ``(cos phi, sin phi)``
along the arc length ``s`` (see the *Coordinates* section of the willmanco.se
*Theory* page)::

    x(s) = x0 + integral_0^s cos(phi) ds'
    y(s) = y0 + integral_0^s sin(phi) ds'
"""

from __future__ import annotations

import numpy as np

from .state import Fields


def _cumtrapz(f: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Cumulative trapezoidal integral with a leading zero (length == len f)."""
    inc = 0.5 * (f[1:] + f[:-1]) * np.diff(x)
    return np.concatenate(([0.0], np.cumsum(inc)))


def positions(phi: np.ndarray, s: np.ndarray, *, x0: float = 0.0,
              y0: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct ``(x, y)`` from the tangent angle ``phi`` along ``s``."""
    x = x0 + _cumtrapz(np.cos(phi), s)
    y = y0 + _cumtrapz(np.sin(phi), s)
    return x, y


def positions_from_fields(fields: Fields, s: np.ndarray, *, x0: float = 0.0,
                          y0: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct ``(x, y)`` from a :class:`~flycastsim.fem.state.Fields`."""
    return positions(fields.phi, s, x0=x0, y0=y0)


def positions_multi(fields: Fields, md, *, x0: float = 0.0, y0: float = 0.0
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct world ``(x, y)`` for a whole :class:`MultiDomain`.

    The global arc-length grid (``md.s``) repeats the junction coordinate, so the
    cumulative tangent integral advances by zero across a junction -- the
    position stays continuous even where a pinned hinge lets the tangent angle
    ``phi`` jump.  This reproduces position continuity at welded *and* pinned
    junctions from the single global ``phi`` field.

    Args:
        fields: Global :class:`~flycastsim.fem.state.Fields` (all subdomains).
        md: The :class:`~flycastsim.fem.multidomain.MultiDomain`.
        x0, y0: World position of the first (handle) node [m].

    Returns:
        ``(x, y)`` arrays of length ``md.n_nodes``.
    """
    return positions(fields.phi, md.s, x0=x0, y0=y0)


def tension(fields: Fields) -> np.ndarray:
    """Return the tangential (tension) force ``F_s`` along the line."""
    return fields.F_s
