"""Plotly helpers for visualising FEM fly-cast simulations.

These mirror the brick-spring helpers: ``simulate_cast`` (in
:mod:`flycastsim.fem.cast`) produces the line shape over time, and the
functions here turn that into Plotly figures.  Keeping the plotting here means
the numerical core (:mod:`flycastsim.fem`) stays free of any plotting
dependency.
"""

import numpy as np
import plotly.graph_objects as go


def _axis_ranges(X, Y, pad=0.3):
    """Fixed, square-ish axis ranges that contain the whole motion."""
    x_min, x_max = float(X.min()), float(X.max())
    y_min, y_max = float(Y.min()), float(Y.max())
    return (x_min - pad, x_max + pad), (y_min - pad, y_max + pad)


def animate_fly_cast(t, X, Y, *, n_frames=120, frame_ms=40,
                     line_color="#1f77b4", tip_color="#d62728",
                     rod_tip_index=None, rod_color="#5c3a21",
                     fly_line_color="#ff7f0e",
                     rigid_rod_angle=None, rigid_rod_length=None,
                     rigid_rod_color="#888888"):
    """Build a Plotly animation of a fly cast.

    Args:
        t: 1-D array of times, shape ``(n_steps + 1,)``.
        X, Y: Node coordinates over time, shape ``(n_steps + 1, n_nodes)``
            (as returned by :func:`flycastsim.fem.simulate_cast`).
        n_frames: Number of animation frames (the data is down-sampled to keep
            the figure light).
        frame_ms: Milliseconds per frame during playback.
        line_color: Colour of the whole rod/line when ``rod_tip_index`` is
            ``None`` (single-colour mode).
        tip_color: Colour of the marker drawn at the (fly) tip.
        rod_tip_index: If given, the node index of the rod tip.  The rod segment
            (nodes ``0..rod_tip_index``) and the fly-line segment
            (``rod_tip_index..end``) are then drawn in distinct colours with a
            legend.
        rod_color, fly_line_color: Colours for the rod and the fly line when
            ``rod_tip_index`` is given.
        rigid_rod_angle: Optional per-row rod-butt tangent angle [rad], shape
            ``(n_steps + 1,)`` (same convention as
            :func:`flycastsim.fem._cast1_data.phi_handle_rad`).  When given
            together with ``rigid_rod_length``, the **imaginary rigid
            (undeflected) rod** -- the reference used by
            :func:`flycastsim.fem.tip_deflection` -- is drawn as a dashed line
            from the rod butt (node 0) along this tangent.
        rigid_rod_length: Optional length [m] of the imaginary rigid rod.
        rigid_rod_color: Colour of the dashed imaginary rigid rod.

    Returns:
        plotly.graph_objects.Figure
    """
    t = np.asarray(t)
    X = np.asarray(X)
    Y = np.asarray(Y)
    n_rows = X.shape[0]
    step = max(1, n_rows // n_frames)
    idx = np.arange(0, n_rows, step)
    if idx[-1] != n_rows - 1:
        idx = np.append(idx, n_rows - 1)

    show_rigid = rigid_rod_angle is not None and rigid_rod_length is not None
    if show_rigid:
        rigid_rod_angle = np.asarray(rigid_rod_angle, dtype=float)
        rod_end_x = X[:, 0] + rigid_rod_length * np.cos(rigid_rod_angle)
        rod_end_y = Y[:, 0] + rigid_rod_length * np.sin(rigid_rod_angle)
        x_for_range = np.concatenate([X.ravel(), rod_end_x])
        y_for_range = np.concatenate([Y.ravel(), rod_end_y])
        (x_lo, x_hi), (y_lo, y_hi) = _axis_ranges(x_for_range, y_for_range)
    else:
        (x_lo, x_hi), (y_lo, y_hi) = _axis_ranges(X, Y)
    split = rod_tip_index is not None

    def _traces(i):
        if split:
            r = rod_tip_index
            line_segments = [
                go.Scatter(x=X[i, :r + 1], y=Y[i, :r + 1], mode="lines",
                           line=dict(color=rod_color, width=4),
                           name="rod", showlegend=True),
                go.Scatter(x=X[i, r:], y=Y[i, r:], mode="lines",
                           line=dict(color=fly_line_color, width=2),
                           name="fly line", showlegend=True),
            ]
        else:
            line_segments = [
                go.Scatter(x=X[i], y=Y[i], mode="lines",
                           line=dict(color=line_color, width=3),
                           name="line", showlegend=False),
            ]
        if show_rigid:
            line_segments.append(
                go.Scatter(x=[X[i, 0], rod_end_x[i]],
                           y=[Y[i, 0], rod_end_y[i]], mode="lines",
                           line=dict(color=rigid_rod_color, width=2,
                                     dash="dash"),
                           name="rigid rod (undeflected)", showlegend=True))
        return line_segments + [
            go.Scatter(x=[X[i, 0]], y=[Y[i, 0]], mode="markers",
                       marker=dict(color="black", size=10, symbol="square"),
                       name="hand", showlegend=False),
            go.Scatter(x=[X[i, -1]], y=[Y[i, -1]], mode="markers",
                       marker=dict(color=tip_color, size=8),
                       name="fly", showlegend=False),
        ]

    frames = [go.Frame(data=_traces(i), name=f"{t[i]:.3f}") for i in idx]
    fig = go.Figure(data=_traces(idx[0]), frames=frames)

    play_button = dict(
        label="Play", method="animate",
        args=[None, dict(frame=dict(duration=frame_ms, redraw=True),
                         fromcurrent=True, transition=dict(duration=0))])
    pause_button = dict(
        label="Pause", method="animate",
        args=[[None], dict(frame=dict(duration=0, redraw=False),
                           mode="immediate", transition=dict(duration=0))])
    slider = dict(
        steps=[dict(method="animate", label=f"{t[i]:.2f}",
                    args=[[f"{t[i]:.3f}"],
                          dict(mode="immediate",
                               frame=dict(duration=0, redraw=True),
                               transition=dict(duration=0))])
               for i in idx],
        x=0.1, len=0.9, currentvalue=dict(prefix="time [s]: "))

    fig.update_layout(
        xaxis=dict(range=[x_lo, x_hi], zeroline=False, showgrid=False,
                   title="x [m]"),
        yaxis=dict(range=[y_lo, y_hi], zeroline=False, showgrid=False,
                   title="y [m]", scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=40, b=10),
        updatemenus=[dict(type="buttons", direction="left",
                          x=0.1, y=1.15, showactive=False,
                          buttons=[play_button, pause_button])],
        sliders=[slider],
    )
    return fig


def plot_cast_snapshots(t, X, Y, *, n_snapshots=12, cmap="Viridis",
                        rod_tip_index=None, rod_color="#5c3a21"):
    """Overlay stroboscopic snapshots of the line shape through the cast.

    Args:
        t: 1-D array of times.
        X, Y: Node coordinates over time, shape ``(n_steps + 1, n_nodes)``.
        n_snapshots: Number of equally-spaced shapes to draw.
        cmap: Name of a Plotly colour scale used to colour snapshots by time.
        rod_tip_index: If given, the rod segment (nodes ``0..rod_tip_index``) is
            drawn in ``rod_color`` at every snapshot and only the fly-line
            segment is time-coloured, so the rod stands out from the line.
        rod_color: Colour of the rod segment when ``rod_tip_index`` is given.

    Returns:
        plotly.graph_objects.Figure
    """
    t = np.asarray(t)
    X = np.asarray(X)
    Y = np.asarray(Y)
    n_rows = X.shape[0]
    idx = np.linspace(0, n_rows - 1, n_snapshots).round().astype(int)
    colors = _sample_colorscale(cmap, len(idx))
    split = rod_tip_index is not None

    fig = go.Figure()
    for c, i in zip(colors, idx):
        if split:
            r = rod_tip_index
            fig.add_trace(go.Scatter(
                x=X[i, r:], y=Y[i, r:], mode="lines",
                line=dict(color=c, width=1.5),
                name=f"t={t[i]:.2f}s", legendgroup="line"))
            fig.add_trace(go.Scatter(
                x=X[i, :r + 1], y=Y[i, :r + 1], mode="lines",
                line=dict(color=rod_color, width=4),
                showlegend=False, legendgroup="rod"))
        else:
            fig.add_trace(go.Scatter(
                x=X[i], y=Y[i], mode="lines",
                line=dict(color=c, width=2),
                name=f"t={t[i]:.2f}s"))
    if split:
        # one legend proxy for the rod colour
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                                 line=dict(color=rod_color, width=4),
                                 name="rod"))
    # mark the (possibly moving) hand
    fig.add_trace(go.Scatter(
        x=[X[0, 0]], y=[Y[0, 0]], mode="markers",
        marker=dict(color="black", size=10, symbol="square"),
        name="hand (start)"))

    (x_lo, x_hi), (y_lo, y_hi) = _axis_ranges(X, Y)
    fig.update_layout(
        xaxis=dict(range=[x_lo, x_hi], title="x [m]"),
        yaxis=dict(range=[y_lo, y_hi], title="y [m]",
                   scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(title="time / part" if split else "time"),
    )
    return fig


def plot_chord_comparison(t_sim, chord_sim, *, show_measured=True):
    """Compare simulated rod chord length against the measured Cast #1 curve.

    Plots the simulated rod chord length over time (rod tip to a base point
    ~30 cm up the rod blank) together with the (approximately digitized)
    measured chord length from the article's Figure 1/2, and marks the labelled
    events (MAV, MCL, RSP, MCF).  Time is relative to RSP (``t = 0``).

    Args:
        t_sim: 1-D array of simulation times [s] (relative to RSP).
        chord_sim: Simulated rod chord length [m], same shape as ``t_sim``.
        show_measured: Whether to overlay the digitized measured curve.

    Returns:
        plotly.graph_objects.Figure
    """
    from .fem import _cast1_data as c1

    t_sim = np.asarray(t_sim)
    chord_sim = np.asarray(chord_sim)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t_sim, y=chord_sim, mode="lines",
        line=dict(color="#1f77b4", width=3),
        name="simulated (rod tip → 30 cm base)"))

    if show_measured:
        fig.add_trace(go.Scatter(
            x=c1.CHORD_M[:, 0], y=c1.CHORD_M[:, 1], mode="lines+markers",
            line=dict(color="#d62728", width=2, dash="dot"),
            marker=dict(size=5),
            name="measured (digitized, approx.)"))

    y_all = list(chord_sim)
    if show_measured:
        y_all += list(c1.CHORD_M[:, 1])
    y_lo, y_hi = min(y_all), max(y_all)
    pad = 0.05 * (y_hi - y_lo + 1e-9)
    for name, ev in c1.EVENTS.items():
        if name == "MAV/2":
            continue
        fig.add_vline(x=ev["t"], line=dict(color="gray", width=1, dash="dash"))
        fig.add_annotation(x=ev["t"], y=y_hi + pad, text=name,
                           showarrow=False, font=dict(size=11, color="gray"))

    fig.update_layout(
        xaxis=dict(title="time relative to RSP [s]"),
        yaxis=dict(title="chord length [m]", range=[y_lo - pad, y_hi + 2 * pad]),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def plot_tip_deflection(t_sim, deflection_sim):
    """Plot the simulated signed rod tip deflection over time.

    Shows the signed perpendicular deflection of the rod tip from the
    undeflected (straight) rod — the tangent line through the rod butt (see
    :func:`flycastsim.fem.tip_deflection`).  Positive values place the tip on
    the CCW side of the butt-tangent direction; ``0`` means the rod is straight.
    A zero reference line and the labelled events (MAV, MCL, RSP, MCF) are
    marked.  Time is relative to RSP (``t = 0``).  There is no measured
    deflection curve, so this is simulated-only.

    Args:
        t_sim: 1-D array of simulation times [s] (relative to RSP).
        deflection_sim: Simulated signed tip deflection [m], same shape as
            ``t_sim``.

    Returns:
        plotly.graph_objects.Figure
    """
    from .fem import _cast1_data as c1

    t_sim = np.asarray(t_sim)
    deflection_sim = np.asarray(deflection_sim)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t_sim, y=deflection_sim, mode="lines",
        line=dict(color="#2ca02c", width=3),
        name="simulated tip deflection"))

    fig.add_hline(y=0.0, line=dict(color="gray", width=1, dash="dot"))

    y_lo, y_hi = float(deflection_sim.min()), float(deflection_sim.max())
    pad = 0.05 * (y_hi - y_lo + 1e-9)
    for name, ev in c1.EVENTS.items():
        if name == "MAV/2":
            continue
        fig.add_vline(x=ev["t"], line=dict(color="gray", width=1, dash="dash"))
        fig.add_annotation(x=ev["t"], y=y_hi + pad, text=name,
                           showarrow=False, font=dict(size=11, color="gray"))

    fig.update_layout(
        xaxis=dict(title="time relative to RSP [s]"),
        yaxis=dict(title="tip deflection [m]",
                   range=[y_lo - pad, y_hi + 2 * pad]),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def plot_cast_speeds(t_sim, rod_tip_speed, line_speed, lever_speed, *,
                     line_distance=0.0, show_measured=True):
    """Plot rod-tip, line and rigid-lever speeds over time for a fly cast.

    Shows three simulated speed curves and (optionally) the exact published
    rod-tip speeds from Cast #1 Table 1 as comparison markers:

    * **rod tip** -- speed of the real (deflected) rod-tip node;
    * **line** -- speed of a line node a selectable arc-length ``line_distance``
      back from the line tip (``0`` = the fly/leader tip);
    * **rigid lever** -- speed of the imaginary rigid (undeflected) rod's tip,
      i.e. the tip speed with zero rod flex (see
      :func:`flycastsim.fem.rigid_lever_speed`).

    The labelled events (MAV/MCL/RSP/MCF) are marked.  Time is relative to RSP
    (``t = 0``).

    Args:
        t_sim: 1-D array of simulation times [s] (relative to RSP).
        rod_tip_speed: Real rod-tip speed [m/s], same shape as ``t_sim``.
        line_speed: Line-node speed [m/s], same shape as ``t_sim``.
        lever_speed: Imaginary rigid-lever tip speed [m/s], same shape as
            ``t_sim``.
        line_distance: Arc-length distance back from the line tip [m] at which
            ``line_speed`` was sampled (used only for the legend label).
        show_measured: Whether to overlay the exact published rod-tip speeds
            from Table 1 as markers.

    Returns:
        plotly.graph_objects.Figure
    """
    from .fem import _cast1_data as c1

    t_sim = np.asarray(t_sim)
    rod_tip_speed = np.asarray(rod_tip_speed)
    line_speed = np.asarray(line_speed)
    lever_speed = np.asarray(lever_speed)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t_sim, y=rod_tip_speed, mode="lines",
        line=dict(color="#d62728", width=3),
        name="rod tip"))
    fig.add_trace(go.Scatter(
        x=t_sim, y=line_speed, mode="lines",
        line=dict(color="#ff7f0e", width=2.5),
        name=f"line ({line_distance:.1f} m from tip)"))
    fig.add_trace(go.Scatter(
        x=t_sim, y=lever_speed, mode="lines",
        line=dict(color="#888888", width=2, dash="dash"),
        name="rigid lever (no flex)"))

    y_all = [rod_tip_speed, line_speed, lever_speed]
    measured = [(ev["t"], ev["vt"]) for name, ev in c1.EVENTS.items()
                if name != "MAV/2"]
    if show_measured and measured:
        mt, mv = zip(*measured)
        fig.add_trace(go.Scatter(
            x=list(mt), y=list(mv), mode="markers",
            marker=dict(color="#d62728", size=9, symbol="x"),
            name="measured rod-tip speed (Table 1)"))
        y_all.append(np.asarray(mv, dtype=float))

    y_concat = np.concatenate([np.ravel(a) for a in y_all])
    y_lo, y_hi = float(y_concat.min()), float(y_concat.max())
    pad = 0.05 * (y_hi - y_lo + 1e-9)
    for name, ev in c1.EVENTS.items():
        if name == "MAV/2":
            continue
        fig.add_vline(x=ev["t"], line=dict(color="gray", width=1, dash="dash"))
        fig.add_annotation(x=ev["t"], y=y_hi + pad, text=name,
                           showarrow=False, font=dict(size=11, color="gray"))

    fig.update_layout(
        xaxis=dict(title="time relative to RSP [s]"),
        yaxis=dict(title="speed [m/s]",
                   range=[min(0.0, y_lo - pad), y_hi + 2 * pad]),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def load_cast1_frames(assets_dir=None):
    """Load the labelled Cast #1 event frames (MAV/MCL/RSP/MCF).

    Reads ``assets/cast1/captions.json`` and returns the frame image paths with
    their captions, ready for display (e.g. with ``streamlit.image``).

    Args:
        assets_dir: Path to the ``assets/cast1`` directory.  If ``None``, it is
            resolved relative to the repository root.

    Returns:
        A list of ``(path, caption)`` tuples, or an empty list if the frames
        are not present (e.g. in a packaged install without ``assets/``).
    """
    import json
    from pathlib import Path

    if assets_dir is None:
        # repo_root/assets/cast1  (this file is src/flycastsim/fem_helpers.py)
        assets_dir = Path(__file__).resolve().parents[2] / "assets" / "cast1"
    assets_dir = Path(assets_dir)
    captions = assets_dir / "captions.json"
    if not captions.is_file():
        return []
    meta = json.loads(captions.read_text())
    out = []
    for fr in meta.get("frames", []):
        path = assets_dir / fr["file"]
        if path.is_file():
            cap = f"{fr['event']} (t={fr['t']:+.3f}s) — {fr['label']}"
            out.append((str(path), cap))
    return out


def _sample_colorscale(name, n):
    """Return ``n`` colours sampled along a named Plotly colour scale."""
    try:
        from plotly.colors import sample_colorscale
        positions = np.linspace(0.0, 1.0, n)
        return sample_colorscale(name, list(positions))
    except Exception:
        # Fallback: a simple blue-to-red ramp.
        return [f"rgb({int(255 * u)},0,{int(255 * (1 - u))})"
                for u in np.linspace(0.0, 1.0, n)]
