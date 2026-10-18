# -*- coding: utf-8 -*-
"""Verification tests for the tip-mass frequency model.

:mod:`flycastsim.rod.vibration` is checked against

* the exact modes of a uniform clamped-free beam
  (:math:`\\beta_n L = 1.8751, 4.6941`),
* the exact frequency equation of a uniform cantilever with a tip mass,
* the massless-rod limit :math:`f = \\sqrt{k / m_t} / 2\\pi`, with the tip
  stiffness :math:`k` of a tapered rod from the unit-load method, and
* the expected :math:`O(h^4)` convergence of the Hermite elements.
"""
import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import brentq

from flycastsim.rod import frequency_vs_tip_mass, natural_frequencies

BETA_1, BETA_2 = 1.8751040687, 4.6940911330


def _uniform_frequency(beta_L, EI, mu, L):
    return beta_L**2 / (2 * math.pi * L**2) * math.sqrt(EI / mu)


def test_uniform_cantilever_modes():
    EI, mu, L = 12.0, 0.04, 2.5
    f = natural_frequencies(EI, mu, length=L, n_modes=2)
    assert f[0] == pytest.approx(_uniform_frequency(BETA_1, EI, mu, L),
                                 rel=1e-8)
    assert f[1] == pytest.approx(_uniform_frequency(BETA_2, EI, mu, L),
                                 rel=1e-7)


def _beta_with_tip_mass(ratio):
    """Root of the clamped-free beam frequency equation with tip mass
    ``ratio = m_t / (mu L)``:

    ``1 + cos b cosh b + ratio * b (cos b sinh b - sin b cosh b) = 0``.
    """
    def g(b):
        return (1 + math.cos(b) * math.cosh(b)
                + ratio * b * (math.cos(b) * math.sinh(b)
                               - math.sin(b) * math.cosh(b)))
    return brentq(g, 0.1, BETA_1 + 1e-9)


@pytest.mark.parametrize("ratio", [0.1, 0.5, 2.0, 10.0])
def test_uniform_cantilever_with_tip_mass(ratio):
    EI, mu, L = 12.0, 0.04, 2.5
    f = natural_frequencies(EI, mu, length=L, tip_mass=ratio * mu * L)[0]
    expected = _uniform_frequency(_beta_with_tip_mass(ratio), EI, mu, L)
    assert f == pytest.approx(expected, rel=1e-8)


def test_massless_tapered_rod_tip_mass_limit():
    """Light rod, heavy tip mass, clamp offset: a spring--mass system with
    the linear static tip stiffness ``k = 1 / int (L - s)^2 / EI ds``."""
    L, s_c, m_t = 2.74, 0.25, 0.02
    EI = lambda s: 40.0 * np.exp(-1.1 * s)          # noqa: E731
    k = 1.0 / quad(lambda s: (L - s) ** 2 / EI(s), s_c, L)[0]
    f = natural_frequencies(EI, 1e-9, length=L, s_clamp=s_c,
                            tip_mass=m_t)[0]
    assert f == pytest.approx(math.sqrt(k / m_t) / (2 * math.pi), rel=1e-6)


def test_fourth_order_convergence():
    """Halving h cuts the frequency error by ~16 (uniform rod + tip mass,
    against the exact root)."""
    EI, mu, L, ratio = 12.0, 0.04, 2.5, 0.5
    exact = _uniform_frequency(_beta_with_tip_mass(ratio), EI, mu, L)
    err = [abs(natural_frequencies(EI, mu, length=L, tip_mass=ratio * mu * L,
                                   n_elements=n)[0] - exact)
           for n in (2, 4, 8)]
    rates = np.log2(np.array(err[:-1]) / np.array(err[1:]))
    assert np.all(rates > 3.7), rates


def test_breakpoints_resolve_mass_jump():
    """A density jump on a node is integrated exactly; off-node it is not."""
    L, jump = 2.0, 0.73
    mu = lambda s: np.where(s < jump, 0.06, 0.02)   # noqa: E731
    ref = natural_frequencies(5.0, mu, length=L, n_elements=120,
                              breakpoints=[jump])[0]
    with_bp = natural_frequencies(5.0, mu, length=L, n_elements=20,
                                  breakpoints=[jump])[0]
    without = natural_frequencies(5.0, mu, length=L, n_elements=20)[0]
    assert abs(with_bp - ref) < 0.1 * abs(without - ref)


def test_frequency_vs_tip_mass_sweep():
    """Sweep equals individual solves; 1/f^2 is near-linear in tip mass."""
    L, s_c = 2.74, 0.25
    EI = lambda s: 40.0 * np.exp(-1.6 * s)          # noqa: E731
    mu = lambda s: 0.05 - 0.012 * s                 # noqa: E731
    masses = np.array([0, 2, 4, 8, 16, 28]) * 1e-3
    f = frequency_vs_tip_mass(EI, mu, masses, length=L, s_clamp=s_c)
    single = [natural_frequencies(EI, mu, length=L, s_clamp=s_c,
                                  tip_mass=m)[0] for m in masses]
    assert f == pytest.approx(single, rel=1e-12)
    assert np.all(np.diff(f) < 0)
    inv_f2 = 1 / f**2
    fit = np.polyfit(masses, inv_f2, 1)
    assert np.max(np.abs(np.polyval(fit, masses) - inv_f2)) < 0.02 * inv_f2[-1]
