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
    # The handle (node 0) now translates along the hand-haul path (it is no
    # longer a fixed pivot): its position is finite and actually moves.
    assert np.isfinite(X[:, 0]).all() and np.isfinite(Y[:, 0]).all()
    assert np.ptp(X[:, 0]) > 0.1
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
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=51, line_out=2.5)
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


def test_cast1_handle_angle_sweeps_q2_to_q1():
    """Handle drive starts up-and-back (Q2) and ends up-and-forward (Q1)."""
    phi0 = np.degrees(float(_cast1_data.phi_handle_rad(-0.40)))
    phi_end = np.degrees(float(_cast1_data.phi_handle_rad(0.13)))
    assert 90.0 < phi0 < 180.0                         # second quadrant start
    assert 0.0 < phi_end < 90.0                        # first quadrant end
    # Clockwise sweep: the absolute angle decreases through the stroke.
    assert phi_end < phi0


def test_cast1_hand_translates():
    """The hand path moves forward and decelerates to rest by RSP."""
    x0, y0 = _cast1_data.hand_xy(-0.40)
    xr, yr = _cast1_data.hand_xy(0.0)
    assert xr > x0                                     # hand moves forward
    # Velocity is zero before the stroke and at/after the stop (RSP).
    vx_start, _ = _cast1_data.hand_vel(-0.50)
    vx_rsp, _ = _cast1_data.hand_vel(0.0)
    vx_mid, _ = _cast1_data.hand_vel(-0.20)
    assert np.isclose(vx_start, 0.0)
    assert np.isclose(vx_rsp, 0.0)
    assert vx_mid > 0.0                                # moving during the stroke


def test_cast1_rod_elevated_and_points_up():
    """The simulated rod stays elevated and ends pointing up-and-forward."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=101)
    def chord_angle(k):
        return np.degrees(np.arctan2(Y[k, rod_tip] - Y[k, 0],
                                     X[k, rod_tip] - X[k, 0]))
    # Starts up-and-back (Q2), ends up-and-forward (Q1).
    assert 90.0 < chord_angle(0) < 180.0
    assert 0.0 < chord_angle(len(t) - 1) < 90.0
    # The rod tip stays above the hand throughout (the rod never drops).
    assert np.all(Y[:, rod_tip] > Y[:, 0])


def test_cast1_handle_translates_in_sim():
    """The reconstructed handle node moves through space during the cast."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=101)
    assert np.ptp(X[:, 0]) > 0.1                       # handle is not pinned


def test_cast1_full_line_length():
    """The default Cast #1 domain spans the rod plus the full line + leader."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=101)
    from flycastsim.fem.cast import CAST1_ROD_LENGTH, CAST1_LINE_OUT
    assert np.isclose(s[-1], CAST1_ROD_LENGTH + CAST1_LINE_OUT, atol=1e-6)
    assert s[-1] > 15.0                                # ~15.5 m total


def test_cast1_colour_coded_viz_builds():
    """Animation and snapshots split the rod and line into coloured traces."""
    t, X, Y, s, chord, rod_tip = simulate_cast1(n_nodes=101)
    anim = animate_fly_cast(t, X, Y, rod_tip_index=rod_tip, n_frames=20)
    names = [d.name for d in anim.data]
    assert "rod" in names and "fly line" in names      # rod vs line coloured
    # Frames keep a consistent trace count.
    assert len(anim.frames[0].data) == len(anim.data)
    snaps = plot_cast_snapshots(t, X, Y, rod_tip_index=rod_tip, n_snapshots=6)
    assert any(d.name == "rod" for d in snaps.data)
