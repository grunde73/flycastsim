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


def tension(fields: Fields) -> np.ndarray:
    """Return the tangential (tension) force ``F_s`` along the line."""
    return fields.F_s
