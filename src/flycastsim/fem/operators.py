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
    s = dom.s
    m = dom.m
    EI = dom.EI
    eta = dom.eta
    dEI = dom.dEI_ds()
    n = dom.n_nodes

    fl = state.Fields.from_vector(x)
    vd = state.zeros(n) if xdot is None else state.Fields.from_vector(xdot)

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
