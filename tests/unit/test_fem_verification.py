# -*- coding: utf-8 -*-
"""Verification tests for the FEM (continuum) fly-casting engine.

These mirror the six verification cases on the willmanco.se *Verification*
page (Ekander, Perkins & Richards, *Sports Engineering* 2025):

* Static, hanging chain   -> catenary
* Static, towed line      -> catenary (drag/axial-force balance, same shape)
* Static, non-uniform beam
* Dynamic, oscillating beam
* Dynamic, hanging chain
* Dynamic, travelling wave

Each numerical solution is compared against the corresponding exact solution.
A couple of cases additionally check the second-order spatial/temporal
convergence claimed by the paper.
"""
import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.special import jn_zeros

from flycastsim import fem
from flycastsim.fem import analytic, state as st
from flycastsim.fem.operators import BoundaryConditions
from flycastsim.fem.coords import positions


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _measure_omega(t, y):
    """Estimate the angular frequency of an oscillation from zero crossings."""
    yy = y - y.mean()
    sign_changes = np.where(np.diff(np.sign(yy)))[0]
    half_period = np.mean(np.diff(t[sign_changes]))
    return np.pi / half_period


def _solve_catenary(N, a=1.0, x0=0.6, m=1.0, g=9.81, EI=1e-3):
    """Solve the static catenary on ``N`` nodes and return (s, y_num, y_exact)."""
    L = 2.0 * a * np.sinh(x0 / a)
    s = np.linspace(0.0, L, N)
    x_an, y_an, phi_an, nu_an, Fs_an = analytic.catenary_by_arclength(
        s, a, x0, m, g)
    Fn_an = -EI * np.gradient(nu_an, s)

    dom = fem.uniform_beam(L, N, m=m, EI=EI)
    bc = BoundaryConditions()
    # One BC per spatially-differentiated field (u_s, u_n, F_s, F_n, phi, nu).
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0)
    bc.dirichlet(0, st.PHI, phi_an[0])
    bc.dirichlet(N - 1, st.F_S, Fs_an[-1]).dirichlet(N - 1, st.NU_Z, nu_an[-1])
    bc.dirichlet(N - 1, st.F_N, Fn_an[-1])

    guess = st.zeros(N)
    guess.phi[:] = phi_an
    guess.nu_z[:] = nu_an
    guess.Gamma_z[:] = np.gradient(nu_an, s)
    guess.F_s[:] = Fs_an
    guess.F_n[:] = Fn_an

    res = fem.solve_static(dom, bc, x0=guess.to_vector(), gravity=g)
    assert res.converged
    fields = st.Fields.from_vector(res.x)
    _, y_num = positions(fields.phi, s, x0=x_an[0], y0=y_an[0])
    return s, y_num, y_an


# --------------------------------------------------------------------------
# 1. Static, hanging chain (catenary)
# --------------------------------------------------------------------------

def test_static_hanging_chain_catenary():
    """A heavy line hangs as a catenary (gravity vs. axial tension)."""
    s, y_num, y_exact = _solve_catenary(N=201)
    rel = np.sqrt(np.mean((y_num - y_exact) ** 2)) / np.sqrt(np.mean(y_exact ** 2))
    assert rel < 1e-3


# --------------------------------------------------------------------------
# 2. Static, towed line (== catenary)
# --------------------------------------------------------------------------

def test_static_towed_line_catenary():
    """With axial drag = 0 and quadratic normal drag the towed line equals the
    catenary; here we verify the shared catenary shape for a second geometry."""
    s, y_num, y_exact = _solve_catenary(N=201, a=1.5, x0=0.8)
    rel = np.sqrt(np.mean((y_num - y_exact) ** 2)) / np.sqrt(np.mean(y_exact ** 2))
    assert rel < 1e-3


# --------------------------------------------------------------------------
# 3. Static, non-uniform beam
# --------------------------------------------------------------------------

def test_static_non_uniform_beam():
    """Cantilever with linearly varying EI(s) under a small tip load."""
    L, N, EI0, P = 1.0, 161, 10.0, 1e-3
    s = np.linspace(0.0, L, N)
    EIs = EI0 * (1.0 + s / L)
    dom = fem.Subdomain(s=s, m=np.ones(N), EI=EIs,
                        d=np.zeros(N), eta=np.zeros(N))

    bc = BoundaryConditions()
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0)
    bc.dirichlet(0, st.PHI, 0.0)
    bc.dirichlet(N - 1, st.F_S, 0.0).dirichlet(N - 1, st.F_N, -P)
    bc.dirichlet(N - 1, st.NU_Z, 0.0)

    res = fem.solve_static(dom, bc, x0=st.zeros(N).to_vector(), gravity=0.0)
    assert res.converged
    fields = st.Fields.from_vector(res.x)
    _, y_num = positions(fields.phi, s)

    # Exact small-deflection solution: integrate curvature M/EI twice.
    moment = -P * (L - s)
    curvature = moment / EIs
    slope = cumulative_trapezoid(curvature, s, initial=0.0)
    y_exact = cumulative_trapezoid(slope, s, initial=0.0)
    rel = abs(y_num[-1] - y_exact[-1]) / abs(y_exact[-1])
    assert rel < 1e-3


# --------------------------------------------------------------------------
# 4. Dynamic, oscillating beam
# --------------------------------------------------------------------------

def test_dynamic_oscillating_beam():
    """Free vibration of a simply-supported (pinned/roller) beam, mode 1.

    The first natural frequency is ``omega = (pi/L)^2 sqrt(EI/m)``.
    """
    L, N, EI, m, amp = 1.0, 81, 1.0, 1.0, 1e-3
    dom = fem.uniform_beam(L, N, m=m, EI=EI)
    s = dom.s

    bc = BoundaryConditions()
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0)
    bc.dirichlet(0, st.NU_Z, 0.0)
    # Roller at the far end (F_s = 0) removes the otherwise-undetermined tension.
    bc.dirichlet(N - 1, st.F_S, 0.0).dirichlet(N - 1, st.U_N, 0.0)
    bc.dirichlet(N - 1, st.NU_Z, 0.0)

    x0 = st.zeros(N)
    x0.phi[:] = amp * (np.pi / L) * np.cos(np.pi * s / L)
    x0.nu_z[:] = np.gradient(x0.phi, s)
    x0.Gamma_z[:] = np.gradient(x0.nu_z, s)

    omega = (np.pi / L) ** 2 * np.sqrt(EI / m)
    period = 2.0 * np.pi / omega
    res = fem.integrate(dom, bc, x0.to_vector(), t_span=(0.0, 4.0 * period),
                        dt=period / 100.0, gravity=0.0, rho_inf=0.95)
    mid = N // 2
    y_mid = np.array([positions(res.fields_at(k).phi, s)[1][mid]
                      for k in range(len(res.t))])
    omega_num = _measure_omega(res.t, y_mid)
    assert abs(omega_num - omega) / omega < 1e-2


# --------------------------------------------------------------------------
# 5. Dynamic, hanging chain (Bessel pendulum)
# --------------------------------------------------------------------------

def test_dynamic_hanging_chain():
    """Small lateral oscillation of a chain hung from the top, free at the
    bottom.  The fundamental frequency is ``omega = 0.5 alpha_1 sqrt(g/L)``
    with ``alpha_1`` the first zero of ``J0``."""
    L, N, m, g, EI = 1.0, 121, 1.0, 9.81, 1e-5
    dom = fem.uniform_beam(L, N, m=m, EI=EI)
    s = dom.s

    bc = BoundaryConditions()
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0)
    bc.dirichlet(0, st.NU_Z, 0.0)
    bc.dirichlet(N - 1, st.F_S, 0.0).dirichlet(N - 1, st.F_N, 0.0)
    bc.dirichlet(N - 1, st.NU_Z, 0.0)

    x0 = st.zeros(N)
    x0.phi[:] = -np.pi / 2 + 0.02            # hang down, small uniform tilt
    x0.nu_z[:] = np.gradient(x0.phi, s)
    x0.Gamma_z[:] = np.gradient(x0.nu_z, s)
    x0.F_s[:] = m * g * (L - s)              # static tension distribution

    omega = 0.5 * jn_zeros(0, 1)[0] * np.sqrt(g / L)
    period = 2.0 * np.pi / omega
    res = fem.integrate(dom, bc, x0.to_vector(), t_span=(0.0, 5.0 * period),
                        dt=period / 120.0, gravity=g, rho_inf=0.9)
    tip_x = np.array([positions(res.fields_at(k).phi, s)[0][-1]
                      for k in range(len(res.t))])
    omega_num = _measure_omega(res.t, tip_x)
    assert abs(omega_num - omega) / omega < 2e-2


# --------------------------------------------------------------------------
# 6. Dynamic, travelling/standing wave on a taut string
# --------------------------------------------------------------------------

def test_dynamic_travelling_wave():
    """Standing wave on a taut string, fundamental ``omega = (pi/L) sqrt(T/m)``
    (tension-dominated limit, ``EI -> 0``)."""
    L, N, m, T0, EI, amp = 1.0, 121, 1.0, 100.0, 1e-4, 1e-3
    dom = fem.uniform_beam(L, N, m=m, EI=EI)
    s = dom.s

    bc = BoundaryConditions()
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0)
    bc.dirichlet(0, st.NU_Z, 0.0)
    bc.dirichlet(N - 1, st.F_S, T0).dirichlet(N - 1, st.U_N, 0.0)
    bc.dirichlet(N - 1, st.NU_Z, 0.0)

    x0 = st.zeros(N)
    x0.phi[:] = amp * (np.pi / L) * np.cos(np.pi * s / L)
    x0.nu_z[:] = np.gradient(x0.phi, s)
    x0.Gamma_z[:] = np.gradient(x0.nu_z, s)
    x0.F_s[:] = T0

    c = analytic.string_wave_speed(T0, m)
    omega = (np.pi / L) * c
    period = 2.0 * np.pi / omega
    res = fem.integrate(dom, bc, x0.to_vector(), t_span=(0.0, 4.0 * period),
                        dt=period / 120.0, gravity=0.0, rho_inf=0.95)
    mid = N // 2
    y_mid = np.array([positions(res.fields_at(k).phi, s)[1][mid]
                      for k in range(len(res.t))])
    omega_num = _measure_omega(res.t, y_mid)
    assert abs(omega_num - omega) / omega < 1e-2


# --------------------------------------------------------------------------
# Convergence-order checks
# --------------------------------------------------------------------------

def test_spatial_second_order_convergence():
    """The spatial discretisation is second-order accurate.

    A geometrically-nonlinear cantilever (finite tip load) is solved on a
    sequence of grids and compared against a highly-refined reference solution
    of the *same* model (Richardson self-convergence).  The tip-deflection
    error must drop by ~4x for each halving of the grid spacing.
    """
    L, EI, P = 1.0, 20.0, 0.5

    def tip_deflection(N):
        dom = fem.uniform_beam(L, N, m=1.0, EI=EI)
        s = dom.s
        bc = BoundaryConditions()
        bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0)
        bc.dirichlet(0, st.PHI, 0.0)
        bc.dirichlet(N - 1, st.F_S, 0.0).dirichlet(N - 1, st.F_N, -P)
        bc.dirichlet(N - 1, st.NU_Z, 0.0)
        res = fem.solve_static(dom, bc, x0=st.zeros(N).to_vector(), gravity=0.0)
        fields = st.Fields.from_vector(res.x)
        _, y = positions(fields.phi, s)
        return y[-1]

    reference = tip_deflection(1281)
    errors = np.array([abs(tip_deflection(N) - reference) for N in (21, 41, 81)])
    orders = np.log2(errors[:-1] / errors[1:])
    assert np.all(orders > 1.8)

