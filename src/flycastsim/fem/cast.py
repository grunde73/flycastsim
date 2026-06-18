"""A simplified, qualitative "sample fly cast" built on the core engine.

This module assembles a single tapered beam/line subdomain (a stiff rod butt
that softens into a flexible fly line), drives its handle end with a rotating
casting stroke, and integrates the resulting motion under gravity using the
generalised-alpha solver.

It is a *qualitative* demonstration of the engine, not a quantitative cast:

* there is no air drag yet (so no realistic loop unrolling),
* the line is inextensible and modelled as a single subdomain,
* the handle is a pure rotation about a fixed pivot (no translation / haul).

The public entry point is :func:`simulate_cast`, which returns the time array
together with the reconstructed ``(x, y)`` coordinates of the whole line at
every time step -- ready to be plotted or animated.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from .coords import positions
from .domain import Subdomain
from .genalpha import integrate
from .operators import BoundaryConditions
from . import state as st


def _smoothstep(u: np.ndarray | float) -> np.ndarray | float:
    """Hermite smoothstep ``3u^2 - 2u^3`` clamped to ``[0, 1]``."""
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def casting_stroke(sweep: float, t_stroke: float,
                   start_angle: float | None = None) -> Callable[[float], float]:
    """Return a handle-angle function ``theta(t)`` for a casting stroke.

    The handle sweeps smoothly (a smoothstep in time, giving zero angular
    velocity at both ends) through a total angle ``sweep`` over a duration
    ``t_stroke``, then holds its final angle.

    Args:
        sweep: Total swept angle [rad] (positive sweeps from ``+sweep/2`` down
            to ``-sweep/2`` by default, i.e. a forward cast).
        t_stroke: Duration of the stroke [s].
        start_angle: Initial handle angle [rad]. Defaults to ``+sweep/2`` so
            the stroke is symmetric about zero.

    Returns:
        A callable ``theta(t)`` giving the handle angle measured from the
        ``+x`` axis.
    """
    if t_stroke <= 0.0:
        raise ValueError("t_stroke must be positive")
    a0 = 0.5 * sweep if start_angle is None else start_angle

    def theta(t: float) -> float:
        return float(a0 - sweep * _smoothstep(t / t_stroke))

    return theta


def fly_cast_domain(length: float = 3.0, n_nodes: int = 61, *,
                    EI_butt: float = 50.0, taper: float = 0.6,
                    EI_line: float = 0.02,
                    mass: float = 0.05) -> Subdomain:
    """Build a tapered rod-plus-line subdomain.

    The bending stiffness decays exponentially from a stiff rod butt into a
    soft fly line::

        EI(s) = EI_butt * exp(-s / taper) + EI_line.

    Args:
        length: Total length of the rod + line [m].
        n_nodes: Number of grid nodes.
        EI_butt: Bending stiffness at the handle (rod butt) [N m^2].
        taper: Exponential taper length scale [m]; smaller is a faster
            transition from rod to line.
        EI_line: Asymptotic line bending stiffness [N m^2].
        mass: Mass per unit length [kg/m] (uniform).

    Returns:
        A :class:`~flycastsim.fem.domain.Subdomain`.
    """
    s = np.linspace(0.0, length, n_nodes)
    EI = EI_butt * np.exp(-s / taper) + EI_line
    m = mass * np.ones(n_nodes)
    return Subdomain(s=s, m=m, EI=EI, d=np.zeros(n_nodes), eta=np.zeros(n_nodes))


def cast_bc(theta: Callable[[float], float], n_nodes: int
            ) -> Callable[[float], BoundaryConditions]:
    """Return a time-dependent boundary-condition function for a cast.

    The handle (node 0) is a rotating pivot: it stays fixed in space
    (``u_s = u_n = 0``) while its tangent angle follows the stroke
    ``phi(0, t) = theta(t)``.  The tip (last node) is free
    (``F_s = F_n = 0``, moment-free ``nu_z = 0``).

    Args:
        theta: Handle-angle function ``theta(t)`` (see :func:`casting_stroke`).
        n_nodes: Number of grid nodes.

    Returns:
        A callable ``bc_func(t) -> BoundaryConditions``.
    """
    last = n_nodes - 1

    def bc_func(t: float) -> BoundaryConditions:
        bc = BoundaryConditions()
        bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0)
        bc.dirichlet(0, st.PHI, theta(t))
        bc.dirichlet(last, st.F_S, 0.0).dirichlet(last, st.F_N, 0.0)
        bc.dirichlet(last, st.NU_Z, 0.0)
        return bc

    return bc_func


def simulate_cast(*, length: float = 3.0, n_nodes: int = 61,
                  EI_butt: float = 50.0, taper: float = 0.6,
                  EI_line: float = 0.02, mass: float = 0.05,
                  sweep: float = np.deg2rad(120.0), t_stroke: float = 0.4,
                  t_end: float = 0.8, dt: float = 2.0e-3,
                  gravity: float = 9.81, rho_inf: float = 0.7):
    """Simulate a simplified fly cast and return the line shape over time.

    Args:
        length: Rod + line length [m].
        n_nodes: Number of grid nodes.
        EI_butt, taper, EI_line, mass: Tapered-domain parameters
            (see :func:`fly_cast_domain`).
        sweep: Total handle sweep angle [rad].
        t_stroke: Stroke duration [s].
        t_end: Total simulated time [s].
        dt: Time step [s].
        gravity: Gravitational acceleration [m/s^2].
        rho_inf: Generalised-alpha spectral radius (numerical damping).

    Returns:
        Tuple ``(t, X, Y, s)`` where ``t`` has shape ``(n_steps + 1,)``,
        ``X`` and ``Y`` have shape ``(n_steps + 1, n_nodes)`` giving the
        physical coordinates of every node at every time step, and ``s`` is
        the arc-length grid.
    """
    dom = fly_cast_domain(length, n_nodes, EI_butt=EI_butt, taper=taper,
                          EI_line=EI_line, mass=mass)
    s = dom.s
    theta = casting_stroke(sweep, t_stroke)
    bc_func = cast_bc(theta, n_nodes)

    x0 = st.zeros(n_nodes)
    x0.phi[:] = theta(0.0)

    res = integrate(dom, bc_func, x0.to_vector(), t_span=(0.0, t_end), dt=dt,
                    gravity=gravity, rho_inf=rho_inf)

    n_t = len(res.t)
    X = np.empty((n_t, n_nodes))
    Y = np.empty((n_t, n_nodes))
    for k in range(n_t):
        X[k], Y[k] = positions(res.fields_at(k).phi, s)
    return res.t, X, Y, s
