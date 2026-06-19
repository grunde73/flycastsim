"""Nonlinear solver and high-level entry points for the FEM engine.

The discrete equations are solved with Newton-Raphson iteration.  The
Jacobian ``J = dE/dX`` is sparse (a consequence of the compact staggered
stencils): each residual row depends only on one or two neighbouring nodes.
It is assembled by finite differences using a two-colour (even/odd node)
scheme -- so the cost is ``2 * NFIELDS`` residual evaluations regardless of
problem size -- and the linear system is solved with a sparse direct solver.

This mirrors the procedure described in the paper: form the error vector,
assemble and invert the Jacobian, update the solution vector, and iterate to
convergence.  The paper uses a banded matrix; here the equivalent sparsity is
captured by the two-colour assembly and a sparse direct (SuperLU) solve.  A
backtracking line search makes the Newton iteration robust to poor initial
guesses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

from . import state
from .domain import Subdomain
from .operators import (BoundaryConditions, residual, residual_multi,
                        row_nodes, row_nodes_multi)


@dataclass
class NewtonResult:
    """Outcome of a Newton solve."""

    x: np.ndarray
    converged: bool
    iterations: int
    residual_norm: float


class _JacobianColouring:
    """Pre-computed structure for a two-colour finite-difference Jacobian.

    Each residual row depends on a small set of neighbouring nodes.  Colouring
    the nodes by parity guarantees that, for a given colour, at most one
    perturbed node influences any row, so the corresponding Jacobian column
    entries can be recovered from a single residual evaluation.
    """

    def __init__(self, dom, bc: BoundaryConditions):
        if hasattr(dom, "subdomains"):       # a MultiDomain
            rows = row_nodes_multi(dom, bc)
        else:                                # a single Subdomain
            rows = row_nodes(dom, bc)
        n_rows = len(rows)
        self.n_rows = n_rows
        self.n_nodes = dom.n_nodes
        # For each colour, the perturbed node influencing each row (-1 if none).
        self.node_for_colour = np.full((2, n_rows), -1, dtype=int)
        for r, nodes in enumerate(rows):
            for nd in nodes:
                self.node_for_colour[nd % 2, r] = nd
        self.row_idx = np.arange(n_rows)

    def jacobian(self, resfun, x: np.ndarray, eps: float = 1e-7
                 ) -> sp.csc_matrix:
        f0 = resfun(x)
        grid = x.reshape(-1, state.NFIELDS)
        rows_i, cols_j, vals = [], [], []
        for colour in (0, 1):
            nodes = np.arange(colour, self.n_nodes, 2)
            steps = eps * (np.abs(grid[nodes, :]) + eps)  # (n_pert, NFIELDS)
            for f in range(state.NFIELDS):
                dz = np.zeros_like(x)
                dz_grid = dz.reshape(-1, state.NFIELDS)
                dz_grid[nodes, f] = steps[:, f]
                df = resfun(x + dz) - f0
                nf = self.node_for_colour[colour]
                mask = nf >= 0
                r = self.row_idx[mask]
                nd = nf[mask]
                h = eps * (np.abs(grid[nd, f]) + eps)
                rows_i.append(r)
                cols_j.append(nd * state.NFIELDS + f)
                vals.append(df[mask] / h)
        J = sp.csc_matrix(
            (np.concatenate(vals),
             (np.concatenate(rows_i), np.concatenate(cols_j))),
            shape=(self.n_rows, x.size),
        )
        return J


def newton_solve(resfun, x0: np.ndarray, colouring: _JacobianColouring, *,
                 tol: float = 1e-9, max_iter: int = 50,
                 line_search: bool = True,
                 verbose: bool = False) -> NewtonResult:
    """Solve ``resfun(x) = 0`` with Newton-Raphson and a sparse Jacobian."""
    x = np.array(x0, dtype=float)
    for it in range(1, max_iter + 1):
        e = resfun(x)
        norm = float(np.linalg.norm(e))
        if verbose:
            print(f"  newton it={it} ||E||={norm:.3e}")
        if norm < tol:
            return NewtonResult(x, True, it - 1, norm)
        J = colouring.jacobian(resfun, x)
        dx = splu(J).solve(-e)
        if line_search:
            lam = 1.0
            for _ in range(40):
                x_try = x + lam * dx
                if np.all(np.isfinite(x_try)) and \
                        np.linalg.norm(resfun(x_try)) < norm:
                    break
                lam *= 0.5
            x = x + lam * dx
        else:
            x = x + dx
    norm = float(np.linalg.norm(resfun(x)))
    return NewtonResult(x, norm < tol, max_iter, norm)


def solve_static(dom: Subdomain, bc: BoundaryConditions, *,
                 x0: np.ndarray | None = None, gravity: float = 9.81,
                 f_drag=None, **newton_kw) -> NewtonResult:
    """Solve the static (time-independent) problem on a subdomain.

    Args:
        dom: The subdomain (grid + properties).
        bc: Boundary conditions (six rows).
        x0: Initial guess (defaults to zeros).
        gravity: Gravitational acceleration [m/s^2].
        f_drag: Optional drag callable (see :func:`operators.residual`).
        **newton_kw: Forwarded to :func:`newton_solve`.

    Returns:
        A :class:`NewtonResult`; unpack with
        :meth:`flycastsim.fem.state.Fields.from_vector`.
    """
    if x0 is None:
        x0 = np.zeros(state.n_unknowns(dom.n_nodes))

    colouring = _JacobianColouring(dom, bc)

    def resfun(x):
        return residual(x, dom, bc, xdot=None, gravity=gravity, f_drag=f_drag)

    return newton_solve(resfun, x0, colouring, **newton_kw)


def solve_static_multi(md, bc: BoundaryConditions, *,
                       x0: np.ndarray | None = None, gravity: float = 9.81,
                       f_drag=None, **newton_kw) -> NewtonResult:
    """Solve the static problem on a :class:`~flycastsim.fem.multidomain.MultiDomain`.

    Args:
        md: The multi-subdomain assembly.
        bc: Boundary conditions at the physical ends (global node indices).
        x0: Initial guess (defaults to zeros).
        gravity: Gravitational acceleration [m/s^2].
        f_drag: ``None`` or a list of per-subdomain drag callables.
        **newton_kw: Forwarded to :func:`newton_solve`.

    Returns:
        A :class:`NewtonResult`.
    """
    if x0 is None:
        x0 = np.zeros(state.n_unknowns(md.n_nodes))

    colouring = _JacobianColouring(md, bc)

    def resfun(x):
        return residual_multi(x, md, bc, xdot=None, gravity=gravity,
                              f_drag=f_drag)

    return newton_solve(resfun, x0, colouring, **newton_kw)
