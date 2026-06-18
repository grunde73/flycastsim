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
    """Rod loads (chord dips) and nearly straightens; chord stays bounded."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=51, line_out=2.5)
    rod_len = _cast1_data.CAST1_ROD_LENGTH \
        if hasattr(_cast1_data, "CAST1_ROD_LENGTH") \
        else _cast1_data.RIG["rod_length_m"]
    # Chord never exceeds the rod length.
    assert chord.max() <= rod_len + 1e-6
    # The rod measurably loads at some point (chord well below straight).
    assert chord.min() < 0.85 * rod_len
    # The rod also nearly straightens at some point in the stroke.
    assert chord.max() > 0.9 * rod_len


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


def test_cast1_event_frames_within_first_12s():
    """All event frames fall within the first 12 s of 30 fps playback."""
    import json
    from pathlib import Path
    meta = json.loads(
        (Path(__file__).resolve().parents[2] / "assets" / "cast1"
         / "captions.json").read_text())
    capture_fps = meta["capture_fps"]
    playback_fps = meta["playback_fps"]
    assert meta["rsp_frame"] == 317
    for fr in meta["frames"]:
        # Real capture time of the frame (>= 0 from start of footage).
        assert fr["frame"] >= 0
        # Time at normal (30 fps) playback must be inside the first 12 s.
        playback_t = fr["frame"] / playback_fps
        assert 0.0 <= playback_t <= 12.0
        # Stored t is relative to RSP at the capture frame rate.
        rel = (fr["frame"] - meta["rsp_frame"]) / capture_fps
        assert abs(rel - fr["t"]) < 1e-2


def test_cast1_handle_angle_sweeps_q4_to_q1():
    """Handle drive starts in Q4 (below level) and ends pointing up (Q1)."""
    phi0 = float(_cast1_data.phi_handle_rad(-0.40))
    phi_end = float(_cast1_data.phi_handle_rad(0.13))
    assert phi0 < 0.0                                  # fourth quadrant start
    assert phi_end > np.deg2rad(45.0)                  # ends pointing up


def test_cast1_rod_points_up_at_end():
    """The simulated rod ends pointing up and forward (tip above the handle)."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=61)
    # Rod-tip chord angle: below level at the start, up-forward at the end.
    def chord_angle(k):
        return np.degrees(np.arctan2(Y[k, rod_tip] - Y[k, 0],
                                     X[k, rod_tip] - X[k, 0]))
    assert chord_angle(0) < 0.0                        # starts low (Q4)
    assert chord_angle(len(t) - 1) > 0.0               # ends up-forward (Q1)
    # The rod tip finishes above the handle.
    assert Y[-1, rod_tip] > Y[0, rod_tip]
