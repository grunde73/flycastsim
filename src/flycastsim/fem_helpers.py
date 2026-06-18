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
