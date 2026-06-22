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

from .coords import positions, positions_multi
from .domain import Subdomain
from .drag import reynolds_drag
from .genalpha import integrate
from .operators import BoundaryConditions
from . import state as st
from . import _cast1_data
from . import components as _components


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
# Cast #1 is reproduced from the documented high-speed footage (``cast01_m1``):
# a 9 ft 5-wt rod (T&T Paradigm) driven by the measured rod-butt motion, with
# the full fly line + leader out of the tip.  The tackle is now modelled as a
# **multi-subdomain assembly** -- a distinct rod, fly line and leader, each with
# its own data-driven tapered material profile -- joined at explicit junctions:
#
#   * rod -> line is a **pinned hinge** (the soft line transmits no bending
#     moment to the rod tip), so the line may lay back at an angle to the rod;
#   * line -> leader is **welded/continuous** (tangent angle and bending moment
#     carried across).
#
# The component profiles (rod EI/mass taper, fly-line head/belly/running-line
# density, tapered leader) live in ``flycastsim/data/components/cast1/`` as
# JSON metadata + CSV tables and are loaded with
# :func:`flycastsim.fem.components.load_rig`.
#
# Honest caveats (also surfaced in the docs / dashboard):
#   * The line starts laid out **behind** the caster, tilted ~5 deg below
#     horizontal (line end lowest, rod tip highest); the pinned rod-line hinge
#     lets it lay back without an artificial angle blend.  The quantitative
#     comparison stays on the **rod** kinematics (chord length / stop sequence).
#   * The fly-line mass is scaled from the AFTM ``line_weight`` standard.
#   * A little line/leader material damping (``CAST1_LINE_ETA``) keeps the floppy
#     tilted layout numerically stable; the rod stays elastic.
#   * The rod-butt angle, the hand haul path and the chord curve are approximate
#     readings of the footage / low-resolution magazine figures (indicative).
#   * The long floppy line needs a fairly fine grid to stay numerically stable.
# ---------------------------------------------------------------------------

#: Name of the bundled component rig describing Cast #1.
CAST1_RIG = "cast1"

#: Reference rod length for Cast #1 (9 ft) [m].
CAST1_ROD_LENGTH = _cast1_data.RIG["rod_length_m"]

#: Arc-length up the rod blank, measured from the butt, of the base point used
#: for the rod **chord length** [m].  The chord is measured from the rod tip to
#: the node at this arc-length (a fixed reference point ~30 cm above the grip),
#: rather than from the rod butt itself.
CAST1_CHORD_BASE_S = 0.30

#: Full modelled line length out of the rod tip for Cast #1: ~10 m of fly line
#: plus a 9 ft leader [m].
CAST1_LINE_OUT = (_cast1_data.RIG["line_out_m"]
                  + _cast1_data.RIG["leader_length_m"])

#: Initial tangent angle of the modelled fly line for Cast #1 [deg], in the
#: engine's convention (``0`` = level forward/+x, ``+90`` = up).  ``185`` lays
#: the line out **behind** the caster tilted **5 deg below horizontal**, so the
#: line end is the lowest point and the rod tip the highest -- a backcast layout
#: sloping up toward the rod tip, from which the forward stroke is delivered.
CAST1_LINE_INIT_DEG = 185.0

#: Small material damping applied to the **line/leader** region by default for
#: Cast #1 [s].  A little Kelvin-Voigt damping keeps the floppy tilted-back
#: layout numerically stable while leaving the **rod** elastic, so the rod chord
#: kinematics are unaffected.
CAST1_LINE_ETA = 5.0e-3


def cast1_domain(*, rig: str = CAST1_RIG, aftm_weight: float | None = 5,
                 line_weight: float | None = None,
                 rod_ei_scale: float = 1.0, eta_rod: float = 0.0,
                 eta_line: float = CAST1_LINE_ETA,
                 n_nodes: int | None = None,
                 n_nodes_overrides: dict[str, int] | None = None):
    """Build the Cast #1 rod+line+leader :class:`MultiDomain` from data files.

    The component material profiles are loaded from the bundled rig
    (:func:`flycastsim.fem.components.load_rig`); the rod is subdomain 0, the fly
    line subdomain 1 and the leader subdomain 2, joined rod--line (pinned) and
    line--leader (welded).

    Args:
        rig: Rig source -- a bundled name (default ``"cast1"``) or a filesystem
            path to a ``rig.json``.
        aftm_weight: AFTM fly-line weight used to scale the line's mass profile
            (the heavier the line, the more it loads the rod).
        line_weight: Convenience alias for ``aftm_weight`` (the dashboard knob).
        rod_ei_scale: Multiplier applied to the **rod** bending-stiffness profile
            (a single stiffness knob for the whole rod).
        eta_rod: Material relaxation time [s] applied to the rod (``0`` =
            elastic).
        eta_line: Material relaxation time [s] applied to the line and leader.
        n_nodes: Optional **total** node budget, split across the components in
            proportion to their length (overridden by ``n_nodes_overrides``).
        n_nodes_overrides: Optional ``{component_kind: n_nodes}`` grid overrides.

    Returns:
        A :class:`~flycastsim.fem.multidomain.MultiDomain`.
    """
    if line_weight is not None:
        aftm_weight = line_weight

    def _load(overrides):
        return _components.load_rig(
            rig, aftm_weight=aftm_weight,
            eta_overrides={"rod": eta_rod, "line": eta_line,
                           "leader": eta_line},
            n_nodes_overrides=overrides)

    md = _load(n_nodes_overrides)
    if n_nodes is not None and n_nodes_overrides is None:
        md = _load(_proportional_nodes(md, int(n_nodes)))
    if rod_ei_scale != 1.0:
        md.subdomains[0].EI = md.subdomains[0].EI * float(rod_ei_scale)
    return md


def _proportional_nodes(md, total: int) -> dict[str, int]:
    """Split a total node budget across components in proportion to length."""
    lengths = np.array([sd.length for sd in md.subdomains], dtype=float)
    kinds = [c for c in _component_kinds(md)]
    raw = total * lengths / lengths.sum()
    counts = np.maximum(3, np.round(raw).astype(int))
    return {kind: int(n) for kind, n in zip(kinds, counts)}


def _component_kinds(md) -> list[str]:
    """Best-effort component kinds for a Cast #1 MultiDomain (rod/line/leader)."""
    default = ["rod", "line", "leader"]
    if md.n_subdomains == len(default):
        return default
    return [f"sd{i}" for i in range(md.n_subdomains)]


def cast1_rod_tip_index(md) -> int:
    """Global node index of the rod tip (last node of subdomain 0)."""
    return int(md.node_offsets[1]) - 1 if md.n_subdomains > 1 \
        else md.subdomains[0].n_nodes - 1


def cast1_chord_base_index(md, base_s: float = CAST1_CHORD_BASE_S) -> int:
    """Global node index of the rod **chord base point**.

    Returns the rod node nearest arc-length ``base_s`` along the rod from the
    butt (default :data:`CAST1_CHORD_BASE_S`, ~30 cm up the blank).  The result
    is clamped to the rod region (``<= cast1_rod_tip_index(md)``) so a coarse
    grid can never pick a line node.

    Args:
        md: The Cast #1 :class:`MultiDomain`.
        base_s: Target arc-length up the rod blank [m].

    Returns:
        The global node index of the chord base point.
    """
    rod_tip = cast1_rod_tip_index(md)
    s_rod = np.asarray(md.s)[:rod_tip + 1]
    return int(np.argmin(np.abs(s_rod - float(base_s))))


def cast1_initial_phi(theta0: float, md,
                      line_init_deg: float = CAST1_LINE_INIT_DEG) -> np.ndarray:
    """Initial tangent-angle field for Cast #1's *tilted backcast* layout.

    The **rod** subdomain starts straight at the handle angle ``theta0``; the
    fly line and leader start laid out **behind** the caster, tilted
    ``line_init_deg`` (default 185 deg = 5 deg below horizontal).  The pinned
    rod--line hinge carries the angle discontinuity, so no artificial blend is
    needed.

    Args:
        theta0: Handle (rod-butt) tangent angle at the start of the window [rad].
        md: The Cast #1 :class:`MultiDomain`.
        line_init_deg: Initial line/leader tangent angle [deg].

    Returns:
        Array of shape ``(md.n_nodes,)`` with the initial tangent angle [rad].
    """
    phi = np.full(md.n_nodes, float(theta0))
    target = np.deg2rad(float(line_init_deg))
    rod_end = int(md.node_offsets[1]) if md.n_subdomains > 1 else md.n_nodes
    phi[rod_end:] = target
    return phi


def chord_length(X: np.ndarray, Y: np.ndarray, rod_tip_index: int,
                 base_index: int = 0) -> np.ndarray:
    """Rod chord length over time.

    The chord is the straight-line distance from a base reference node on the
    rod to the rod tip.  For Cast #1 the base node is ~30 cm up the rod blank
    (see :func:`cast1_chord_base_index`); ``base_index=0`` reproduces the old
    butt-to-tip definition.

    Args:
        X, Y: Position arrays of shape ``(n_steps, n_nodes)``.
        rod_tip_index: Node index of the rod tip (end of the rod region).
        base_index: Node index of the chord base point (default ``0``, the
            rod butt / handle).

    Returns:
        Array of shape ``(n_steps,)`` with the straight-line distance from the
        base node to the rod tip at every time step.
    """
    return np.hypot(X[:, rod_tip_index] - X[:, base_index],
                    Y[:, rod_tip_index] - Y[:, base_index])


def tip_deflection(X: np.ndarray, Y: np.ndarray, rod_tip_index: int,
                   butt_angle: np.ndarray, base_index: int = 0
                   ) -> tuple[np.ndarray, np.ndarray]:
    """Rod tip deflection from the undeflected (straight) rod, over time.

    The "undeflected rod" is the infinite **tangent line** through the rod butt
    (``base_index``) pointing along the rod-butt tangent ``butt_angle``.  The
    deflection is the **perpendicular offset** of the rod tip from that line, so
    it is independent of rod length.  It is returned both as a **signed scalar**
    and as a **vector**.

    With the butt position ``P0``, tip ``Ptip``, ``v = Ptip - P0`` and the unit
    normal ``n_hat = (-sin(butt_angle), cos(butt_angle))`` (90 deg CCW from the
    tangent):

    * signed scalar ``d_signed = v . n_hat`` -- the perpendicular distance from
      the tip to the tangent line; ``> 0`` when the tip lies on the CCW side of
      the butt-tangent direction, ``< 0`` on the CW side, ``~0`` when straight.
    * vector ``d_vec = d_signed * n_hat`` -- the perpendicular offset as an
      ``(x, y)`` displacement, with ``hypot(d_vec) == abs(d_signed)``.

    Args:
        X, Y: Position arrays of shape ``(n_steps, n_nodes)``.
        rod_tip_index: Node index of the rod tip (end of the rod region).
        butt_angle: Rod-butt tangent angle [rad], shape ``(n_steps,)``.
        base_index: Node index anchoring the tangent line (default ``0``, the
            rod butt / handle).

    Returns:
        Tuple ``(d_signed, d_vec)`` with shapes ``(n_steps,)`` and
        ``(n_steps, 2)``.
    """
    butt_angle = np.asarray(butt_angle, dtype=float)
    vx = X[:, rod_tip_index] - X[:, base_index]
    vy = Y[:, rod_tip_index] - Y[:, base_index]
    nx = -np.sin(butt_angle)
    ny = np.cos(butt_angle)
    d_signed = vx * nx + vy * ny
    d_vec = np.stack([d_signed * nx, d_signed * ny], axis=-1)
    return d_signed, d_vec


def cast1_stroke(t_start: float = -0.40) -> Callable[[float], float]:
    """Return the handle-angle function ``theta(t)`` for Cast #1.

    The handle tangent angle follows the idealized rod-butt sweep fitted to the
    footage (:func:`flycastsim.fem._cast1_data.phi_handle_rad`): the rod stays
    elevated and sweeps clockwise from up-and-back (~125 deg) through the
    vertical to up-and-forward (~45 deg) as the loop forms.

    Args:
        t_start: Start time of the simulation window [s] (kept for signature
            compatibility; the drive is absolute).

    Returns:
        A callable ``theta(t)`` with ``t`` in seconds relative to RSP.
    """
    def theta(t: float) -> float:
        return float(_cast1_data.phi_handle_rad(t))

    return theta


def simulate_cast1(*, rig: str = CAST1_RIG, aftm_weight: float | None = 5,
                   line_weight: float | None = None,
                   rod_ei_scale: float = 1.0,
                   t_span: tuple[float, float] = (-0.40, 1.0),
                   dt: float = 2.0e-3, gravity: float = 9.81,
                   rho_inf: float = 0.6, air_drag: bool = False,
                   eta_rod: float = 0.0, eta_line: float = CAST1_LINE_ETA,
                   n_nodes: int | None = None,
                   n_nodes_overrides: dict[str, int] | None = None,
                   line_init_deg: float = CAST1_LINE_INIT_DEG):
    """Simulate Cast #1 with the multi-subdomain rod+line+leader model.

    The tackle is assembled from data-driven component profiles
    (:func:`cast1_domain`): a tapered rod, an AFTM-scaled fly line and a tapered
    leader, joined rod--line (pinned hinge) and line--leader (welded).  The
    handle (global node 0) both **rotates** (angle follows :func:`cast1_stroke`)
    and **translates** along a short hand-haul path
    (:func:`flycastsim.fem._cast1_data.hand_xy` / ``hand_vel``); the leader tip
    is free.  The line starts laid out **behind** the caster, tilted below
    horizontal (:func:`cast1_initial_phi`).  Time is measured **relative to RSP**
    (Rod Straight Position), so ``t = 0`` is RSP.

    Args:
        rig: Rig source (bundled name or path to a ``rig.json``).
        aftm_weight: AFTM fly-line weight that scales the line mass (the
            ``line_weight`` knob; heavier line loads the rod more).
        rod_ei_scale: Multiplier on the rod bending-stiffness profile.
        t_span: ``(t0, t1)`` simulation window [s] relative to RSP.
        dt: Time step [s].
        gravity: Gravitational acceleration [m/s^2].
        rho_inf: Generalised-alpha spectral radius (numerical damping).
        air_drag: If ``True``, apply the Reynolds-number air-drag law per
            subdomain.
        eta_rod, eta_line: Material relaxation times [s] on the rod / line+leader
            (``0`` is purely elastic).  ``eta_line`` defaults to
            :data:`CAST1_LINE_ETA` to stabilise the tilted-back line layout.
        n_nodes_overrides: Optional ``{component_kind: n_nodes}`` grid overrides.
        line_init_deg: Initial line/leader tangent angle [deg].

    Returns:
        Tuple ``(t, X, Y, s, chord, deflection, deflection_vec, rod_tip_index)``
        where ``t`` is the time grid (relative to RSP), ``X``/``Y`` are node
        positions of shape ``(n_steps, n_nodes)``, ``s`` is the global
        arc-length grid, ``chord`` is the rod chord length over time (rod tip to
        the base point ~30 cm up the blank, see :data:`CAST1_CHORD_BASE_S`),
        ``deflection`` is the signed perpendicular tip deflection from the
        undeflected (straight) rod and ``deflection_vec`` its ``(n_steps, 2)``
        vector form (see :func:`tip_deflection`), and ``rod_tip_index`` is the
        rod-tip node index.
    """
    md = cast1_domain(rig=rig, aftm_weight=aftm_weight, line_weight=line_weight,
                      rod_ei_scale=rod_ei_scale, eta_rod=eta_rod,
                      eta_line=eta_line, n_nodes=n_nodes,
                      n_nodes_overrides=n_nodes_overrides)
    s = md.s
    n_nodes = md.n_nodes
    rod_tip_index = cast1_rod_tip_index(md)

    theta = cast1_stroke(t_start=t_span[0])
    bc_func = cast1_bc(theta, _cast1_data.hand_vel, n_nodes)

    x0 = st.zeros(n_nodes)
    x0.phi[:] = cast1_initial_phi(theta(t_span[0]), md, line_init_deg)

    f_drag = ([reynolds_drag(sd) for sd in md.subdomains]
              if air_drag else None)
    res = integrate(md, bc_func, x0.to_vector(), t_span=t_span, dt=dt,
                    gravity=gravity, rho_inf=rho_inf, f_drag=f_drag)

    n_t = len(res.t)
    X = np.empty((n_t, n_nodes))
    Y = np.empty((n_t, n_nodes))
    for k in range(n_t):
        xh, yh = _cast1_data.hand_xy(res.t[k])
        X[k], Y[k] = positions_multi(res.fields_at(k), md,
                                     x0=float(xh), y0=float(yh))
    chord = chord_length(X, Y, rod_tip_index,
                         base_index=cast1_chord_base_index(md))
    butt_angle = _cast1_data.phi_handle_rad(res.t)
    deflection, deflection_vec = tip_deflection(X, Y, rod_tip_index, butt_angle)
    return res.t, X, Y, s, chord, deflection, deflection_vec, rod_tip_index
