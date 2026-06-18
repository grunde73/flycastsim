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
                     line_color="#1f77b4", tip_color="#d62728"):
    """Build a Plotly animation of a fly cast.

    Args:
        t: 1-D array of times, shape ``(n_steps + 1,)``.
        X, Y: Node coordinates over time, shape ``(n_steps + 1, n_nodes)``
            (as returned by :func:`flycastsim.fem.simulate_cast`).
        n_frames: Number of animation frames (the data is down-sampled to keep
            the figure light).
        frame_ms: Milliseconds per frame during playback.
        line_color: Colour of the rod/line.
        tip_color: Colour of the marker drawn at the (fly) tip.

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

    (x_lo, x_hi), (y_lo, y_hi) = _axis_ranges(X, Y)

    def _traces(i):
        return [
            go.Scatter(x=X[i], y=Y[i], mode="lines",
                       line=dict(color=line_color, width=3),
                       name="line", showlegend=False),
            go.Scatter(x=[X[i, 0]], y=[Y[i, 0]], mode="markers",
                       marker=dict(color="black", size=10, symbol="square"),
                       name="handle", showlegend=False),
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


def plot_cast_snapshots(t, X, Y, *, n_snapshots=12, cmap="Viridis"):
    """Overlay stroboscopic snapshots of the line shape through the cast.

    Args:
        t: 1-D array of times.
        X, Y: Node coordinates over time, shape ``(n_steps + 1, n_nodes)``.
        n_snapshots: Number of equally-spaced shapes to draw.
        cmap: Name of a Plotly colour scale used to colour snapshots by time.

    Returns:
        plotly.graph_objects.Figure
    """
    t = np.asarray(t)
    X = np.asarray(X)
    Y = np.asarray(Y)
    n_rows = X.shape[0]
    idx = np.linspace(0, n_rows - 1, n_snapshots).round().astype(int)
    colors = _sample_colorscale(cmap, len(idx))

    fig = go.Figure()
    for c, i in zip(colors, idx):
        fig.add_trace(go.Scatter(
            x=X[i], y=Y[i], mode="lines",
            line=dict(color=c, width=2),
            name=f"t={t[i]:.2f}s"))
    # mark the handle pivot
    fig.add_trace(go.Scatter(
        x=[X[0, 0]], y=[Y[0, 0]], mode="markers",
        marker=dict(color="black", size=10, symbol="square"),
        name="handle"))

    (x_lo, x_hi), (y_lo, y_hi) = _axis_ranges(X, Y)
    fig.update_layout(
        xaxis=dict(range=[x_lo, x_hi], title="x [m]"),
        yaxis=dict(range=[y_lo, y_hi], title="y [m]",
                   scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(title="time"),
    )
    return fig


def plot_chord_comparison(t_sim, chord_sim, *, show_measured=True):
    """Compare simulated rod chord length against the measured Cast #1 curve.

    Plots the simulated handle-to-rod-tip chord length over time together with
    the (approximately digitized) measured chord length from the article's
    Figure 1/2, and marks the labelled events (MAV, MCL, RSP, MCF).  Time is
    relative to RSP (``t = 0``).

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
        name="simulated (rod tip → handle)"))

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
