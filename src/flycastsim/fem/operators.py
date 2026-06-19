"""Spatial discretisation and residual assembly for the FEM engine.

The seven coupled field equations of Ekander, Perkins & Richards
(*Sports Engineering* 2025) are discretised on a **staggered** grid using
compact, second-order centered differences:

* the six equations that contain a spatial derivative (the two kinematic
  constraints, the two momentum equations and the two curvature definitions)
  are enforced at the ``N-1`` cell **midpoints**, using the compact stencil
  ``df/ds|_{j+1/2} = (f[j+1] - f[j]) / ds`` and midpoint averages
  ``f|_{j+1/2} = (f[j] + f[j+1]) / 2``;
* the algebraic moment/curvature relation (eq 9), which has no spatial
  derivative of an unknown, is enforced at the ``N`` **nodes**.

This staggered placement is compact (each equation couples only neighbouring
nodes) and -- unlike collocated centered differences -- does not admit the
spurious odd/even ("checkerboard") modes, while remaining second-order
accurate.  The six remaining degrees of freedom are fixed by six boundary
conditions appended to the residual.

Field / equation symbols follow :mod:`flycastsim.fem.state`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import state
from .domain import Subdomain

GRAVITY = 9.81

# Midpoint-equation slot indices (order within each cell block) --------------
EQ_KIN_S = 0     # eq (1):  du_s/ds = u_n nu_z
EQ_KIN_N = 1     # eq (2):  dphi/dt - du_n/ds = u_s nu_z
EQ_MOM_S = 2     # eq (3):  tangential momentum
EQ_MOM_N = 3     # eq (4):  normal momentum
EQ_DEF_NU = 4    # def:     nu_z = dphi/ds
EQ_DEF_GAMMA = 5  # def:     Gamma_z = dnu_z/ds
N_MID_EQ = 6


@dataclass
class BoundaryRow:
    """A single Dirichlet boundary condition appended to the residual.

    The appended residual is ``X[field @ node] - value``.

    Args:
        node: Grid node index (typically 0 or N-1).
        field: Field index (see :mod:`flycastsim.fem.state`) being fixed.
        value: Prescribed value of the field at the node.
    """

    node: int
    field: int
    value: float


@dataclass
class BoundaryConditions:
    """A collection of Dirichlet boundary conditions.

    A well-posed single-subdomain problem requires exactly six conditions
    (typically three at each end).
    """

    rows: list[BoundaryRow] = field(default_factory=list)

    def dirichlet(self, node: int, fld: int, value: float
                  ) -> "BoundaryConditions":
        """Prescribe ``field = value`` at ``node``."""
        self.rows.append(BoundaryRow(node, fld, value))
        return self

    # Backwards-compatible alias.
    def add(self, node: int, fld: int, value: float) -> "BoundaryConditions":
        return self.dirichlet(node, fld, value)

    @property
    def n_bc(self) -> int:
        return len(self.rows)


def n_residual(n_nodes: int, n_bc: int) -> int:
    """Total residual length: nodal eq9 + midpoint eqs + boundary rows."""
    return n_nodes + N_MID_EQ * (n_nodes - 1) + n_bc


def _interior_residual(fl: "state.Fields", vd: "state.Fields", dom: Subdomain,
                       *, gravity: float, f_drag) -> tuple[np.ndarray, np.ndarray]:
    """Assemble one subdomain's interior residual blocks.

    Returns ``(res_node, res_mid)`` where ``res_node`` has shape ``(N,)`` (the
    nodal moment/curvature relation, eq 9) and ``res_mid`` has shape
    ``(N-1, N_MID_EQ)`` (the staggered midpoint equations).  No boundary or
    coupling rows are added here.

    Args:
        fl: Solution :class:`~flycastsim.fem.state.Fields` on this subdomain.
        vd: Time-derivative fields ``dX/dt`` on this subdomain.
        dom: The :class:`Subdomain` (grid + material properties).
        gravity: Gravitational acceleration [m/s^2].
        f_drag: Optional callable ``(fields) -> (f_s, f_n)`` for this subdomain.
    """
    s = dom.s
    m = dom.m
    EI = dom.EI
    eta = dom.eta
    dEI = dom.dEI_ds()
    n = dom.n_nodes

    # --- Nodal moment/curvature relation, eq (9) ---------------------------
    res_node = (
        EI * (fl.Gamma_z + eta * vd.Gamma_z)
        + dEI * (fl.nu_z + eta * vd.nu_z)
        + fl.F_n
    )

    # --- Midpoint quantities (compact centered scheme) ---------------------
    ds = np.diff(s)

    def mid(a):
        return 0.5 * (a[1:] + a[:-1])

    def dd(a):
        return (a[1:] - a[:-1]) / ds

    us_m, un_m = mid(fl.u_s), mid(fl.u_n)
    Fs_m, Fn_m = mid(fl.F_s), mid(fl.F_n)
    phi_m, nu_m = mid(fl.phi), mid(fl.nu_z)
    Gam_m = mid(fl.Gamma_z)
    m_m = mid(m)

    dus, dun = dd(fl.u_s), dd(fl.u_n)
    dphi, dnu = dd(fl.phi), dd(fl.nu_z)
    dFs, dFn = dd(fl.F_s), dd(fl.F_n)

    vus_m, vun_m, vphi_m = mid(vd.u_s), mid(vd.u_n), mid(vd.phi)

    if f_drag is None:
        fs_drag = np.zeros(n - 1)
        fn_drag = np.zeros(n - 1)
    else:
        fs_drag, fn_drag = f_drag(fl)
        fs_drag = mid(np.asarray(fs_drag, dtype=float))
        fn_drag = mid(np.asarray(fn_drag, dtype=float))

    res_mid = np.empty((n - 1, N_MID_EQ))
    # eq (1)
    res_mid[:, EQ_KIN_S] = dus - un_m * nu_m
    # eq (2)
    res_mid[:, EQ_KIN_N] = vphi_m - dun - us_m * nu_m
    # eq (3) tangential momentum
    res_mid[:, EQ_MOM_S] = (
        m_m * (vus_m - un_m * dun - us_m * dus)
        - dFs + nu_m * Fn_m + m_m * gravity * np.sin(phi_m) + fs_drag
    )
    # eq (4) normal momentum
    res_mid[:, EQ_MOM_N] = (
        m_m * (vun_m + us_m * dun + us_m ** 2 * dphi)
        - dFn - nu_m * Fs_m + m_m * gravity * np.cos(phi_m) + fn_drag
    )
    # def nu_z
    res_mid[:, EQ_DEF_NU] = nu_m - dphi
    # def Gamma_z
    res_mid[:, EQ_DEF_GAMMA] = Gam_m - dnu

    return res_node, res_mid


def residual(x: np.ndarray, dom: Subdomain, bc: BoundaryConditions,
             *, xdot: np.ndarray | None = None,
             gravity: float = GRAVITY, f_drag=None) -> np.ndarray:
    """Assemble the full residual (error) vector ``E``.

    Args:
        x: Flat node-major solution vector (length ``7 * N``).
        dom: The :class:`Subdomain` (grid + material properties).
        bc: Boundary conditions (six rows for a well-posed problem).
        xdot: Flat node-major time-derivative vector ``dX/dt``.  ``None``
            (the default) means a static problem (all time terms zero).
        gravity: Gravitational acceleration [m/s^2]. Use 0 to disable.
        f_drag: Optional callable ``(fields) -> (f_s, f_n)`` returning air
            drag force per unit length arrays.  Defaults to no drag.

    Returns:
        The residual vector ``E`` of length ``n_nodes + 6*(n_nodes-1) + n_bc``.
    """
    n = dom.n_nodes
    fl = state.Fields.from_vector(x)
    vd = state.zeros(n) if xdot is None else state.Fields.from_vector(xdot)

    res_node, res_mid = _interior_residual(fl, vd, dom, gravity=gravity,
                                           f_drag=f_drag)

    # --- Boundary conditions ----------------------------------------------
    grid = x.reshape(-1, state.NFIELDS)
    res_bc = np.array([grid[br.node, br.field] - br.value for br in bc.rows])

    return np.concatenate((res_node, res_mid.reshape(-1), res_bc))


def row_nodes(dom: Subdomain, bc: BoundaryConditions) -> list[np.ndarray]:
    """Candidate node indices each residual row depends on.

    Used by the sparse-Jacobian colouring in :mod:`flycastsim.fem.solver`.
    The residual ordering is: ``N`` nodal eq-(9) rows, then ``6*(N-1)``
    midpoint rows (cell-major), then the boundary rows.
    """
    n = dom.n_nodes
    rows: list[np.ndarray] = []
    for i in range(n):
        rows.append(np.array([i]))
    for j in range(n - 1):
        for _ in range(N_MID_EQ):
            rows.append(np.array([j, j + 1]))
    for br in bc.rows:
        rows.append(np.array([br.node]))
    return rows


# ===========================================================================
# Multi-subdomain assembly (rod + line + leader joined at junctions)
# ===========================================================================
#: Number of coupling equations contributed by each junction.
N_JUNCTION_EQ = 6


def local_to_world(s_comp: np.ndarray | float, n_comp: np.ndarray | float,
                   phi: np.ndarray | float
                   ) -> tuple[np.ndarray | float, np.ndarray | float]:
    """Rotate a local ``(tangential, normal)`` vector into world ``(x, y)``.

    With tangent angle ``phi`` the unit tangent is ``(cos phi, sin phi)`` and the
    unit normal is ``(-sin phi, cos phi)``, so::

        x =  s_comp * cos(phi) - n_comp * sin(phi)
        y =  s_comp * sin(phi) + n_comp * cos(phi)

    This converts the local velocity ``(u_s, u_n)`` or internal force
    ``(F_s, F_n)`` at a node into the world frame, used to express junction
    continuity that is invariant to a tangent-angle kink.
    """
    c, sn = np.cos(phi), np.sin(phi)
    x = s_comp * c - n_comp * sn
    y = s_comp * sn + n_comp * c
    return x, y


def _node_fields(grid: np.ndarray, node: int) -> dict:
    """Pull the seven fields at a single global ``node`` from the reshaped grid."""
    row = grid[node]
    return {
        "u_s": row[state.U_S], "u_n": row[state.U_N],
        "F_s": row[state.F_S], "F_n": row[state.F_N],
        "phi": row[state.PHI], "nu_z": row[state.NU_Z],
        "Gamma_z": row[state.GAMMA_Z],
    }


def junction_residual(grid: np.ndarray, left_node: int, right_node: int,
                      kind: str, EI_left: float, EI_right: float) -> np.ndarray:
    """The six coupling residuals joining two subdomains at a junction.

    Args:
        grid: The global solution vector reshaped to ``(n_nodes, NFIELDS)``.
        left_node: Global index of the left subdomain's last node.
        right_node: Global index of the right subdomain's first node.
        kind: ``"pinned"`` or ``"welded"``.
        EI_left, EI_right: Bending stiffness at the two junction nodes [N m^2].

    Returns:
        A length-6 residual array (all zero when the coupling is satisfied).

    Both joints enforce **world-frame velocity and force continuity** (4 rows).
    A ``pinned`` joint additionally enforces a **free hinge** (zero bending
    moment, i.e. ``nu_z = 0`` on each side); a ``welded`` joint enforces
    **tangent-angle continuity** and **bending-moment continuity**
    (``EI_left * nu_left = EI_right * nu_right``).
    """
    L = _node_fields(grid, left_node)
    R = _node_fields(grid, right_node)

    vxL, vyL = local_to_world(L["u_s"], L["u_n"], L["phi"])
    vxR, vyR = local_to_world(R["u_s"], R["u_n"], R["phi"])
    FxL, FyL = local_to_world(L["F_s"], L["F_n"], L["phi"])
    FxR, FyR = local_to_world(R["F_s"], R["F_n"], R["phi"])

    res = np.empty(N_JUNCTION_EQ)
    res[0] = vxL - vxR          # world velocity continuity
    res[1] = vyL - vyR
    res[2] = FxL - FxR          # world force continuity
    res[3] = FyL - FyR
    if kind == "pinned":
        res[4] = L["nu_z"]      # free hinge: zero moment each side
        res[5] = R["nu_z"]
    elif kind == "welded":
        res[4] = L["phi"] - R["phi"]                 # tangent continuity
        res[5] = EI_left * L["nu_z"] - EI_right * R["nu_z"]   # moment continuity
    else:
        raise ValueError(f"unknown junction kind {kind!r}")
    return res


def n_residual_multi(md, n_bc: int) -> int:
    """Total multi-subdomain residual length."""
    interior = sum(sd.n_nodes + N_MID_EQ * (sd.n_nodes - 1)
                   for sd in md.subdomains)
    return interior + N_JUNCTION_EQ * len(md.junctions) + n_bc


def residual_multi(x: np.ndarray, md, bc: BoundaryConditions, *,
                   xdot: np.ndarray | None = None,
                   gravity: float = GRAVITY, f_drag=None) -> np.ndarray:
    """Assemble the residual for a :class:`~flycastsim.fem.multidomain.MultiDomain`.

    The residual is ordered as: for each subdomain in turn its ``N_i`` nodal
    eq-(9) rows then its ``6*(N_i-1)`` midpoint rows; then ``6`` rows per
    junction; then the boundary rows (which use **global** node indices).

    Args:
        x: Flat global node-major solution vector (length ``7 * n_nodes``).
        md: The :class:`~flycastsim.fem.multidomain.MultiDomain`.
        bc: Boundary conditions at the physical ends (global node indices).
        xdot: Flat global time-derivative vector (``None`` => static).
        gravity: Gravitational acceleration [m/s^2].
        f_drag: ``None``, or a list of per-subdomain drag callables aligned with
            ``md.subdomains`` (each ``(fields) -> (f_s, f_n)``).

    Returns:
        The full residual vector ``E``.
    """
    grid = x.reshape(-1, state.NFIELDS)
    vgrid = (np.zeros_like(grid) if xdot is None
             else xdot.reshape(-1, state.NFIELDS))

    node_blocks: list[np.ndarray] = []
    mid_blocks: list[np.ndarray] = []
    for i, dom in enumerate(md.subdomains):
        sl = md.subdomain_slice(i)
        fl = state.Fields.from_vector(grid[sl].reshape(-1))
        vd = state.Fields.from_vector(vgrid[sl].reshape(-1))
        drag_i = None if f_drag is None else f_drag[i]
        res_node, res_mid = _interior_residual(fl, vd, dom, gravity=gravity,
                                               f_drag=drag_i)
        node_blocks.append(res_node)
        mid_blocks.append(res_mid.reshape(-1))

    res_junc: list[np.ndarray] = []
    for j in md.junctions:
        left_node, right_node = md.junction_nodes(j)
        EI_left = md.subdomains[j.left].EI[-1]
        EI_right = md.subdomains[j.right].EI[0]
        res_junc.append(junction_residual(grid, left_node, right_node,
                                          j.kind, EI_left, EI_right))

    res_bc = np.array([grid[br.node, br.field] - br.value for br in bc.rows])

    parts = node_blocks + mid_blocks + res_junc
    if res_bc.size:
        parts.append(res_bc)
    return np.concatenate(parts)


def row_nodes_multi(md, bc: BoundaryConditions) -> list[np.ndarray]:
    """Candidate global node indices each multi-subdomain residual row depends on.

    Mirrors the row ordering of :func:`residual_multi` so the sparse-Jacobian
    colouring in :mod:`flycastsim.fem.solver` can be reused.  Junction rows
    depend on the two (globally adjacent, opposite-parity) junction nodes.
    """
    rows: list[np.ndarray] = []
    # Per-subdomain nodal rows, then that subdomain's midpoint rows.
    node_rows: list[np.ndarray] = []
    mid_rows: list[np.ndarray] = []
    for i, dom in enumerate(md.subdomains):
        off = int(md.node_offsets[i])
        n = dom.n_nodes
        for k in range(n):
            node_rows.append(np.array([off + k]))
        for j in range(n - 1):
            for _ in range(N_MID_EQ):
                mid_rows.append(np.array([off + j, off + j + 1]))
    rows.extend(node_rows)
    rows.extend(mid_rows)
    for j in md.junctions:
        left_node, right_node = md.junction_nodes(j)
        for _ in range(N_JUNCTION_EQ):
            rows.append(np.array([left_node, right_node]))
    for br in bc.rows:
        rows.append(np.array([br.node]))
    return rows
