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


def node_speed(t: np.ndarray, X: np.ndarray, Y: np.ndarray, index: int
               ) -> np.ndarray:
    """Speed of a single node over time.

    Differentiates the reconstructed node position with respect to time using
    central differences (:func:`numpy.gradient`, which handles a non-uniform
    ``t`` grid) and returns the velocity magnitude.

    Args:
        t: 1-D array of times, shape ``(n_steps,)``.
        X, Y: Node coordinates over time, shape ``(n_steps, n_nodes)`` (as
            returned by :func:`flycastsim.fem.simulate_cast` /
            :func:`flycastsim.fem.simulate_cast1`).
        index: Node index whose speed to compute.

    Returns:
        Speed [m/s] of the node, shape ``(n_steps,)``.
    """
    t = np.asarray(t, dtype=float)
    vx = np.gradient(np.asarray(X)[:, index], t)
    vy = np.gradient(np.asarray(Y)[:, index], t)
    return np.hypot(vx, vy)


def node_index_from_tip(s: np.ndarray, distance: float, *, start: int = 0,
                        stop: int | None = None) -> int:
    """Node index a given arc-length ``distance`` back from the tip.

    Finds the node nearest arc-length ``s[stop - 1] - distance`` within the
    half-open node range ``[start, stop)``, clamped to that range so the result
    can never fall outside the selected region (e.g. a line-distance selection
    can never pick a rod node when ``start`` is the rod-tip index).

    Args:
        s: Global arc-length grid, shape ``(n_nodes,)``.
        distance: Arc-length distance back from the tip [m] (``0`` = the tip).
        start: First node index of the region to search (inclusive).
        stop: One past the last node index of the region (exclusive); defaults
            to ``len(s)``.

    Returns:
        The global node index nearest the target arc-length.
    """
    s = np.asarray(s, dtype=float)
    if stop is None:
        stop = s.shape[0]
    seg = s[start:stop]
    target = seg[-1] - float(distance)
    return start + int(np.argmin(np.abs(seg - target)))


def rigid_lever_tip(X: np.ndarray, Y: np.ndarray, butt_angle: np.ndarray,
                    length: float) -> tuple[np.ndarray, np.ndarray]:
    """Tip position of the imaginary rigid (undeflected) rod over time.

    The rigid lever is a straight rod of ``length`` anchored at the handle
    (node 0) and pointing along the rod-butt tangent ``butt_angle`` -- the same
    reference rod drawn by :func:`flycastsim.fem_helpers.animate_fly_cast` and
    measured against by :func:`flycastsim.fem.tip_deflection`.

    Args:
        X, Y: Node coordinates over time, shape ``(n_steps, n_nodes)``.
        butt_angle: Rod-butt tangent angle [rad], shape ``(n_steps,)``.
        length: Length of the imaginary rigid rod [m].

    Returns:
        Tuple ``(xr, yr)`` of the lever-tip coordinates, each shape
        ``(n_steps,)``.
    """
    butt_angle = np.asarray(butt_angle, dtype=float)
    xr = np.asarray(X)[:, 0] + length * np.cos(butt_angle)
    yr = np.asarray(Y)[:, 0] + length * np.sin(butt_angle)
    return xr, yr


def rigid_lever_speed(t: np.ndarray, X: np.ndarray, Y: np.ndarray,
                      butt_angle: np.ndarray, length: float) -> np.ndarray:
    """Speed of the imaginary rigid-rod tip over time.

    The speed the rod tip *would* have if the rod were perfectly rigid (no
    flex): the velocity magnitude of :func:`rigid_lever_tip`.  Comparing it with
    the real :func:`node_speed` at the rod tip isolates the speed the rod's
    bend-and-unbend adds or removes.

    Args:
        t: 1-D array of times, shape ``(n_steps,)``.
        X, Y: Node coordinates over time, shape ``(n_steps, n_nodes)``.
        butt_angle: Rod-butt tangent angle [rad], shape ``(n_steps,)``.
        length: Length of the imaginary rigid rod [m].

    Returns:
        Speed [m/s] of the rigid-lever tip, shape ``(n_steps,)``.
    """
    t = np.asarray(t, dtype=float)
    xr, yr = rigid_lever_tip(X, Y, butt_angle, length)
    return np.hypot(np.gradient(xr, t), np.gradient(yr, t))
