# -*- coding: utf-8 -*-
"""Smoke tests for the simplified fly-cast demo and its plotting helpers."""
import numpy as np

from flycastsim import animate_fly_cast, plot_cast_snapshots
from flycastsim.fem import simulate_cast
from flycastsim.fem.cast import casting_stroke


def test_casting_stroke_smoothstep():
    """The stroke starts at +sweep/2, ends at -sweep/2 and holds."""
    sweep = np.deg2rad(120.0)
    theta = casting_stroke(sweep, t_stroke=0.4)
    assert np.isclose(theta(0.0), sweep / 2)
    assert np.isclose(theta(0.4), -sweep / 2)
    assert np.isclose(theta(1.0), -sweep / 2)        # held after the stroke
    # monotonic decrease through the stroke
    ts = np.linspace(0.0, 0.4, 20)
    vals = np.array([theta(t) for t in ts])
    assert np.all(np.diff(vals) <= 1e-12)


def test_simulate_cast_runs_and_moves():
    """A cast produces finite output, a fixed handle and a moving tip."""
    t, X, Y, s = simulate_cast(n_nodes=41, dt=4e-3, t_end=0.6)
    n_t = len(t)
    assert X.shape == (n_t, 41)
    assert Y.shape == (n_t, 41)
    assert s.shape == (41,)
    assert np.isfinite(X).all() and np.isfinite(Y).all()
    # Handle (node 0) is a fixed pivot at the origin.
    assert np.allclose(X[:, 0], 0.0) and np.allclose(Y[:, 0], 0.0)
    # The tip actually sweeps a meaningful distance.
    tip_travel = np.hypot(np.ptp(X[:, -1]), np.ptp(Y[:, -1]))
    assert tip_travel > 0.5


def test_no_gravity_planar_symmetry():
    """With gravity off the cast still runs and stays finite."""
    t, X, Y, s = simulate_cast(n_nodes=41, dt=4e-3, t_end=0.5, gravity=0.0)
    assert np.isfinite(X).all() and np.isfinite(Y).all()


def test_cast_figures_build():
    """The Plotly helpers build figures with the expected structure."""
    t, X, Y, s = simulate_cast(n_nodes=41, dt=4e-3, t_end=0.5)
    anim = animate_fly_cast(t, X, Y, n_frames=40)
    assert len(anim.frames) > 0
    assert len(anim.data) == 3                       # line + handle + tip
    snaps = plot_cast_snapshots(t, X, Y, n_snapshots=6)
    assert len(snaps.data) == 6 + 1                  # snapshots + handle marker
