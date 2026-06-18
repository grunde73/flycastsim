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


def cast1_bc(theta: Callable[[float], float],
             hand_vel: Callable[[float], tuple[float, float]],
             n_nodes: int) -> Callable[[float], BoundaryConditions]:
    """Boundary conditions for Cast #1 with a **translating** rotating handle.

    Like :func:`cast_bc`, but the handle (node 0) is not a fixed pivot: it both
    rotates (``phi(0,t)=theta(t)``) **and** translates along a prescribed hand
    path.  The hand's world-frame velocity ``(vx, vy)`` from ``hand_vel(t)`` is
    projected into the rod's local tangent/normal frame at the handle (tangent
    angle ``theta(t)``) and applied as the node-0 velocity Dirichlet data::

        u_s =  vx*cos(theta) + vy*sin(theta)
        u_n = -vx*sin(theta) + vy*cos(theta)

    The tip (last node) is free.

    Args:
        theta: Handle-angle function ``theta(t)``.
        hand_vel: Hand world-velocity function ``t -> (vx, vy)`` [m/s].
        n_nodes: Number of grid nodes.

    Returns:
        A callable ``bc_func(t) -> BoundaryConditions``.
    """
    last = n_nodes - 1

    def bc_func(t: float) -> BoundaryConditions:
        a = theta(t)
        vx, vy = hand_vel(t)
        u_s = vx * np.cos(a) + vy * np.sin(a)
        u_n = -vx * np.sin(a) + vy * np.cos(a)
        bc = BoundaryConditions()
        bc.dirichlet(0, st.U_S, float(u_s)).dirichlet(0, st.U_N, float(u_n))
        bc.dirichlet(0, st.PHI, float(a))
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
# driven by the rod-butt motion measured from the footage.  The rod stays
# elevated and sweeps **clockwise from up-and-back (Q2) to up-and-forward (Q1)**
# while the hand both **rotates and translates** (a short forward haul); the
# full fly line + leader out of the tip is modelled and drawn.  See
# :mod:`flycastsim.fem._cast1_data` for the reference data and its provenance.
#
# Honest caveats (also surfaced in the docs / dashboard):
#   * The line starts laid out **behind** the caster, tilted ~15 deg below
#     horizontal (line end lowest, rod tip highest), and is a single subdomain,
#     so it cannot unroll into a fully realistic loop -- the full-length line
#     lofts/drapes rather than forming a crisp loop; the quantitative comparison
#     stays on the **rod** kinematics (the chord length / stop sequence).
#   * The line mass per length is set from the AFTM ``line_weight`` standard
#     (rated 30 ft head mass spread over its length; heavier line loads the rod
#     more).
#   * A little line-only material damping (``CAST1_LINE_ETA``) keeps that floppy
#     tilted layout numerically stable; the rod itself stays elastic.
#   * The rod-butt angle, the hand haul path and the chord curve are approximate
#     readings of the footage / low-resolution magazine figures (indicative).
#   * The long floppy line needs a fairly fine grid (``n_nodes >= 101``) to stay
#     numerically stable.
# ---------------------------------------------------------------------------

#: Reference rod length for Cast #1 (9 ft) [m].
CAST1_ROD_LENGTH = _cast1_data.RIG["rod_length_m"]

#: Full modelled line length out of the rod tip for Cast #1: ~10 m of fly line
#: plus a 9 ft leader [m].
CAST1_LINE_OUT = (_cast1_data.RIG["line_out_m"]
                  + _cast1_data.RIG["leader_length_m"])

#: Initial tangent angle of the modelled fly line for Cast #1 [deg], in the
#: engine's convention (``0`` = level forward/+x, ``+90`` = up).  ``195`` lays
#: the line out **behind** the caster tilted **15 deg below horizontal**, so the
#: line end is the lowest point and the rod tip the highest -- a backcast layout
#: sloping up toward the rod tip, from which the forward stroke is delivered.
CAST1_LINE_INIT_DEG = 195.0

#: Number of nodes over which the initial shape blends from the rod-tip angle to
#: the tilted-back line angle, to avoid a hard kink at the junction.
CAST1_INIT_BLEND_NODES = 8

#: Small material damping applied to the **line** region by default for Cast #1
#: [s].  The tilted-back backcast layout starts with a (smoothed) angular
#: discontinuity at the rod tip; a little line-only Kelvin-Voigt damping keeps
#: the floppy line numerically stable while leaving the **rod** elastic, so the
#: rod chord kinematics are unaffected.
CAST1_LINE_ETA = 5.0e-3


def cast1_initial_phi(theta0: float, s: np.ndarray, rod_length: float,
                      line_init_deg: float = CAST1_LINE_INIT_DEG,
                      blend_nodes: int = CAST1_INIT_BLEND_NODES) -> np.ndarray:
    """Initial tangent-angle field for Cast #1's *tilted backcast* layout.

    The rod region (``s <= rod_length``) starts at the handle angle ``theta0``;
    the modelled fly line starts laid out **behind** the caster, tilted
    ``line_init_deg`` (default 195 deg = 15 deg below horizontal, pointing back
    and slightly down, so the line end is lowest and the rod tip highest).  To
    avoid a hard kink at the rod tip -- which makes the floppy line numerically
    unstable -- the angle blends linearly from ``theta0`` to ``line_init_deg``
    over the first ``blend_nodes`` line nodes past the junction.

    Args:
        theta0: Handle (rod-butt) tangent angle at the start of the window [rad].
        s: Arc-length grid of the domain [m].
        rod_length: Length of the rod region [m].
        line_init_deg: Initial line tangent angle [deg] (195 = tilted 15 deg
            below horizontal, behind the caster).
        blend_nodes: Number of line nodes over which to blend the junction.

    Returns:
        Array of shape ``s.shape`` with the initial tangent angle [rad].
    """
    phi = np.full(s.shape, float(theta0))
    tip = int(np.argmin(np.abs(s - rod_length)))
    target = np.deg2rad(float(line_init_deg))
    n = len(s)
    span = max(1, int(blend_nodes))
    for j in range(tip, n):
        frac = min(1.0, (j - tip) / span)
        phi[j] = theta0 + (target - theta0) * frac
    return phi


def cast1_domain(rod_length: float = CAST1_ROD_LENGTH,
                 line_out: float = CAST1_LINE_OUT,
                 n_nodes: int = 101, *, EI_butt: float = 180.0,
                 EI_rod_tip: float = 18.0, taper: float = 1.1,
                 EI_line: float = 0.05, mass_rod: float = 0.045,
                 mass_line: float | None = None, line_weight: float | None = 5,
                 rod_diameter: float = 6.0e-3, line_diameter: float = 1.2e-3,
                 eta_rod: float = 0.0,
                 eta_line: float = CAST1_LINE_ETA) -> Subdomain:
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
        mass_rod: Mass per length of the rod [kg/m].
        mass_line: Mass per length of the line [kg/m].  If ``None`` (default),
            it is derived from ``line_weight``.
        line_weight: AFTM fly-line weight number used to set ``mass_line`` (via
            :func:`flycastsim.fem._cast1_data.line_mass_per_length`) when
            ``mass_line`` is ``None``.  An explicit ``mass_line`` takes
            precedence.
        rod_diameter, line_diameter: Outer diameter [m] of the rod / line
            regions, used for air drag. No effect without a drag law.
        eta_rod, eta_line: Material relaxation time [s] (Kelvin-Voigt damping)
            on the rod / line regions. ``0`` (default) is purely elastic.

    Returns:
        A :class:`~flycastsim.fem.domain.Subdomain`.
    """
    if mass_line is None:
        mass_line = _cast1_data.line_mass_per_length(
            line_weight if line_weight is not None
            else _cast1_data.RIG["line_weight"])
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
    convention (target direction ``+x``, ``+90 deg`` = straight up).  The rod
    stays **elevated** and sweeps **clockwise**: it starts up-and-back (second
    quadrant, ~125 deg), rotates through the vertical near mid-stroke, and ends
    up-and-forward (first quadrant, ~45 deg) as the loop forms -- matching the
    observed Cast #1 rod motion.

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
                   line_out: float = CAST1_LINE_OUT, n_nodes: int = 101,
                   EI_butt: float = 180.0, EI_rod_tip: float = 18.0,
                   taper: float = 1.1, EI_line: float = 0.05,
                   mass_rod: float = 0.045, mass_line: float | None = None,
                   line_weight: float | None = 5,
                   t_span: tuple[float, float] = (-0.40, 0.13),
                   dt: float = 2.0e-3, gravity: float = 9.81,
                   rho_inf: float = 0.6,
                   air_drag: bool = False, eta_rod: float = 0.0,
                   eta_line: float = CAST1_LINE_ETA,
                   rod_diameter: float = 6.0e-3,
                   line_diameter: float = 1.2e-3):
    """Simulate Cast #1 driven by the fitted rod-butt motion.

    The handle (node 0) both **rotates** (angle follows :func:`cast1_stroke`)
    and **translates** along a short hand-haul path
    (:func:`flycastsim.fem._cast1_data.hand_xy` / ``hand_vel``); the tip is free.
    The full fly line + leader out of the tip is modelled (see
    :data:`CAST1_LINE_OUT`).  The line **starts laid out behind the caster,
    tilted 15 deg below horizontal** (line end lowest, rod tip highest; see
    :func:`cast1_initial_phi`), and a little line-only material damping
    (:data:`CAST1_LINE_ETA`) keeps that floppy layout numerically stable while
    the rod stays elastic.  The line mass is set by the AFTM ``line_weight``
    (heavier line loads the rod more).  Time is measured **relative to RSP** (Rod
    Straight Position), matching the article, so ``t = 0`` is RSP.

    Args:
        rod_length, line_out, n_nodes, EI_butt, EI_rod_tip, taper, EI_line,
        mass_rod, mass_line, line_weight: Domain parameters (see
            :func:`cast1_domain`).  ``line_weight`` (AFTM number, default 5) sets
            the line mass per length unless an explicit ``mass_line`` is given.
        t_span: ``(t0, t1)`` simulation window [s] relative to RSP.
        dt: Time step [s].
        gravity: Gravitational acceleration [m/s^2].
        rho_inf: Generalised-alpha spectral radius (numerical damping).
        air_drag: If ``True``, apply the Reynolds-number air-drag law.
        eta_rod, eta_line: Material relaxation time [s] (Kelvin-Voigt damping)
            on the rod / line regions (``0`` is purely elastic).  ``eta_line``
            defaults to :data:`CAST1_LINE_ETA` to stabilise the tilted-back
            line layout.
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
                       line_weight=line_weight,
                       rod_diameter=rod_diameter, line_diameter=line_diameter,
                       eta_rod=eta_rod, eta_line=eta_line)
    s = dom.s
    rod_tip_index = int(np.argmin(np.abs(s - rod_length)))
    theta = cast1_stroke(t_start=t_span[0])
    bc_func = cast1_bc(theta, _cast1_data.hand_vel, n_nodes)

    x0 = st.zeros(n_nodes)
    x0.phi[:] = cast1_initial_phi(theta(t_span[0]), s, rod_length)

    f_drag = reynolds_drag(dom) if air_drag else None
    res = integrate(dom, bc_func, x0.to_vector(), t_span=t_span, dt=dt,
                    gravity=gravity, rho_inf=rho_inf, f_drag=f_drag)

    n_t = len(res.t)
    X = np.empty((n_t, n_nodes))
    Y = np.empty((n_t, n_nodes))
    for k in range(n_t):
        xh, yh = _cast1_data.hand_xy(res.t[k])
        X[k], Y[k] = positions(res.fields_at(k).phi, s,
                               x0=float(xh), y0=float(yh))
    chord = chord_length(X, Y, rod_tip_index)
    return res.t, X, Y, s, chord, rod_tip_index
