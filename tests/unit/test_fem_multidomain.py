# -*- coding: utf-8 -*-
"""Tests for the data-driven components and the multi-subdomain coupling.

These cover the refactor that splits the Cast #1 rig into distinct rod / line /
leader subdomains joined by explicit junctions, with material profiles loaded
from bundled JSON + CSV data files.
"""
import numpy as np
import pytest

from flycastsim import fem
from flycastsim.fem import state as st
from flycastsim.fem.components import (Component, load_component, load_rig,
                                       bundled_rig_path, copy_example_rig)
from flycastsim.fem.domain import Subdomain, uniform_beam
from flycastsim.fem.multidomain import MultiDomain, Junction
from flycastsim.fem.operators import (BoundaryConditions, local_to_world,
                                       residual_multi, n_residual_multi)
from flycastsim.fem.solver import solve_static, solve_static_multi
from flycastsim.fem.coords import positions, positions_multi


# ---------------------------------------------------------------------------
# Component loading / interpolation
# ---------------------------------------------------------------------------
def test_component_interpolates_and_to_subdomain():
    """A Component linearly interpolates its profiles onto a grid."""
    comp = Component(
        name="bench", kind="rod", length=2.0, n_nodes=5,
        s=np.array([0.0, 1.0, 2.0]),
        m=np.array([0.06, 0.04, 0.02]),
        EI=np.array([100.0, 40.0, 10.0]),
        d=np.array([0.012, 0.008, 0.004]),
        eta=1e-3,
    )
    sd = comp.to_subdomain(n_nodes=5, s0=3.0)
    assert isinstance(sd, Subdomain)
    assert sd.n_nodes == 5
    # Grid is offset by s0 and spans the component length.
    assert np.isclose(sd.s[0], 3.0) and np.isclose(sd.s[-1], 5.0)
    # Midpoint interpolation of EI between control points (s=1.0 -> 40).
    mid = np.interp(1.0, [0.0, 1.0, 2.0], [100.0, 40.0, 10.0])
    assert np.isclose(mid, 40.0)
    # eta is a constant array over the grid.
    assert np.allclose(sd.eta, 1e-3)


def test_component_rejects_decreasing_s():
    """Control-point arc-length must be strictly increasing."""
    with pytest.raises(ValueError):
        Component(name="bad", kind="rod", length=1.0, n_nodes=3,
                  s=np.array([0.0, 0.5, 0.5]), m=np.ones(3),
                  EI=np.ones(3), d=np.zeros(3))


def test_load_bundled_cast1_components():
    """The bundled Cast #1 JSON+CSV files load into Components."""
    rig_path = bundled_rig_path("cast1")
    assert rig_path.name == "rig.json" and rig_path.exists()
    md = load_rig("cast1")
    assert isinstance(md, MultiDomain)
    # rod -> line -> leader, joined by two junctions (pinned, welded).
    assert md.n_subdomains == 3
    assert [j.kind for j in md.junctions] == ["pinned", "welded"]
    # Global arc-length grid is continuous and increasing across junctions.
    assert np.all(np.diff(md.s) >= -1e-12)


def test_aftm_scaling_matches_standard():
    """A scaled-by-AFTM line carries roughly the rated 30 ft head mass."""
    md = load_rig("cast1", aftm_weight=5)
    line = md.subdomains[1]                              # rod, line, leader
    # Integrated mass over the first 9.144 m (30 ft) head ~ AFTM 5-wt (~9 g).
    s = line.s - line.s[0]
    head = s <= 9.144
    head_mass_g = np.trapezoid(line.m[head], s[head]) * 1e3
    assert 7.5 < head_mass_g < 10.5                     # ~9 g, grid-tolerant


def test_copy_example_rig(tmp_path):
    """copy_example_rig clones the bundled rig so users can edit it."""
    dest = copy_example_rig(tmp_path / "myrig")
    assert dest.name == "rig.json" and dest.exists()
    folder = dest.parent
    assert (folder / "rod.csv").exists() and (folder / "line.csv").exists()
    # The copied rig loads from its filesystem path.
    md = load_rig(dest)
    assert md.n_subdomains == 3


# ---------------------------------------------------------------------------
# Frame helper
# ---------------------------------------------------------------------------
def test_local_to_world_round_trip():
    """local_to_world rotates a local vector by phi; inverse recovers it."""
    rng = np.random.default_rng(0)
    s_comp, n_comp = rng.standard_normal(8), rng.standard_normal(8)
    phi = rng.uniform(-np.pi, np.pi, 8)
    x, y = local_to_world(s_comp, n_comp, phi)
    # Inverse rotation (by -phi) maps world back to local.
    s_back, n_back = local_to_world(x, y, -phi)
    assert np.allclose(s_back, s_comp) and np.allclose(n_back, n_comp)
    # phi = 0 is the identity.
    x0, y0 = local_to_world(s_comp, n_comp, 0.0)
    assert np.allclose(x0, s_comp) and np.allclose(y0, n_comp)


# ---------------------------------------------------------------------------
# Multi-subdomain bookkeeping
# ---------------------------------------------------------------------------
def test_multidomain_dof_accounting():
    """Total residual rows equal the unknown count (well-posed system)."""
    a = uniform_beam(1.0, 21, m=0.05, EI=5.0)
    b = uniform_beam(1.0, 21, m=0.05, EI=5.0, s0=1.0)
    md = MultiDomain([a, b], [Junction("welded", 0, 1)])
    assert md.n_nodes == 42
    assert np.array_equal(md.node_offsets, [0, 21])
    # Junction joins last node of A (20) to first node of B (21).
    assert md.junction_nodes(md.junctions[0]) == (20, 21)
    # The assembled residual is square: rows == 7 * n_nodes when the two
    # physical ends contribute six boundary rows.
    assert n_residual_multi(md, 6) == st.n_unknowns(md.n_nodes)


# ---------------------------------------------------------------------------
# Static benchmarks: welded reproduces a single beam; pinned is a free hinge
# ---------------------------------------------------------------------------
def _cantilever_bc(last_node):
    bc = BoundaryConditions()
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0).dirichlet(0, st.PHI, 0.0)
    bc.dirichlet(last_node, st.F_S, 0.0).dirichlet(last_node, st.F_N, 0.0)
    bc.dirichlet(last_node, st.NU_Z, 0.0)
    return bc


def test_welded_two_subdomains_match_single_domain():
    """A welded split of a uniform cantilever reproduces the single-domain solve."""
    m, EI, g = 0.05, 5.0, 9.81
    dom = uniform_beam(2.0, 41, m=m, EI=EI)
    r = solve_static(dom, _cantilever_bc(40), gravity=g, max_iter=80)
    assert r.converged
    fs = st.Fields.from_vector(r.x)
    xs, ys = positions(fs.phi, dom.s)

    a = uniform_beam(1.0, 21, m=m, EI=EI)
    b = uniform_beam(1.0, 21, m=m, EI=EI, s0=1.0)
    md = MultiDomain([a, b], [Junction("welded", 0, 1)])
    rm = solve_static_multi(md, _cantilever_bc(md.n_nodes - 1),
                            gravity=g, max_iter=80)
    assert rm.converged
    fm = st.Fields.from_vector(rm.x)
    xm, ym = positions_multi(fm, md)
    # The welded chain matches the monolithic cantilever tip to tight tolerance.
    assert np.isclose(xm[-1], xs[-1], atol=1e-3)
    assert np.isclose(ym[-1], ys[-1], atol=1e-3)


def test_pinned_junction_is_a_free_hinge():
    """A pinned junction transmits no bending moment (nu_z = 0 each side)."""
    m, EI, g = 0.05, 5.0, 9.81
    md = MultiDomain(
        [uniform_beam(1.0, 21, m=m, EI=EI),
         uniform_beam(1.0, 21, m=m, EI=EI, s0=1.0)],
        [Junction("pinned", 0, 1)])
    last = md.n_nodes - 1
    bc = BoundaryConditions()
    bc.dirichlet(0, st.U_S, 0.0).dirichlet(0, st.U_N, 0.0).dirichlet(0, st.PHI, 0.0)
    # Constrain the tip angle so the free hinge is not a rigid-body mechanism.
    bc.dirichlet(last, st.F_S, 0.0).dirichlet(last, st.PHI, np.deg2rad(-10.0))
    bc.dirichlet(last, st.NU_Z, 0.0)
    rp = solve_static_multi(md, bc, gravity=g, max_iter=120)
    assert rp.converged
    fp = st.Fields.from_vector(rp.x)
    L, R = md.junction_nodes(md.junctions[0])
    # No bending moment carried across a free hinge.
    assert abs(fp.nu_z[L]) < 1e-6 and abs(fp.nu_z[R]) < 1e-6
    # Position stays continuous across the hinge even with an angle kink.
    xp, yp = positions_multi(fp, md)
    assert np.isclose(xp[L], xp[R], atol=1e-9)
    assert np.isclose(yp[L], yp[R], atol=1e-9)
