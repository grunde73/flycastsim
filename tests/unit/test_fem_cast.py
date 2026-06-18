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


# ---------------------------------------------------------------------------
# Cast #1 of "The Rod & The Cast"
# ---------------------------------------------------------------------------

from flycastsim import plot_chord_comparison, load_cast1_frames
from flycastsim.fem import simulate_cast1, chord_length
from flycastsim.fem import _cast1_data


def test_cast1_data_events_ordered():
    """The reference event times are strictly increasing and RSP is t=0."""
    order = ["MAV", "MCL", "MAV/2", "RSP", "MCF"]
    ts = [_cast1_data.EVENTS[k]["t"] for k in order]
    assert all(a < b for a, b in zip(ts, ts[1:]))
    assert _cast1_data.EVENTS["RSP"]["t"] == 0.0


def test_simulate_cast1_runs_finite():
    """Cast #1 simulation is finite, fixed-handle and time-referenced to RSP."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=51, line_out=2.5)
    n_t = len(t)
    assert X.shape == (n_t, 51) and Y.shape == (n_t, 51)
    assert np.isfinite(X).all() and np.isfinite(Y).all()
    assert np.isfinite(chord).all() and chord.shape == (n_t,)
    # Handle (node 0) is a fixed pivot at the origin.
    assert np.allclose(X[:, 0], 0.0) and np.allclose(Y[:, 0], 0.0)
    # Time window is relative to RSP (covers t = 0).
    assert t[0] < 0.0 < t[-1]
    # The rod-tip node sits at (or before) the end of the rod region.
    assert 0 < rod_tip < 51


def test_simulate_cast1_chord_shape():
    """Chord shows the MCL dip then recovers toward RSP (the stop sequence)."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=51, line_out=2.5)
    chord_mcl = np.interp(_cast1_data.EVENTS["MCL"]["t"], t, chord)
    chord_rsp = np.interp(0.0, t, chord)
    # Chord recovers from the minimum-chord event toward rod-straight.
    assert chord_rsp > chord_mcl
    # Chord never exceeds the rod length.
    assert chord.max() <= _cast1_data.CAST1_ROD_LENGTH + 1e-6 \
        if hasattr(_cast1_data, "CAST1_ROD_LENGTH") \
        else chord.max() <= _cast1_data.RIG["rod_length_m"] + 1e-6


def test_chord_length_helper():
    """chord_length matches a direct handle-to-tip distance computation."""
    X = np.array([[0.0, 1.0, 2.0], [0.0, 0.0, 3.0]])
    Y = np.array([[0.0, 0.0, 0.0], [0.0, 4.0, 0.0]])
    got = chord_length(X, Y, rod_tip_index=1)
    assert np.allclose(got, [1.0, 4.0])


def test_cast1_comparison_and_frames():
    """The comparison figure builds and the event frames load."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=51)
    fig = plot_chord_comparison(t, chord)
    assert len(fig.data) == 2                         # simulated + measured
    frames = load_cast1_frames()
    assert len(frames) == 4                           # MAV/MCL/RSP/MCF
