# -*- coding: utf-8 -*-
"""Tests for the rod stiffness / mass profile fit.

Covers the building blocks of :mod:`flycastsim.rod.profile_fit` (linear
section densities, the section mass model, the monotone log-EI spline and
curve projection), the fixed-mesh elastica solver used by the fit, and an
end-to-end recovery of a known synthetic rod from noise-free bend frames and
tip-mass frequencies with an unknown load step.
"""
import math

import numpy as np
import pytest
from scipy.integrate import quad

from flycastsim.rod import (RodSection, frequency_vs_tip_mass,
                            solve_cantilever, solve_cantilever_fd,
                            solve_load_sequence)
from flycastsim.rod.profile_fit import (BendFrame, FrequencyData,
                                        ImageTransform, MonotoneLogEI,
                                        ProfileFitProblem,
                                        SectionMassModel, fit_profile,
                                        linear_density, project_onto_curve)

L, S_C = 2.743, 0.25


# ---------------------------------------------------------------------------
# Mass model
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("xc_frac", [1 / 3, 0.4, 0.5, 0.6, 2 / 3])
def test_linear_density_moments(xc_frac):
    m, l = 0.017, 0.72
    a, b = linear_density(m, l, xc_frac * l)
    assert quad(lambda x: a + b * x, 0, l)[0] == pytest.approx(m)
    assert quad(lambda x: (a + b * x) * x, 0, l)[0] / m == pytest.approx(
        xc_frac * l)
    assert min(a, a + b * l) >= -1e-12


def _three_sections(**kwargs):
    return SectionMassModel(lengths=[0.95, 0.95, 0.95],
                            ferrule_overlap=(2.85 - L) / 2,
                            masses=[0.040, 0.016, 0.006],
                            mass_centers=[0.42, 0.44, 0.43], **kwargs)


def test_section_mass_model_totals_and_overlap():
    model = _three_sections()
    mu = model.density()
    pts = np.concatenate([[0.0, L], model.breakpoints])
    total = sum(quad(mu, a, b)[0] for a, b in
                zip(np.sort(pts)[:-1], np.sort(pts)[1:]))
    assert total == pytest.approx(sum(model.masses), rel=1e-9)
    assert model.starts == pytest.approx([0.0, 0.8965, 1.793])
    # section 2 alone: its density integrates to its mass
    a, b = model.starts[1], model.starts[1] + 0.95
    m2 = quad(lambda s: linear_density(0.016, 0.95, 0.44)[0]
              + linear_density(0.016, 0.95, 0.44)[1] * (s - a), a, b)[0]
    assert m2 == pytest.approx(0.016)


def test_section_mass_model_from_sections_and_reel_seat():
    secs = [RodSection(0.0675, 0.727, 0.173), RodSection(0.0162, 0.725, 0.319),
            RodSection(0.0092, 0.725, 0.316), RodSection(0.0039, 0.725, 0.346)]
    model = SectionMassModel.from_sections(secs, 2.724, has_reel_seat=True)
    assert model.ferrule_overlap == pytest.approx((2.902 - 2.724) / 3)
    mu = model.density()
    pts = np.sort(np.concatenate([[0.0, 2.724], model.breakpoints]))
    total = sum(quad(mu, a, b)[0] for a, b in zip(pts[:-1], pts[1:]))
    assert total == pytest.approx(sum(s.mass for s in secs), rel=1e-9)
    assert mu(np.array([0.05]))[0] > mu(np.array([0.3]))[0]   # grip mass
    assert 0.16 in model.breakpoints


def test_mass_prior_residuals():
    model = _three_sections(mass_sigma=1e-3, mass_center_sigma=1e-2)
    p = model.initial_params().copy()
    assert np.allclose(model.prior_residuals(p), 0)
    p[2] += 2e-3
    p[5] -= 1e-2
    r = model.prior_residuals(p)
    assert r[1] == pytest.approx(2.0) and r[5] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# Stiffness model
# ---------------------------------------------------------------------------
def test_monotone_log_ei_is_non_increasing():
    model = MonotoneLogEI(S_C, L, n_coef=8)
    rng = np.random.default_rng(0)
    s = np.linspace(0, L + 0.1, 2000)
    for _ in range(20):
        p = np.concatenate([[rng.normal(3, 1)], rng.normal(-1, 1.5, 7)])
        EI = model.stiffness(p)(s)
        assert np.all(np.diff(EI) <= 1e-12 * EI[:-1])
        assert np.all(EI[s <= S_C] == EI[0])            # flat behind clamp


def test_monotone_log_ei_exponential_taper_is_exact():
    model = MonotoneLogEI(S_C, L, n_coef=7)
    EI = model.stiffness(model.params_from_endpoints(40.0, 2.0))
    s = np.linspace(S_C, L, 50)
    expected = 40.0 * (2.0 / 40.0) ** ((s - S_C) / (L - S_C))
    assert EI(s) == pytest.approx(expected, rel=1e-10)
    assert np.allclose(model.smoothness_residuals(
        model.params_from_endpoints(40.0, 2.0)), 0)


# ---------------------------------------------------------------------------
# Fixed-mesh elastica and projection
# ---------------------------------------------------------------------------
def _rod():
    EI = lambda s: 3 + 22 * np.exp(-1.8 * (np.clip(s, S_C, L) - S_C))  # noqa
    return EI, _three_sections().density()


@pytest.mark.parametrize("tip_mass", [0.0, 0.03, 0.12])
def test_fd_solver_matches_bvp(tip_mass):
    EI, mu = _rod()
    kw = dict(length=L, s_clamp=S_C, tip_load=tip_mass * 9.81)
    ref = solve_cantilever(EI, mu, tol=1e-9, **kw)
    fd = solve_cantilever_fd(EI, mu, **kw)
    assert fd.tip == pytest.approx(ref.tip, abs=2e-5)
    s = np.linspace(S_C, L, 37)
    assert np.allclose(fd.at(s)[:2], ref.at(s)[:2], atol=2e-5)


def test_fd_solver_second_order():
    EI, mu = _rod()
    kw = dict(length=L, s_clamp=S_C, tip_load=0.06 * 9.81)
    ref = np.array(solve_cantilever(EI, mu, tol=1e-9, **kw).tip)
    err = [np.abs(np.array(solve_cantilever_fd(EI, mu, n_segments=n,
                                               **kw).tip) - ref).max()
           for n in (25, 50, 100)]
    rates = np.log2(np.array(err[:-1]) / np.array(err[1:]))
    assert np.all(rates > 1.8), rates


def test_fd_solver_clamp_compliance():
    """A rotational spring at the clamp adds a rigid rotation c * M(s_c):
    small-deflection tip drop c P L^2 and clamp angle -c P L."""
    L_, EI, P, c = 2.0, 10.0, 1e-3, 0.05
    rigid = solve_cantilever_fd(EI, length=L_, tip_load=P)
    soft = solve_cantilever_fd(EI, length=L_, tip_load=P, clamp_compliance=c)
    assert soft.tip[1] - rigid.tip[1] == pytest.approx(-c * P * L_**2,
                                                       rel=1e-4)
    assert soft.theta[0] == pytest.approx(-c * P * L_, rel=1e-4)
    # large deflection: the clamp moment balances the loads as before
    EI_, mu = _rod()
    sol = solve_cantilever_fd(EI_, mu, length=L, s_clamp=S_C,
                              tip_load=0.1 * 9.81, clamp_compliance=0.02)
    assert sol.theta[0] == pytest.approx(0.02 * sol.moment[0], rel=1e-9)


def test_project_onto_curve_recovers_offsets():
    EI, mu = _rod()
    sol = solve_cantilever_fd(EI, mu, length=L, s_clamp=S_C,
                              tip_load=0.05 * 9.81)
    s_true = np.linspace(0.4, 2.6, 12)
    offset = np.linspace(-3e-3, 3e-3, 12)
    x, y, theta, _ = sol.at(s_true)
    pts = np.column_stack([x - offset * np.sin(theta),
                           y + offset * np.cos(theta)])
    s, d = project_onto_curve(sol, pts)
    assert s == pytest.approx(s_true, abs=1e-5)
    assert d == pytest.approx(offset, abs=1e-7)


# ---------------------------------------------------------------------------
# End-to-end synthetic recovery
# ---------------------------------------------------------------------------
def test_recovers_synthetic_rod():
    """Noise-free frames with an unknown load step plus tip-mass frequencies:
    the fit recovers the load step and EI over the free length (except right
    at the tip, where the bending moment vanishes and EI is unobservable)."""
    EI_true, mu_true = _rod()
    load_step = 0.006
    steps = np.array([0, 3, 6, 10])
    sols = solve_load_sequence(EI_true, mu_true, tip_loads=steps * load_step
                               * 9.81, length=L, s_clamp=S_C,
                               solver=solve_cantilever_fd)
    frames = []
    for k, sol in zip(steps, sols):
        s = np.linspace(S_C + 0.05, L - 0.02, 15)
        frames.append(BendFrame(points=sol.at(s)[:2].T, load_steps=k,
                                tip=np.array(sol.tip)))
    masses = np.array([0, 4, 8, 16, 28]) * 1e-3
    mass_model = _three_sections()
    freq = FrequencyData(masses, frequency_vs_tip_mass(
        EI_true, mu_true, masses, length=L, s_clamp=S_C,
        breakpoints=mass_model.breakpoints))
    ei_model = MonotoneLogEI(S_C, L, n_coef=7)
    problem = ProfileFitProblem(ei_model, mass_model, L, S_C, frames,
                                load_step=0.010, sigma_xy=5e-4,
                                frequency=freq, smoothness=0.01)
    res = fit_profile(problem, ei_params=ei_model.params_from_endpoints(15, 2))

    assert res.load_step == pytest.approx(load_step, rel=2e-3)
    s = np.linspace(S_C, L - 0.3, 30)
    assert res.EI(s) == pytest.approx(EI_true(s), rel=0.02)
    assert res.mass_params == pytest.approx(mass_model.initial_params(),
                                            rel=0.01)
    table = res.table(11)
    assert set(table) == {"s_m", "m_kg_per_m", "EI_Nm2"}
    assert math.isclose(table["s_m"][-1], L)


# ---------------------------------------------------------------------------
# Image transform
# ---------------------------------------------------------------------------
def test_image_transform_orientation_and_round_trip():
    tr = ImageTransform(clamp_px=np.array([1000.0, 200.0]), scale=1e-3)
    p = tr.initial_params()
    # left of the clamp is along the rod (+x), above it is +y
    assert tr.to_physical(p, [[900.0, 200.0]])[0] == pytest.approx([0.1, 0])
    assert tr.to_physical(p, [[1000.0, 150.0]])[0] == pytest.approx(
        [0.0, 0.05])
    p[3] = np.radians(2.0)
    pts = np.random.default_rng(0).uniform(0, 2000, (10, 2))
    assert np.allclose(tr.to_pixels(p, tr.to_physical(p, pts)), pts)


def test_recovers_rod_and_transform_from_pixels():
    """Frames given in pixels with a rolled, offset, scaled camera: the fit
    recovers the transform and the load step.  Camera roll and clamp angle
    are only separated by heavily loaded frames (tip near vertical), which
    show the gravity direction."""
    EI_true, mu_true = _rod()
    true = ImageTransform(clamp_px=np.array([2990.0, 130.0]), scale=8.8e-4,
                          roll=np.radians(0.4))
    p_true = true.initial_params()      # zero changes: the true values
    steps = np.array([0, 6, 12, 24])
    sols = solve_load_sequence(EI_true, mu_true, tip_loads=steps * 0.006
                               * 9.81, length=L, s_clamp=S_C,
                               solver=solve_cantilever_fd)
    frames = []
    for k, sol in zip(steps, sols):
        s = np.linspace(S_C + 0.08, L - 0.02, 15)
        frames.append(BendFrame(
            points=true.to_pixels(p_true, sol.at(s)[:2].T), load_steps=k,
            tip=true.to_pixels(p_true, [sol.tip])[0]))
    masses = np.array([0, 4, 8, 16, 28]) * 1e-3
    mass_model = _three_sections()
    freq = FrequencyData(masses, frequency_vs_tip_mass(
        EI_true, mu_true, masses, length=L, s_clamp=S_C,
        breakpoints=mass_model.breakpoints))
    guess = ImageTransform(clamp_px=np.array([2998.0, 126.0]), scale=8.95e-4,
                           sigma_px=0.5)
    ei_model = MonotoneLogEI(S_C, L, n_coef=7)
    problem = ProfileFitProblem(ei_model, mass_model, L, S_C, frames,
                                load_step=0.010, frequency=freq,
                                smoothness=0.01, transform=guess)
    res = fit_profile(problem, ei_params=ei_model.params_from_endpoints(15, 2))
    fit = guess.fitted(res.transform_params)
    # the clamp position along the rod trades off against the scale (both
    # mainly move the tip), so it is only good to a pixel or two
    assert fit.clamp_px == pytest.approx(true.clamp_px, abs=2.0)     # px
    assert fit.scale == pytest.approx(true.scale, rel=2e-3)
    assert fit.roll == pytest.approx(true.roll, abs=np.radians(0.05))
    assert res.load_step == pytest.approx(0.006, rel=5e-3)
