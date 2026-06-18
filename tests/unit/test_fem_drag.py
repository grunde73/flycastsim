# -*- coding: utf-8 -*-
"""Tests for the Reynolds air-drag law and Kelvin-Voigt material damping."""
import numpy as np

from flycastsim.fem import reynolds_drag, simulate_cast
from flycastsim.fem.cast import fly_cast_domain
from flycastsim.fem.drag import RHO_AIR, MU_AIR
from flycastsim.fem import state


def _fields(n, u_s, u_n):
    """Build a Fields with uniform tangential/normal velocities."""
    x = np.zeros(n * state.NFIELDS)
    fl = state.Fields.from_vector(x)
    fl.u_s[:] = u_s
    fl.u_n[:] = u_n
    return fl


def test_drag_zero_at_zero_velocity():
    """No motion => no drag."""
    dom = fly_cast_domain(n_nodes=21, line_diameter=1.2e-3)
    f_drag = reynolds_drag(dom)
    f_s, f_n = f_drag(_fields(dom.n_nodes, 0.0, 0.0))
    assert np.allclose(f_s, 0.0, atol=1e-9)
    assert np.allclose(f_n, 0.0, atol=1e-9)


def test_drag_zero_for_zero_diameter():
    """A zero-diameter line carries no drag and does not blow up."""
    dom = fly_cast_domain(n_nodes=21, line_diameter=0.0)
    f_drag = reynolds_drag(dom)
    f_s, f_n = f_drag(_fields(dom.n_nodes, 3.0, 5.0))
    assert np.all(np.isfinite(f_s)) and np.all(np.isfinite(f_n))
    assert np.allclose(f_s, 0.0) and np.allclose(f_n, 0.0)


def test_drag_shares_sign_with_velocity():
    """Each drag component has the same sign as its velocity (opposes motion
    once moved to the acceleration side of the momentum balance)."""
    dom = fly_cast_domain(n_nodes=21, line_diameter=1.2e-3)
    f_drag = reynolds_drag(dom)
    for u in (-4.0, -1.0, 2.0, 6.0):
        f_s, f_n = f_drag(_fields(dom.n_nodes, u, u))
        assert np.all(np.sign(f_s) == np.sign(u))
        assert np.all(np.sign(f_n) == np.sign(u))


def test_drag_monotonic_in_speed():
    """Faster motion => larger drag magnitude (normal component)."""
    dom = fly_cast_domain(n_nodes=11, line_diameter=1.2e-3)
    f_drag = reynolds_drag(dom)
    mags = []
    for u in (0.5, 2.0, 8.0, 20.0):
        _, f_n = f_drag(_fields(dom.n_nodes, 0.0, u))
        mags.append(abs(f_n[0]))
    assert np.all(np.diff(mags) > 0.0)


def test_drag_normal_exceeds_tangential():
    """For equal speeds the normal drag dwarfs the tangential (slender body)."""
    dom = fly_cast_domain(n_nodes=11, line_diameter=1.2e-3)
    f_drag = reynolds_drag(dom)
    f_s, f_n = f_drag(_fields(dom.n_nodes, 10.0, 10.0))
    assert abs(f_n[0]) > 10.0 * abs(f_s[0])


def test_reynolds_form_term_matches_formula():
    """The quadratic form-drag term reproduces the closed-form value at a
    speed where the friction term is comparatively small."""
    d = 1.2e-3
    dom = fly_cast_domain(n_nodes=5, line_diameter=d)
    f_drag = reynolds_drag(dom)
    u = 15.0
    _, f_n = f_drag(_fields(dom.n_nodes, 0.0, u))
    form = 1.0 * d * RHO_AIR / 2.0 * u * u
    fric = 10.0 * (RHO_AIR * d / MU_AIR) ** (-0.75) * d * 0.5 * RHO_AIR \
        * u ** (1 - 0.75) * u
    assert np.isclose(f_n[0], form + fric, rtol=1e-6)


def _tip_kinetic_proxy(**kw):
    t, X, Y, s = simulate_cast(n_nodes=41, dt=2e-3, t_end=0.6, **kw)
    vx = np.gradient(X[:, -1], t)
    vy = np.gradient(Y[:, -1], t)
    return float(np.max(np.hypot(vx, vy)))


def test_air_drag_is_dissipative():
    """Air drag reduces the peak tip speed relative to no drag."""
    fast = _tip_kinetic_proxy(air_drag=False)
    slow = _tip_kinetic_proxy(air_drag=True)
    assert slow < fast


def test_material_damping_is_dissipative():
    """Kelvin-Voigt damping further reduces the peak tip speed."""
    base = _tip_kinetic_proxy(air_drag=True, eta=0.0)
    damped = _tip_kinetic_proxy(air_drag=True, eta=3.0e-3)
    assert damped < base


def test_drag_off_reproduces_baseline():
    """With drag off and eta zero the result is bit-for-bit the legacy run."""
    a = simulate_cast(n_nodes=41, dt=2e-3, t_end=0.5)
    b = simulate_cast(n_nodes=41, dt=2e-3, t_end=0.5, air_drag=False, eta=0.0)
    assert np.allclose(a[1], b[1]) and np.allclose(a[2], b[2])
