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

from flycastsim import plot_chord_comparison, plot_tip_deflection
from flycastsim import load_cast1_frames
from flycastsim.fem import simulate_cast1, chord_length, tip_deflection
from flycastsim.fem import _cast1_data


def test_cast1_initial_phi_tilted_line():
    """The initial-shape helper sets the rod angle then a tilted-back line."""
    from flycastsim.fem import (cast1_initial_phi, cast1_domain,
                                CAST1_LINE_INIT_DEG)
    md = cast1_domain(n_nodes=51)
    theta0 = np.deg2rad(128.0)
    phi = cast1_initial_phi(theta0, md)
    assert phi.shape == (md.n_nodes,)
    rod_end = int(md.node_offsets[1])
    # The rod subdomain holds the handle angle.
    assert np.allclose(phi[:rod_end], theta0)
    # The fly line and leader start at the tilted-back target (~195 deg =
    # 15 deg below horizontal, behind the caster). The pinned rod-line hinge
    # carries the angle discontinuity, so no blend is applied.
    assert np.allclose(np.degrees(phi[rod_end:]), CAST1_LINE_INIT_DEG)
    assert CAST1_LINE_INIT_DEG > 180.0                 # tilted below horizontal


def test_cast1_line_mass_per_length():
    """Line mass follows the AFTM standard (rated head mass over 30 ft)."""
    # A 5-wt head is ~9.07 g over 30 ft (9.144 m) -> ~0.99 g/m.
    m5 = _cast1_data.line_mass_per_length(5)
    assert np.isclose(m5, 9.07 * 1e-3 / 9.144, rtol=1e-2)
    assert 0.7e-3 < m5 < 1.2e-3                         # ~1 g/m, physical
    # Heavier line weights are heavier per length (strictly monotonic).
    masses = [_cast1_data.line_mass_per_length(w) for w in (3, 4, 5, 6, 7, 8)]
    assert all(b > a for a, b in zip(masses, masses[1:]))
    # The AFTM head reference mass matches the published grain chart.
    assert np.isclose(_cast1_data.line_head_mass_grams(5), 9.07, atol=0.05)
    assert np.isclose(_cast1_data.line_head_mass_grams(8), 13.61, atol=0.05)


def test_cast1_data_events_ordered():
    """The reference event times are strictly increasing and RSP is t=0."""
    order = ["MAV", "MCL", "MAV/2", "RSP", "MCF"]
    ts = [_cast1_data.EVENTS[k]["t"] for k in order]
    assert all(a < b for a, b in zip(ts, ts[1:]))
    assert _cast1_data.EVENTS["RSP"]["t"] == 0.0


def test_simulate_cast1_runs_finite():
    """Cast #1 simulation is finite, fixed-handle and time-referenced to RSP."""
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=51)
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
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=51)
    rod_len = _cast1_data.CAST1_ROD_LENGTH \
        if hasattr(_cast1_data, "CAST1_ROD_LENGTH") \
        else _cast1_data.RIG["rod_length_m"]
    # The chord now runs from the rod tip to a base point ~30 cm up the blank,
    # so its straightened length is the rod length minus that base arc-length.
    from flycastsim.fem.cast import cast1_chord_base_index, cast1_domain
    md = cast1_domain(rig="cast1", n_nodes=51)
    base_s = float(s[cast1_chord_base_index(md)])
    eff_len = rod_len - base_s
    # Chord never exceeds the straightened tip-to-base length.
    assert chord.max() <= eff_len + 1e-6
    # The rod measurably loads at some point (chord dips below straight).
    assert chord.min() < 0.95 * eff_len
    # The rod also nearly straightens at some point in the stroke.
    assert chord.max() > 0.9 * eff_len


def test_chord_length_helper():
    """chord_length measures the base-node-to-tip distance over time."""
    X = np.array([[0.0, 1.0, 2.0], [0.0, 0.0, 3.0]])
    Y = np.array([[0.0, 0.0, 0.0], [0.0, 4.0, 0.0]])
    # Default base (node 0) -> rod tip (node 1).
    got = chord_length(X, Y, rod_tip_index=1)
    assert np.allclose(got, [1.0, 4.0])
    # Explicit base node 1 -> rod tip (node 2).
    got_base = chord_length(X, Y, rod_tip_index=2, base_index=1)
    assert np.allclose(got_base, [1.0, 5.0])


def test_tip_deflection_helper():
    """tip_deflection is the signed perpendicular offset from the tangent line."""
    # Butt at origin, node 1 the tip; butt tangent along +x (angle 0), so the
    # normal is +y and the perpendicular offset is just the tip's y.
    X = np.array([[0.0, 2.0], [0.0, 2.0], [0.0, 5.0]])
    Y = np.array([[0.0, 0.0], [0.0, 0.5], [0.0, 0.0]])
    butt_angle = np.array([0.0, 0.0, 0.0])
    d_signed, d_vec = tip_deflection(X, Y, rod_tip_index=1, butt_angle=butt_angle)
    # On the line -> 0; +0.5 perpendicular -> +0.5; along-rod only -> 0.
    assert np.allclose(d_signed, [0.0, 0.5, 0.0])
    assert np.allclose(d_vec, [[0.0, 0.0], [0.0, 0.5], [0.0, 0.0]])
    # Vector magnitude equals the absolute signed length.
    assert np.allclose(np.hypot(d_vec[:, 0], d_vec[:, 1]), np.abs(d_signed))

    # Rotated tangent (pointing up): tip bowed in -x reads positive (CCW side).
    Xu = np.array([[0.0, -0.35], [0.0, 0.0]])
    Yu = np.array([[0.0, 2.55], [0.0, 2.0]])
    du, dvu = tip_deflection(Xu, Yu, rod_tip_index=1,
                             butt_angle=np.array([np.pi / 2, np.pi / 2]))
    assert np.allclose(du, [0.35, 0.0])
    assert np.allclose(dvu, [[-0.35, 0.0], [0.0, 0.0]])

    # base_index anchors the tangent line at a non-zero node.
    Xb = np.array([[0.0, 1.0, 3.0]])
    Yb = np.array([[0.0, 1.0, 1.5]])
    db, _ = tip_deflection(Xb, Yb, rod_tip_index=2, butt_angle=np.array([0.0]),
                           base_index=1)
    assert np.allclose(db, [0.5])


def test_simulate_cast1_tip_deflection():
    """Tip deflection is finite, vector-consistent, and loads then straightens."""
    t, X, Y, s, chord, deflection, deflection_vec, rod_tip = \
        simulate_cast1(n_nodes=51)
    n_t = len(t)
    assert deflection.shape == (n_t,)
    assert deflection_vec.shape == (n_t, 2)
    assert np.isfinite(deflection).all() and np.isfinite(deflection_vec).all()
    # The vector magnitude matches the absolute signed scalar.
    assert np.allclose(np.hypot(deflection_vec[:, 0], deflection_vec[:, 1]),
                       np.abs(deflection))
    # The rod measurably deflects during the loading stroke ...
    assert np.abs(deflection).max() > 0.1
    # ... and nearly straightens at some point (deflection passes near zero).
    assert np.abs(deflection).min() < 0.1


def test_animate_fly_cast_rigid_rod():
    """The rigid-rod dashed trace appears only when its params are given."""
    t = np.array([0.0, 0.1, 0.2])
    X = np.array([[0.0, 1.0, 2.0], [0.0, 1.0, 2.0], [0.0, 1.0, 2.0]])
    Y = np.array([[0.0, 0.1, 0.2], [0.0, 0.2, 0.4], [0.0, 0.3, 0.6]])
    angle = np.array([np.pi / 2, np.pi / 2, np.pi / 2])

    with_rod = animate_fly_cast(t, X, Y, rod_tip_index=2, n_frames=3,
                                rigid_rod_angle=angle, rigid_rod_length=2.74)
    names = [d.name for d in with_rod.data]
    assert "rigid rod (undeflected)" in names
    # Every frame also carries the dashed rigid-rod trace.
    for fr in with_rod.frames:
        assert any(d.name == "rigid rod (undeflected)" for d in fr.data)

    without = animate_fly_cast(t, X, Y, rod_tip_index=2, n_frames=3)
    assert "rigid rod (undeflected)" not in [d.name for d in without.data]


def test_cast1_comparison_and_frames():
    """The comparison figure builds and the event frames load."""
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=51)
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


def test_cast1_rod_loads_and_stays_elevated():
    """The rod loads against the backcast line, sweeps forward and stays up."""
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=101)
    def chord_angle(k):
        return np.degrees(np.arctan2(Y[k, rod_tip] - Y[k, 0],
                                     X[k, rod_tip] - X[k, 0]))
    ang = np.array([chord_angle(k) for k in range(len(t))])
    # Starts up-and-back (second quadrant) with the rod held elevated.
    assert 90.0 < ang[0] < 180.0
    # Driven forward through the stroke, the rod reaches at least the vertical
    # (loading deeply against the heavy tilted backcast line).
    assert ang.min() < 95.0
    # The rod tip stays above the hand throughout (the rod never drops).
    assert np.all(Y[:, rod_tip] > Y[:, 0])


def test_cast1_line_starts_tilted_behind():
    """The fly line starts behind the caster, tilted up toward the rod tip."""
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=101)
    # A line node well past the rod tip starts far behind the hand (negative x).
    j = rod_tip + (len(s) - rod_tip) // 2
    assert X[0, j] < X[0, 0] - 1.0                     # behind the hand (-x)
    # The far end of the line lies well behind the caster.
    assert X[0, -1] < -5.0
    # The line tilts down away from the rod tip, so the line end is the lowest
    # point of the line/leader portion (past the rod tip) and the rod tip is the
    # highest.
    assert Y[0, -1] < Y[0, rod_tip]
    assert Y[0, -1] == np.min(Y[0, rod_tip:])          # line end is lowest line node
    # The line slopes downward going away from the rod tip (tilted ~5 deg
    # below horizontal: tangent points back and down, ~185 deg).
    seg = np.degrees(np.arctan2(Y[0, j + 1] - Y[0, j],
                                X[0, j + 1] - X[0, j])) % 360.0
    assert 180.0 < seg < 210.0


def test_cast1_line_weight_changes_loading():
    """A heavier AFTM line loads the rod differently (and stays finite)."""
    t3, X3, Y3, *_ = simulate_cast1(n_nodes=101, line_weight=3)
    t8, X8, Y8, *_ = simulate_cast1(n_nodes=101, line_weight=8)
    assert np.isfinite(X3).all() and np.isfinite(X8).all()
    # The heavier line produces a measurably different rod/line motion.
    assert not np.allclose(Y3, Y8)


def test_cast1_handle_translates_in_sim():
    """The reconstructed handle node moves through space during the cast."""
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=101)
    assert np.ptp(X[:, 0]) > 0.1                       # handle is not pinned


def test_cast1_full_line_length():
    """The default Cast #1 domain spans the rod plus the full line + leader."""
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=101)
    from flycastsim.fem.cast import CAST1_ROD_LENGTH, CAST1_LINE_OUT
    assert np.isclose(s[-1], CAST1_ROD_LENGTH + CAST1_LINE_OUT, atol=1e-6)
    assert s[-1] > 15.0                                # ~15.5 m total


def test_cast1_colour_coded_viz_builds():
    """Animation and snapshots split the rod and line into coloured traces."""
    t, X, Y, s, chord, *_, rod_tip = simulate_cast1(n_nodes=101)
    anim = animate_fly_cast(t, X, Y, rod_tip_index=rod_tip, n_frames=20)
    names = [d.name for d in anim.data]
    assert "rod" in names and "fly line" in names      # rod vs line coloured
    # Frames keep a consistent trace count.
    assert len(anim.frames[0].data) == len(anim.data)
    snaps = plot_cast_snapshots(t, X, Y, rod_tip_index=rod_tip, n_snapshots=6)
    assert any(d.name == "rod" for d in snaps.data)
