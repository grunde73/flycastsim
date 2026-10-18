# -*- coding: utf-8 -*-
"""Tests for the solver speed-ups: cached material terms and Jacobian reuse.

Both must leave results unchanged: the cached terms equal the directly
computed ones (and follow changes of the material), and modified Newton
(``integrate(reuse_jacobian=True)``) converges to the same solution as a
fresh Jacobian every iteration, with fewer Jacobian evaluations.
"""
import numpy as np
import pytest

from flycastsim.fem import state as st
from flycastsim.fem.cast import casting_stroke, cast_bc, fly_cast_domain
from flycastsim.fem.domain import uniform_beam
from flycastsim.fem.genalpha import integrate
from flycastsim.fem import solver


def test_material_terms_cached_and_refreshed():
    dom = uniform_beam(2.0, 11, m=0.05, EI=5.0)
    dEI, ds, m_m = dom.material_terms()
    assert dom.material_terms()[0] is dEI            # cached
    assert ds == pytest.approx(np.diff(dom.s))
    assert m_m == pytest.approx(np.full(10, 0.05))
    dom.EI = np.linspace(10.0, 1.0, 11)              # reassigned
    assert dom.dEI_ds() == pytest.approx(np.gradient(dom.EI, dom.s))
    dom.EI *= 2.0                                     # edited in place
    assert dom.dEI_ds() == pytest.approx(np.gradient(dom.EI, dom.s))
    dom.m[:] = 0.02
    assert dom.material_terms()[2] == pytest.approx(np.full(10, 0.02))


def _cast_run(reuse):
    n = 31
    dom = fly_cast_domain(3.0, n)
    theta = casting_stroke(1.2, 0.3)
    x0 = st.zeros(n)
    x0.phi[:] = theta(0.0)
    return integrate(dom, cast_bc(theta, n), x0.to_vector(),
                     t_span=(0.0, 0.4), dt=2e-3, reuse_jacobian=reuse)


def test_jacobian_reuse_same_solution_fewer_jacobians(monkeypatch):
    calls = {"n": 0}
    original = solver._JacobianColouring.jacobian

    def counting(self, *args, **kwargs):
        calls["n"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(solver._JacobianColouring, "jacobian", counting)
    fresh = _cast_run(False)
    n_fresh = calls["n"]
    calls["n"] = 0
    reused = _cast_run(True)
    n_reused = calls["n"]
    assert np.max(np.abs(reused.X - fresh.X)) < 1e-7
    assert n_reused < n_fresh / 3
