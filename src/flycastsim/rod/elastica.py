"""Static large-deflection bending of a clamped fly rod (the *elastica*).

This is the forward model for the static bend tests used to estimate a rod's
bending-stiffness profile :math:`EI(s)` (see ``docs/rod_profile.rst``): the rod
is clamped at :math:`s_c` (measured from the butt) at angle :math:`\\theta_c`
and loaded by its own weight and a point load at the tip.

The rod is modelled as a planar, inextensible, shear-free Euler--Bernoulli rod
(Bisshopp & Drucker 1945; Frisch-Fay, *Flexible Bars*, 1962).  With
:math:`\\theta(s)` the tangent angle above the horizontal and :math:`M(s)` the
bending moment (counter-clockwise positive, :math:`EI\\,\\theta' = M`):

.. math::

    x' = \\cos\\theta,\\qquad y' = \\sin\\theta,\\qquad
    \\theta' = \\frac{M}{EI(s)},\\qquad M' = W(s)\\cos\\theta,

where :math:`W(s) = P + g\\int_s^L \\mu(\\sigma)\\,d\\sigma` is the weight
outboard of :math:`s` (tip load :math:`P` plus self-weight).  The boundary
conditions are :math:`x = y = 0,\\ \\theta = \\theta_c` at the clamp and
:math:`M = 0` at the free tip.  :math:`y` points up; gravity acts along
:math:`-y`.

The two-point boundary-value problem is solved with
:func:`scipy.integrate.solve_bvp`.  Heavy loads are reached by load
continuation from the unloaded rod, and :func:`solve_load_sequence` warm-starts
each load from the previous solution.  :func:`solve_cantilever_fd` is a
faster fixed-mesh (trapezoidal) variant whose result depends smoothly on the
inputs, used for profile fitting.  A converged solution is only accepted
if the tangent angle stays between the clamp angle and straight down (the
stable branch for downward loads, for clamp angles in
:math:`(-3\\pi/2, \\pi/2]`); otherwise the load step is halved.

Deliberate simplifications (cf. the dynamic continuum engine in
:mod:`flycastsim.fem`): static equilibrium only, no axial stretching or shear,
and the rod is fixed rigidly at the clamp.  Everything is in SI units.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import cumulative_trapezoid, solve_bvp
from scipy.interpolate import CubicHermiteSpline
from scipy.linalg import solve_banded

#: Gravitational acceleration [m/s^2], matching :mod:`flycastsim.fem`.
GRAVITY = 9.81

#: A rod property along the arc length: a constant or a vectorised ``f(s)``.
Profile = float | Callable[[np.ndarray], np.ndarray]

# Resolution of the dense grid used to integrate the outboard self-weight.
_N_WEIGHT_GRID = 2001


def _as_function(p: Profile | None) -> Callable[[np.ndarray], np.ndarray]:
    if p is None:
        return lambda s: np.zeros_like(np.asarray(s, dtype=float))
    if callable(p):
        return lambda s: np.asarray(p(np.asarray(s, dtype=float)), dtype=float)
    value = float(p)
    return lambda s: np.full_like(np.asarray(s, dtype=float), value)


class ElasticaError(RuntimeError):
    """Raised when the boundary-value solver fails to converge."""


@dataclass
class ElasticaSolution:
    """Equilibrium shape of a clamped rod.

    Attributes:
        s: Solver mesh, arc length from the rod butt [m].
        x: Horizontal position relative to the clamp [m].
        y: Vertical position relative to the clamp (up positive) [m].
        theta: Tangent angle above the horizontal [rad].
        moment: Bending moment, counter-clockwise positive [N m].
        s_clamp: Clamp position measured from the butt [m].
        length: Assembled rod length (``s`` at the tip) [m].
        tip_load: Tip load ``P`` [N].
        clamp_angle: Clamp angle above the horizontal [rad].
    """

    s: np.ndarray
    x: np.ndarray
    y: np.ndarray
    theta: np.ndarray
    moment: np.ndarray
    s_clamp: float
    length: float
    tip_load: float
    clamp_angle: float
    _interp: Callable[[np.ndarray], np.ndarray] = field(repr=False)

    def at(self, s: float | np.ndarray) -> np.ndarray:
        """Interpolated state ``[x, y, theta, moment]`` at arc length(s) ``s``.

        Uses the solver's C1-continuous cubic interpolant; ``s`` must lie in
        ``[s_clamp, length]``.
        """
        return self._interp(np.asarray(s, dtype=float))

    @property
    def tip(self) -> tuple[float, float]:
        """Tip position ``(x, y)`` relative to the clamp [m]."""
        return float(self.x[-1]), float(self.y[-1])

    @property
    def tip_angle(self) -> float:
        """Tangent angle at the tip [rad]."""
        return float(self.theta[-1])

    @property
    def free_length(self) -> float:
        """Clamp-to-tip length ``length - s_clamp`` [m]."""
        return self.length - self.s_clamp


def outboard_weight(mu: Profile | None, s_clamp: float, length: float,
                    tip_load: float = 0.0, gravity: float = GRAVITY
                    ) -> Callable[[np.ndarray], np.ndarray]:
    """Return ``W(s)``: tip load plus the weight of the rod outboard of ``s``.

    The self-weight integral is evaluated by the trapezoidal rule on a dense
    grid, so piecewise profiles with jumps (ferrules) are handled.

    Args:
        mu: Linear mass density [kg/m], constant or ``f(s)``; ``None`` = 0.
        s_clamp: Clamp position from the butt [m].
        length: Rod length (tip position) [m].
        tip_load: Tip load ``P`` [N].
        gravity: Gravitational acceleration [m/s^2].
    """
    grid = np.linspace(s_clamp, length, _N_WEIGHT_GRID)
    mass = _as_function(mu)(grid)
    # Mass outboard of each grid point: integral from s to the tip.
    outboard = cumulative_trapezoid(mass[::-1], -grid[::-1], initial=0.0)[::-1]
    weight = gravity * outboard

    def W(s: np.ndarray) -> np.ndarray:
        return tip_load + np.interp(s, grid, weight)

    return W


def _initial_guess(mesh: np.ndarray, s_clamp: float, clamp_angle: float,
                   W: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
    """Straight rod at the clamp angle with its small-deflection moment."""
    c, s_ = np.cos(clamp_angle), np.sin(clamp_angle)
    w = W(mesh)
    # M(s) = -cos(theta_c) * integral_s^L W, for a straight rod.
    outboard = cumulative_trapezoid(w[::-1], -mesh[::-1], initial=0.0)[::-1]
    return np.vstack([(mesh - s_clamp) * c, (mesh - s_clamp) * s_,
                      np.full_like(mesh, clamp_angle), -c * outboard])


def _is_stable_branch(res, clamp_angle: float, atol: float = 1e-6) -> bool:
    """True if the tangent angle stays between the clamp angle and straight
    down, as on the stable equilibrium under downward loads.

    ``solve_bvp`` may otherwise converge to a spurious (e.g. looped) branch
    when started far from the solution.
    """
    lo, hi = sorted((clamp_angle, -np.pi / 2))
    theta = res.y[2]
    return bool(np.all(theta >= lo - atol) and np.all(theta <= hi + atol))


def _solve(EI_f, W, s_clamp, length, clamp_angle, mesh, guess, tol,
           max_nodes):
    def rhs(s, Y):
        theta, M = Y[2], Y[3]
        c = np.cos(theta)
        return np.vstack([c, np.sin(theta), M / EI_f(s), W(s) * c])

    def bc(ya, yb):
        return np.array([ya[0], ya[1], ya[2] - clamp_angle, yb[3]])

    res = solve_bvp(rhs, bc, mesh, guess, tol=tol, max_nodes=max_nodes)
    if res.success and not _is_stable_branch(res, clamp_angle):
        res.success = False
        res.message = "converged to a non-physical (looped) branch"
    return res


def solve_cantilever(EI: Profile, mu: Profile | None = None, *,
                     length: float, s_clamp: float = 0.0,
                     tip_load: float = 0.0, clamp_angle: float = 0.0,
                     gravity: float = GRAVITY,
                     guess: ElasticaSolution | None = None,
                     n_nodes: int = 101, tol: float = 1e-6,
                     max_nodes: int = 20000,
                     max_halvings: int = 8) -> ElasticaSolution:
    """Solve the static equilibrium of a clamped rod under self-weight and a
    tip load.

    Args:
        EI: Bending stiffness [N m^2], constant or vectorised ``f(s)``.
        mu: Linear mass density [kg/m], constant, ``f(s)`` or ``None``
            (weightless rod).
        length: Rod length; the tip is at ``s = length`` [m].
        s_clamp: Clamp position measured from the butt [m].
        tip_load: Downward point load at the tip, ``P = m_tip * g`` [N].
        clamp_angle: Clamp (butt) angle above the horizontal [rad].
        gravity: Gravitational acceleration [m/s^2].
        guess: Previous solution to warm-start from (e.g. a nearby load).
        n_nodes: Initial mesh size.
        tol: ``solve_bvp`` residual tolerance.
        max_nodes: ``solve_bvp`` mesh limit.
        max_halvings: How often a failed load-continuation step may be
            halved before giving up.

    Returns:
        The equilibrium :class:`ElasticaSolution`.

    Raises:
        ElasticaError: If no converged solution is found.
    """
    if not length > s_clamp:
        raise ValueError("length must be larger than s_clamp")
    EI_f = _as_function(EI)
    mesh = np.linspace(s_clamp, length, n_nodes)

    def weight(fraction: float):
        return outboard_weight(mu, s_clamp, length, fraction * tip_load,
                               fraction * gravity)

    if guess is not None:
        res = _solve(EI_f, weight(1.0), s_clamp, length, clamp_angle, mesh,
                     guess.at(mesh), tol, max_nodes)
        if res.success:
            return _wrap(res, s_clamp, length, tip_load, clamp_angle)

    # Load continuation from the unloaded (straight) rod: try the full load
    # first, halving the step whenever the solver fails to converge.
    done, step, halvings = 0.0, 1.0, 0
    Y = _initial_guess(mesh, s_clamp, clamp_angle, weight(0.0))
    res = None
    while done < 1.0:
        target = min(1.0, done + step)
        W = weight(target)
        first_guess = Y if res is None else res.sol(mesh)
        trial = _solve(EI_f, W, s_clamp, length, clamp_angle, mesh,
                       first_guess, tol, max_nodes)
        if trial.success:
            res, done = trial, target
            step = min(2.0 * step, 1.0 - done) if done < 1.0 else step
        else:
            halvings += 1
            if halvings > max_halvings:
                raise ElasticaError(
                    f"solve_bvp failed at load fraction {target:.4f}: "
                    f"{trial.message}")
            step /= 2.0
    return _wrap(res, s_clamp, length, tip_load, clamp_angle)


def _wrap(res, s_clamp, length, tip_load, clamp_angle) -> ElasticaSolution:
    x, y, theta, M = res.y
    return ElasticaSolution(s=res.x, x=x, y=y, theta=theta, moment=M,
                            s_clamp=s_clamp, length=length,
                            tip_load=tip_load, clamp_angle=clamp_angle,
                            _interp=res.sol)


def _fd_newton(EI_s, W_s, h, clamp_angle, theta, M, max_iter, atol,
               compliance=0.0):
    """Newton iteration for the trapezoidal fixed-mesh equations.

    The unknowns are interleaved as ``z = [theta_0, M_0, theta_1, M_1, ...]``
    and the equations ordered as clamp condition, then (rotation, moment)
    for each segment, then the free-tip condition; the Jacobian is then
    banded with two sub- and two super-diagonals and is solved with LAPACK's
    banded solver (:func:`scipy.linalg.solve_banded`).
    """
    n = len(theta) - 1
    N = 2 * n + 2
    half = 0.5 * h
    inv_EI = 1.0 / EI_s
    i = np.arange(n)
    r_rot = 2 * i + 1                 # rotation equation of segment i
    r_mom = 2 * i + 2                 # moment equation of segment i
    # Constant entries of the banded matrix: ab[2 + row - col, col].
    base = np.zeros((5, N))
    base[2, 0] = 1.0                  # clamp: d/d theta_0
    base[2 - 1, 1] = -compliance      # clamp: d/d M_0
    base[2 + r_rot - 2 * i, 2 * i] = -1.0              # rot: theta_i
    base[2 + r_rot - (2 * i + 2), 2 * i + 2] = 1.0     # rot: theta_i+1
    base[2 + r_rot - (2 * i + 1), 2 * i + 1] = -half * inv_EI[:-1]  # M_i
    base[2 + r_rot - (2 * i + 3), 2 * i + 3] = -half * inv_EI[1:]   # M_i+1
    base[2 + r_mom - (2 * i + 1), 2 * i + 1] = -1.0    # mom: M_i
    base[2 + r_mom - (2 * i + 3), 2 * i + 3] = 1.0     # mom: M_i+1
    base[2, N - 1] = 1.0              # free tip: d/d M_n
    R = np.empty(N)
    converged = False
    for _ in range(max_iter):
        c, s_ = np.cos(theta), np.sin(theta)
        kappa = M * inv_EI
        Wc = W_s * c
        R[0] = theta[0] - clamp_angle - compliance * M[0]
        R[r_rot] = np.diff(theta) - half * (kappa[:-1] + kappa[1:])
        R[r_mom] = np.diff(M) - half * (Wc[:-1] + Wc[1:])
        R[N - 1] = M[-1]
        ab = base.copy()
        ab[2 + r_mom - 2 * i, 2 * i] = half * W_s[:-1] * s_[:-1]
        ab[2 + r_mom - (2 * i + 2), 2 * i + 2] = half * W_s[1:] * s_[1:]
        try:
            delta = solve_banded((2, 2), ab, -R, overwrite_ab=True,
                                 check_finite=False)
        except np.linalg.LinAlgError:
            return theta, M, False
        if not np.all(np.isfinite(delta)):
            return theta, M, False
        theta = theta + delta[0::2]
        M = M + delta[1::2]
        if converged:
            return theta, M, True
        # One extra (quadratically convergent) step after reaching ``atol``
        # takes the solution to round-off, so that the result is a smooth
        # function of the inputs for finite-difference Jacobians.
        converged = np.max(np.abs(delta)) < atol
    return theta, M, converged


def solve_cantilever_fd(EI: Profile, mu: Profile | None = None, *,
                        length: float, s_clamp: float = 0.0,
                        tip_load: float = 0.0, clamp_angle: float = 0.0,
                        gravity: float = GRAVITY,
                        guess: ElasticaSolution | None = None,
                        clamp_compliance: float = 0.0,
                        n_segments: int = 200, atol: float = 1e-10,
                        max_iter: int = 30,
                        max_halvings: int = 8) -> ElasticaSolution:
    """Fixed-mesh variant of :func:`solve_cantilever` for profile fitting.

    The same equations are discretised with the trapezoidal rule on
    ``n_segments`` uniform segments (second-order accurate) and solved by
    Newton's method with a banded analytic Jacobian, then ``x``/``y`` are
    integrated with the trapezoidal rule.  Unlike the adaptive
    :func:`solve_cantilever`, the result is a smooth function of ``EI``,
    ``mu`` and the load, which finite-difference Jacobians in a
    least-squares fit need, and it is roughly ten times faster.  With 200
    segments the relative tip-position error is about ``1e-5``.

    Arguments are as for :func:`solve_cantilever`; ``atol`` is the Newton
    step tolerance and ``max_iter`` its iteration limit.  A non-rigid mount
    can be modelled with ``clamp_compliance`` ``c`` [rad/(N m)]: the rod
    angle at the clamp becomes ``clamp_angle + c * M(s_clamp)``, a linear
    rotational spring of stiffness ``1/c``.
    """
    if not length > s_clamp:
        raise ValueError("length must be larger than s_clamp")
    mesh = np.linspace(s_clamp, length, n_segments + 1)
    h = mesh[1] - mesh[0]
    EI_s = _as_function(EI)(mesh)

    def weight(fraction: float) -> np.ndarray:
        return outboard_weight(mu, s_clamp, length, fraction * tip_load,
                               fraction * gravity)(mesh)

    W_full = weight(1.0)

    def stable(theta) -> bool:
        lo, hi = sorted((theta[0], -np.pi / 2))
        return bool(np.all(theta >= lo - 1e-6) and np.all(theta <= hi + 1e-6))

    def attempt(W_s, theta, M):
        theta, M, ok = _fd_newton(EI_s, W_s, h, clamp_angle, theta, M,
                                  max_iter, atol, clamp_compliance)
        return theta, M, ok and stable(theta)

    state = None
    if guess is not None:
        _x, _y, theta0, M0 = guess.at(mesh)
        theta, M, ok = attempt(W_full, theta0, M0)
        if ok:
            state = (theta, M)
    if state is None:
        # Load continuation from the straight, unloaded rod.
        _x, _y, theta, M = _initial_guess(mesh, s_clamp, clamp_angle,
                                          lambda s: np.zeros_like(s))
        done, step, halvings = 0.0, 1.0, 0
        while done < 1.0:
            target = min(1.0, done + step)
            t_new, M_new, ok = attempt(
                W_full if target == 1.0 else weight(target), theta, M)
            if ok:
                theta, M, done = t_new, M_new, target
                step = min(2.0 * step, 1.0 - done) if done < 1.0 else step
            else:
                halvings += 1
                if halvings > max_halvings:
                    raise ElasticaError(
                        f"Newton failed at load fraction {target:.4f}")
                step /= 2.0
        state = (theta, M)

    theta, M = state
    c, s_ = np.cos(theta), np.sin(theta)
    x = cumulative_trapezoid(c, mesh, initial=0.0)
    y = cumulative_trapezoid(s_, mesh, initial=0.0)
    # one C1 cubic Hermite interpolant for all four state components
    spline = CubicHermiteSpline(mesh, np.vstack([x, y, theta, M]),
                                np.vstack([c, s_, M / EI_s, W_full * c]),
                                axis=1)

    def interp(s):
        return spline(s)

    return ElasticaSolution(s=mesh, x=x, y=y, theta=theta, moment=M,
                            s_clamp=s_clamp, length=length,
                            tip_load=tip_load, clamp_angle=clamp_angle,
                            _interp=interp)


def solve_load_sequence(EI: Profile, mu: Profile | None = None, *,
                        tip_loads: Sequence[float], length: float,
                        s_clamp: float = 0.0, clamp_angle: float = 0.0,
                        gravity: float = GRAVITY, solver=None, **kwargs
                        ) -> list[ElasticaSolution]:
    """Solve a sequence of tip loads, warm-starting each from the previous.

    Intended for the static bend test, where the load increases frame by
    frame.  ``solver`` is :func:`solve_cantilever` (default) or
    :func:`solve_cantilever_fd`; extra keyword arguments are passed to it.
    """
    solver = solve_cantilever if solver is None else solver
    out: list[ElasticaSolution] = []
    previous = None
    for load in tip_loads:
        previous = solver(EI, mu, length=length, s_clamp=s_clamp,
                                    tip_load=load, clamp_angle=clamp_angle,
                                    gravity=gravity, guess=previous,
                                    **kwargs)
        out.append(previous)
    return out
