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
from .drag import reynolds_drag
from .genalpha import integrate
from .operators import BoundaryConditions
from . import state as st
from . import _cast1_data


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
                    mass: float = 0.05,
                    line_diameter: float = 1.2e-3,
                    eta: float = 0.0) -> Subdomain:
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
        line_diameter: Outer diameter [m] used for air drag (uniform). Has no
            effect unless a drag law is supplied to the integrator.
        eta: Material relaxation time [s] (Kelvin-Voigt damping). ``0`` (the
            default) is purely elastic.

    Returns:
        A :class:`~flycastsim.fem.domain.Subdomain`.
    """
    s = np.linspace(0.0, length, n_nodes)
    EI = EI_butt * np.exp(-s / taper) + EI_line
    m = mass * np.ones(n_nodes)
    d = line_diameter * np.ones(n_nodes)
    return Subdomain(s=s, m=m, EI=EI, d=d, eta=eta * np.ones(n_nodes))


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
                  gravity: float = 9.81, rho_inf: float = 0.7,
                  air_drag: bool = False, eta: float = 0.0,
                  line_diameter: float = 1.2e-3):
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
        air_drag: If ``True``, apply the Reynolds-number air-drag law
            (:func:`flycastsim.fem.drag.reynolds_drag`).
        eta: Material relaxation time [s] for Kelvin-Voigt damping (``0`` is
            purely elastic).
        line_diameter: Outer diameter [m] used by the air-drag law.

    Returns:
        Tuple ``(t, X, Y, s)`` where ``t`` has shape ``(n_steps + 1,)``,
        ``X`` and ``Y`` have shape ``(n_steps + 1, n_nodes)`` giving the
        physical coordinates of every node at every time step, and ``s`` is
        the arc-length grid.
    """
    dom = fly_cast_domain(length, n_nodes, EI_butt=EI_butt, taper=taper,
                          EI_line=EI_line, mass=mass,
                          line_diameter=line_diameter, eta=eta)
    s = dom.s
    theta = casting_stroke(sweep, t_stroke)
    bc_func = cast_bc(theta, n_nodes)

    x0 = st.zeros(n_nodes)
    x0.phi[:] = theta(0.0)

    f_drag = reynolds_drag(dom) if air_drag else None
    res = integrate(dom, bc_func, x0.to_vector(), t_span=(0.0, t_end), dt=dt,
                    gravity=gravity, rho_inf=rho_inf, f_drag=f_drag)

    n_t = len(res.t)
    X = np.empty((n_t, n_nodes))
    Y = np.empty((n_t, n_nodes))
    for k in range(n_t):
        X[k], Y[k] = positions(res.fields_at(k).phi, s)
    return res.t, X, Y, s


# ---------------------------------------------------------------------------
# Cast #1 of "The Rod & The Cast" (Loevoll & Borger)
#
# This block configures the engine to *reproduce* the documented Cast #1 (the
# uploaded ``cast01_m1`` high-speed footage): a 9 ft 5-wt rod (T&T Paradigm)
# driven by the rod-butt motion measured from the footage (the forward stroke
# sweeps the rod from up-and-back to up-and-forward, ending rod-up).  See
# :mod:`flycastsim.fem._cast1_data` for the reference data and its provenance.
#
# Honest caveats (also surfaced in the docs / dashboard):
#   * Only a short line stub is modelled (single subdomain), so the *line*
#     cannot unroll into a fully realistic loop; the comparison is restricted
#     to the **rod** kinematics (the chord length / stop sequence).
#   * The measured rod-butt angle and chord curve are approximate readings of
#     the footage / low-resolution magazine figures.
#   * The handle is a pure rotation about a fixed pivot (no translation / haul).
# ---------------------------------------------------------------------------

#: Reference rod length for Cast #1 (9 ft) [m].
CAST1_ROD_LENGTH = _cast1_data.RIG["rod_length_m"]


def cast1_domain(rod_length: float = CAST1_ROD_LENGTH, line_out: float = 2.5,
                 n_nodes: int = 61, *, EI_butt: float = 180.0,
                 EI_rod_tip: float = 18.0, taper: float = 1.1,
                 EI_line: float = 0.05, mass_rod: float = 0.045,
                 mass_line: float = 0.010,
                 rod_diameter: float = 6.0e-3, line_diameter: float = 1.2e-3,
                 eta_rod: float = 0.0, eta_line: float = 0.0) -> Subdomain:
    """Build a rod-plus-short-line subdomain tuned to a 9 ft 5-wt rod (T&T
    Paradigm).

    The bending stiffness decays exponentially along the **rod** region
    (``s <= rod_length``) from a stiff butt to a softer tip, then drops to a
    small constant value along the modelled **line** stub::

        EI(s) = EI_butt * exp(-s / taper) + EI_rod_tip   for s <= rod_length
        EI(s) = EI_line                                  for s >  rod_length

    Mass per unit length is ``mass_rod`` on the rod and ``mass_line`` on the
    line stub.

    Args:
        rod_length: Length of the rod region [m] (default 9 ft).
        line_out: Length of the modelled line stub beyond the tip [m].
        n_nodes: Number of grid nodes over the whole domain.
        EI_butt, EI_rod_tip, taper: Rod stiffness profile [N m^2, N m^2, m].
        EI_line: Line-stub bending stiffness [N m^2].
        mass_rod, mass_line: Mass per length of the rod / line [kg/m].
        rod_diameter, line_diameter: Outer diameter [m] of the rod / line
            regions, used for air drag. No effect without a drag law.
        eta_rod, eta_line: Material relaxation time [s] (Kelvin-Voigt damping)
            on the rod / line regions. ``0`` (default) is purely elastic.

    Returns:
        A :class:`~flycastsim.fem.domain.Subdomain`.
    """
    s = np.linspace(0.0, rod_length + line_out, n_nodes)
    rod = s <= rod_length
    EI = np.where(rod,
                  EI_butt * np.exp(-s / taper) + EI_rod_tip, EI_line)
    m = np.where(rod, mass_rod, mass_line)
    d = np.where(rod, rod_diameter, line_diameter)
    eta = np.where(rod, eta_rod, eta_line)
    return Subdomain(s=s, m=m, EI=EI, d=d, eta=eta)


def cast1_stroke(t_start: float = -0.40) -> Callable[[float], float]:
    """Return the handle-angle function ``theta(t)`` for Cast #1.

    The handle tangent angle follows the idealized rod-butt sweep fitted to the
    footage (:func:`flycastsim.fem._cast1_data.phi_handle_rad`), in the engine's
    convention (target direction ``+x``, ``+90 deg`` = straight up).  The stroke
    sweeps the rod **up**: it starts low and forward (fourth quadrant), rotates
    up through level, and ends **pointing up and forward** (first quadrant) as
    the loop forms -- matching the observed Cast #1 rod motion.

    Args:
        t_start: Start time of the simulation window [s], relative to RSP
            (unused for the absolute drive; kept for signature compatibility).

    Returns:
        A callable ``theta(t)`` with ``t`` in seconds relative to RSP.
    """
    def theta(t: float) -> float:
        return float(_cast1_data.phi_handle_rad(t))

    return theta


def chord_length(X: np.ndarray, Y: np.ndarray, rod_tip_index: int
                 ) -> np.ndarray:
    """Rod chord length (handle-to-rod-tip distance) over time.

    Args:
        X, Y: Position arrays of shape ``(n_steps, n_nodes)``.
        rod_tip_index: Node index of the rod tip (end of the rod region).

    Returns:
        Array of shape ``(n_steps,)`` with the straight-line distance from the
        handle (node 0) to the rod tip at every time step.
    """
    return np.hypot(X[:, rod_tip_index] - X[:, 0],
                    Y[:, rod_tip_index] - Y[:, 0])


def simulate_cast1(*, rod_length: float = CAST1_ROD_LENGTH,
                   line_out: float = 2.5, n_nodes: int = 61,
                   EI_butt: float = 180.0, EI_rod_tip: float = 18.0,
                   taper: float = 1.1, EI_line: float = 0.05,
                   mass_rod: float = 0.045, mass_line: float = 0.010,
                   t_span: tuple[float, float] = (-0.40, 0.13),
                   dt: float = 2.0e-3, gravity: float = 9.81,
                   rho_inf: float = 0.6,
                   air_drag: bool = False, eta_rod: float = 0.0,
                   eta_line: float = 0.0,
                   rod_diameter: float = 6.0e-3,
                   line_diameter: float = 1.2e-3):
    """Simulate Cast #1 driven by the fitted rod-butt motion.

    The handle (node 0) is a rotating pivot whose angle follows
    :func:`cast1_stroke`; the tip is free.  Time is measured **relative to
    RSP** (Rod Straight Position), matching the article, so ``t = 0`` is RSP.

    Args:
        rod_length, line_out, n_nodes, EI_butt, EI_rod_tip, taper, EI_line,
        mass_rod, mass_line: Domain parameters (see :func:`cast1_domain`).
        t_span: ``(t0, t1)`` simulation window [s] relative to RSP.
        dt: Time step [s].
        gravity: Gravitational acceleration [m/s^2].
        rho_inf: Generalised-alpha spectral radius (numerical damping).
        air_drag: If ``True``, apply the Reynolds-number air-drag law.
        eta_rod, eta_line: Material relaxation time [s] (Kelvin-Voigt damping)
            on the rod / line regions (``0`` is purely elastic).
        rod_diameter, line_diameter: Outer diameter [m] used by the air-drag
            law on the rod / line regions.

    Returns:
        Tuple ``(t, X, Y, s, chord, rod_tip_index)`` where ``t`` is the time
        grid (relative to RSP), ``X``/``Y`` are node positions of shape
        ``(n_steps, n_nodes)``, ``s`` is the arc-length grid, ``chord`` is the
        rod chord length over time, and ``rod_tip_index`` is the node index of
        the rod tip.
    """
    dom = cast1_domain(rod_length, line_out, n_nodes, EI_butt=EI_butt,
                       EI_rod_tip=EI_rod_tip, taper=taper, EI_line=EI_line,
                       mass_rod=mass_rod, mass_line=mass_line,
                       rod_diameter=rod_diameter, line_diameter=line_diameter,
                       eta_rod=eta_rod, eta_line=eta_line)
    s = dom.s
    rod_tip_index = int(np.argmin(np.abs(s - rod_length)))
    theta = cast1_stroke(t_start=t_span[0])
    bc_func = cast_bc(theta, n_nodes)

    x0 = st.zeros(n_nodes)
    x0.phi[:] = theta(t_span[0])

    f_drag = reynolds_drag(dom) if air_drag else None
    res = integrate(dom, bc_func, x0.to_vector(), t_span=t_span, dt=dt,
                    gravity=gravity, rho_inf=rho_inf, f_drag=f_drag)

    n_t = len(res.t)
    X = np.empty((n_t, n_nodes))
    Y = np.empty((n_t, n_nodes))
    for k in range(n_t):
        X[k], Y[k] = positions(res.fields_at(k).phi, s)
    chord = chord_length(X, Y, rod_tip_index)
    return res.t, X, Y, s, chord, rod_tip_index
