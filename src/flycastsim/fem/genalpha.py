"""Generalised-alpha time integration for the FEM fly-casting engine.

The first-order generalised-alpha method of Jansen, Whiting & Hulbert (2000)
is used.  It is second-order accurate and provides controllable high-frequency
numerical damping through the spectral radius ``rho_inf`` in ``[0, 1]``
(``rho_inf = 1`` -> no damping; ``rho_inf = 0`` -> maximal damping).

For a system written as a residual ``R(X, dX/dt, t) = 0`` (which may be a
differential-algebraic system, as here), one step from ``t_n`` to
``t_{n+1} = t_n + dt`` proceeds as follows.  With ``V = dX/dt``:

* unknown ``X_{n+1}`` (and ``V_{n+1}`` linked by the update rule)::

      V_{n+1} = (X_{n+1} - X_n) / (gamma * dt) - (1 - gamma)/gamma * V_n

* evaluate the residual at the intermediate levels::

      X_{n+af} = X_n + af * (X_{n+1} - X_n)
      V_{n+am} = V_n + am * (V_{n+1} - V_n)
      R(X_{n+af}, V_{n+am}, t_n + af * dt) = 0

The nonlinear system in ``X_{n+1}`` is solved with Newton-Raphson and the same
banded Jacobian machinery as the static solver.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import state
from .domain import Subdomain
from .operators import BoundaryConditions, residual, residual_multi
from .solver import _JacobianColouring, newton_solve


def genalpha_params(rho_inf: float) -> tuple[float, float, float]:
    """Return ``(alpha_m, alpha_f, gamma)`` for a given spectral radius."""
    if not (0.0 <= rho_inf <= 1.0):
        raise ValueError("rho_inf must be in [0, 1]")
    alpha_m = 0.5 * (3.0 - rho_inf) / (1.0 + rho_inf)
    alpha_f = 1.0 / (1.0 + rho_inf)
    gamma = 0.5 + alpha_m - alpha_f
    return alpha_m, alpha_f, gamma


@dataclass
class GenAlphaResult:
    """Result of a time integration.

    Attributes:
        t: 1-D array of output times, shape ``(nt,)``.
        X: Solution vectors, shape ``(nt, 7 * n_nodes)`` (node-major).
        s: Grid coordinates, shape ``(n_nodes,)``.
        iterations: Newton iterations used on each step, shape ``(nt-1,)``.
    """

    t: np.ndarray
    X: np.ndarray
    s: np.ndarray
    iterations: np.ndarray

    def fields_at(self, k: int) -> state.Fields:
        """Return the :class:`~flycastsim.fem.state.Fields` at output ``k``."""
        return state.Fields.from_vector(self.X[k])


def integrate(dom: Subdomain, bc_func, x0: np.ndarray, *,
              t_span: tuple[float, float], dt: float,
              v0: np.ndarray | None = None, rho_inf: float = 0.8,
              gravity: float = 9.81, f_drag=None,
              tol: float = 1e-9, max_iter: int = 50,
              verbose: bool = False) -> GenAlphaResult:
    """Integrate the dynamic problem in time with generalised-alpha.

    Args:
        dom: The subdomain (grid + material properties).
        bc_func: Callable ``t -> BoundaryConditions`` giving the (possibly
            time-dependent) boundary conditions.  A static
            :class:`~flycastsim.fem.operators.BoundaryConditions` may also be
            passed directly.
        x0: Initial solution vector (node-major).
        t_span: ``(t_start, t_end)``.
        dt: Time step.
        v0: Initial time derivative ``dX/dt`` (defaults to zeros).
        rho_inf: Spectral radius controlling numerical damping, in ``[0, 1]``.
        gravity: Gravitational acceleration [m/s^2].
        f_drag: Optional drag callable (see :func:`operators.residual`).
        tol: Newton convergence tolerance.
        max_iter: Maximum Newton iterations per step.
        verbose: Print per-step diagnostics.

    Returns:
        A :class:`GenAlphaResult`.
    """
    alpha_m, alpha_f, gamma = genalpha_params(rho_inf)

    is_multi = hasattr(dom, "subdomains")

    def eval_residual(x_af, bc, v_am):
        if is_multi:
            return residual_multi(x_af, dom, bc, xdot=v_am,
                                  gravity=gravity, f_drag=f_drag)
        return residual(x_af, dom, bc, xdot=v_am,
                        gravity=gravity, f_drag=f_drag)

    if callable(bc_func):
        get_bc = bc_func
    else:
        def get_bc(_t, _bc=bc_func):
            return _bc

    t0, t1 = t_span
    n_steps = int(round((t1 - t0) / dt))
    times = t0 + dt * np.arange(n_steps + 1)

    n = x0.size
    X_hist = np.empty((n_steps + 1, n))
    iters = np.empty(n_steps, dtype=int)

    # The boundary-condition *structure* (which nodes/fields) is assumed
    # constant in time; only the prescribed values may vary.  Build the
    # Jacobian colouring once.
    colouring = _JacobianColouring(dom, get_bc(t0))

    x_n = np.array(x0, dtype=float)
    v_n = np.zeros(n) if v0 is None else np.array(v0, dtype=float)
    X_hist[0] = x_n

    for k in range(n_steps):
        t_n = times[k]
        t_af = t_n + alpha_f * dt
        bc = get_bc(t_af)

        def resfun(x_np1, x_n=x_n, v_n=v_n, bc=bc):
            v_np1 = (x_np1 - x_n) / (gamma * dt) \
                - (1.0 - gamma) / gamma * v_n
            x_af = x_n + alpha_f * (x_np1 - x_n)
            v_am = v_n + alpha_m * (v_np1 - v_n)
            return eval_residual(x_af, bc, v_am)

        res = newton_solve(resfun, x_n, colouring, tol=tol,
                           max_iter=max_iter, verbose=verbose)
        x_np1 = res.x
        v_np1 = (x_np1 - x_n) / (gamma * dt) \
            - (1.0 - gamma) / gamma * v_n

        X_hist[k + 1] = x_np1
        iters[k] = res.iterations
        x_n, v_n = x_np1, v_np1

    return GenAlphaResult(t=times, X=X_hist, s=dom.s, iterations=iters)
