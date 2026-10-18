# -*- coding: utf-8 -*-
"""Verification tests for the static large-deflection rod solver.

The solver (:mod:`flycastsim.rod.elastica`) is checked against

* small-deflection Euler--Bernoulli beam theory (uniform rod with tip load or
  self-weight, and a tapered rod with offset clamp via the unit-load method),
* the exact large-deflection tip-loaded cantilever (Bisshopp & Drucker 1945),
  evaluated by quadrature of the first integral of the elastica, and
* global static equilibrium about the clamp for a heavily loaded tapered rod.
"""
import math

import numpy as np
import pytest
from scipy.integrate import quad

from flycastsim.rod import solve_cantilever, solve_load_sequence
from flycastsim.rod.elastica import GRAVITY, outboard_weight


# ---------------------------------------------------------------------------
# Small deflection
# ---------------------------------------------------------------------------
def test_uniform_tip_load_small_deflection():
    """Tip deflection P L^3 / (3 EI) for a tiny tip load."""
    L, EI, P = 2.5, 12.0, 1e-3
    sol = solve_cantilever(EI, length=L, tip_load=P)
    expected = P * L**3 / (3 * EI)
    assert -sol.tip[1] == pytest.approx(expected, rel=1e-4)
    assert sol.tip_angle == pytest.approx(-P * L**2 / (2 * EI), rel=1e-4)


def test_uniform_self_weight_small_deflection():
    """Tip deflection w L^4 / (8 EI) under a light uniform self-weight."""
    L, EI, mu = 2.0, 50.0, 1e-4
    sol = solve_cantilever(EI, mu, length=L)
    w = mu * GRAVITY
    assert -sol.tip[1] == pytest.approx(w * L**4 / (8 * EI), rel=1e-4)


def test_tapered_rod_offset_clamp_unit_load():
    """Tapered EI and mu with the clamp away from the butt.

    Linear theory (unit-load method): the tip deflection is
    ``int_{s_c}^L M(s) (L - s) / EI(s) ds`` with ``M(s) = int_s^L W``.
    """
    L, s_c, P = 2.74, 0.25, 2e-3
    EI = lambda s: 40.0 * np.exp(-1.1 * s)          # noqa: E731
    mu = lambda s: 0.06 - 0.015 * s                 # noqa: E731
    scale = 1e-3                                    # keep deflections tiny
    sol = solve_cantilever(EI, lambda s: scale * mu(s), length=L,
                           s_clamp=s_c, tip_load=P)

    W = outboard_weight(lambda s: scale * mu(s), s_c, L, P)

    def moment(s):
        return quad(lambda t: float(W(np.array(t))), s, L)[0]

    expected = quad(lambda s: moment(s) * (L - s) / EI(s), s_c, L,
                    limit=200)[0]
    assert -sol.tip[1] == pytest.approx(expected, rel=1e-3)
    assert sol.s[0] == s_c and sol.s[-1] == L


def test_rotated_clamp_small_deflection():
    """With the clamp at angle beta only P cos(beta) bends the rod."""
    L, EI, P, beta = 2.0, 10.0, 1e-3, math.radians(30)
    sol = solve_cantilever(EI, length=L, tip_load=P, clamp_angle=beta)
    x, y = sol.tip
    # displacement perpendicular to the clamp direction
    normal = -x * math.sin(beta) + y * math.cos(beta)
    assert -normal == pytest.approx(P * math.cos(beta) * L**3 / (3 * EI),
                                    rel=1e-3)


def test_hanging_rod_stays_straight():
    """A rod clamped pointing straight down is not bent by gravity."""
    sol = solve_cantilever(5.0, 0.05, length=2.0, tip_load=0.5,
                           clamp_angle=-math.pi / 2)
    assert np.allclose(sol.theta, -math.pi / 2, atol=1e-8)
    assert np.allclose(sol.moment, 0.0, atol=1e-8)
    assert sol.tip == pytest.approx((0.0, -2.0), abs=1e-8)


# ---------------------------------------------------------------------------
# Large deflection: exact tip-loaded cantilever
# ---------------------------------------------------------------------------
def _exact_tip_load(theta0):
    """Exact elastica of a horizontal cantilever with a vertical tip load.

    For tip angle ``-theta0`` the first integral of
    ``EI theta'' = -P cos(theta)`` gives (Bisshopp & Drucker 1945)

    * ``alpha = P L^2 / EI = I1^2 / 2``,
    * ``delta / L = I2 / I1``  (vertical tip deflection),
    * ``a / L = 2 sqrt(sin theta0) / I1``  (horizontal tip position),

    with ``I1 = int_0^theta0 dphi / sqrt(sin theta0 - sin phi)`` and ``I2``
    the same integral weighted by ``sin phi``.  The endpoint singularity is
    handled by QUADPACK's algebraic weight after substituting
    ``u = theta0 - phi``.
    """
    def integral(weight):
        def f(u):
            if u == 0.0:                  # limit u -> 0
                return weight(theta0) / math.sqrt(math.cos(theta0))
            return (weight(theta0 - u) * math.sqrt(u)
                    / math.sqrt(math.sin(theta0) - math.sin(theta0 - u)))
        return quad(f, 0.0, theta0, weight="alg", wvar=(-0.5, 0.0),
                    epsabs=1e-13, epsrel=1e-12)[0]

    I1 = integral(lambda phi: 1.0)
    I2 = integral(math.sin)
    return I1**2 / 2, I2 / I1, 2 * math.sqrt(math.sin(theta0)) / I1


@pytest.mark.parametrize("theta0_deg", [20.0, 45.0, 70.0, 85.0])
def test_large_deflection_tip_load_exact(theta0_deg):
    L, EI = 2.0, 8.0
    alpha, delta, a = _exact_tip_load(math.radians(theta0_deg))
    sol = solve_cantilever(EI, length=L, tip_load=alpha * EI / L**2,
                           tol=1e-8)
    assert sol.tip_angle == pytest.approx(-math.radians(theta0_deg),
                                          abs=1e-5)
    assert -sol.tip[1] / L == pytest.approx(delta, abs=1e-5)
    assert sol.tip[0] / L == pytest.approx(a, abs=1e-5)


def test_bisshopp_drucker_table_value():
    """Classic tabulated point: alpha = 1 gives delta/L = 0.3017."""
    sol = solve_cantilever(1.0, length=1.0, tip_load=1.0, tol=1e-8)
    assert -sol.tip[1] == pytest.approx(0.3017, abs=1e-4)
    assert sol.tip[0] == pytest.approx(0.9436, abs=2e-4)


# ---------------------------------------------------------------------------
# Global equilibrium and load sequences (rod-like parameters)
# ---------------------------------------------------------------------------
def _rodlike():
    EI = lambda s: 20.0 * np.exp(-1.6 * s)          # noqa: E731  [N m^2]
    mu = lambda s: 0.045 - 0.012 * s                # noqa: E731  [kg/m]
    return EI, mu, 2.743, 0.25


def test_clamp_moment_balances_loads():
    """Clamp moment equals the moment of tip load + self-weight about it."""
    EI, mu, L, s_c = _rodlike()
    P = 0.2 * GRAVITY                     # heavy: tip hangs nearly vertical
    sol = solve_cantilever(EI, mu, length=L, s_clamp=s_c, tip_load=P,
                           tol=1e-8)
    assert sol.tip_angle < -math.radians(70)
    s = np.linspace(s_c, L, 4001)
    x = sol.at(s)[0]
    self_weight = np.trapezoid(mu(s) * GRAVITY * x, s)
    assert sol.moment[0] == pytest.approx(-(P * sol.tip[0] + self_weight),
                                          rel=1e-5)


def test_rod_is_inextensible():
    """Arc length of the solved curve equals the free length."""
    EI, mu, L, s_c = _rodlike()
    sol = solve_cantilever(EI, mu, length=L, s_clamp=s_c,
                           tip_load=0.08 * GRAVITY, tol=1e-8)
    s = np.linspace(s_c, L, 20001)
    x, y = sol.at(s)[:2]
    assert np.hypot(np.diff(x), np.diff(y)).sum() == pytest.approx(
        sol.free_length, rel=1e-6)


def test_load_sequence_matches_cold_solves():
    """Warm-started sequence agrees with independent solves and bends more
    with each load step."""
    EI, mu, L, s_c = _rodlike()
    loads = np.arange(0, 8) * 0.015 * GRAVITY
    seq = solve_load_sequence(EI, mu, tip_loads=loads, length=L,
                              s_clamp=s_c, tol=1e-8)
    tips = np.array([sol.tip[1] for sol in seq])
    assert np.all(np.diff(tips) < 0)
    cold = solve_cantilever(EI, mu, length=L, s_clamp=s_c,
                            tip_load=loads[-1], tol=1e-8)
    assert seq[-1].tip == pytest.approx(cold.tip, abs=1e-6)
