"""Plotly helpers for visualising fly-rod results (swingweight, profile
fits)."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .profile_fit import ProfileFitResult
from .swingweight import SwingweightResult


def plot_swingweight_contributions(result: SwingweightResult) -> go.Figure:
    """Bar chart of each section's swingweight contribution.

    The paper recommends graphing the per-section MOI against the distance of
    the section's balance point to the butt: it makes the dominant role of the
    upper (tip-ward) sections obvious, since MOI grows with the *square* of the
    distance to the axis.

    Args:
        result: A :class:`~flycastsim.rod.swingweight.SwingweightResult`.

    Returns:
        A Plotly :class:`~plotly.graph_objects.Figure` with one bar per
        section (height = contribution in :math:`g\\,m^2`, x = distance of the
        section balance point to the butt).
    """
    names = [s.name for s in result.sections]
    d = [s.d for s in result.sections]
    contrib = [s.I_sec_gm2 for s in result.sections]
    total = result.swingweight_gm2

    pct = [100.0 * c / total if total else 0.0 for c in contrib]
    text = [f"{c:.1f} g·m²<br>({p:.0f}%)" for c, p in zip(contrib, pct)]

    fig = go.Figure(
        go.Bar(x=d, y=contrib, text=text, textposition="outside",
               customdata=names,
               hovertemplate=("%{customdata}<br>"
                              "balance point: %{x:.3f} m from butt<br>"
                              "contribution: %{y:.2f} g·m²<extra></extra>"),
               marker_color="#1f77b4"))
    fig.update_layout(
        title=(f"Swingweight contribution by section "
               f"(total Iₛ = {total:.1f} g·m²)"),
        xaxis_title="Distance of section balance point to butt [m]",
        yaxis_title="Section contribution to swingweight [g·m²]",
        template="simple_white", showlegend=False)
    return fig


def plot_rod_profiles(result: ProfileFitResult, n: int = 200) -> go.Figure:
    """Fitted bending stiffness and mass density along the rod.

    The clamp position is marked; behind it the stiffness is not observed
    (held constant), and close to the tip it is poorly constrained because
    the bending moment vanishes there.
    """
    s = np.linspace(0.0, result.problem.length, n)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08)
    fig.add_trace(go.Scatter(x=s, y=result.EI(s), name="EI(s)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=s, y=1e3 * result.mu(s), name="mu(s)"),
                  row=2, col=1)
    for row in (1, 2):
        fig.add_vline(x=result.problem.s_clamp, line_dash="dot",
                      row=row, col=1)
    fig.update_yaxes(title_text="EI [N m^2]", type="log", row=1, col=1)
    fig.update_yaxes(title_text="mu [g/m]", row=2, col=1)
    fig.update_xaxes(title_text="s from butt [m]", row=2, col=1)
    fig.update_layout(title="Fitted rod profiles", showlegend=False)
    return fig


def plot_bend_fit(result: ProfileFitResult, every: int = 1) -> go.Figure:
    """Observed centre lines and fitted rod shapes for the bend frames.

    Shown in the frames' own coordinates: image pixels (``y`` down) when the
    fit used an image transform, otherwise metres relative to the clamp.
    """
    prob = result.problem
    tr, tp = prob.transform, result.transform_params
    EI, mu = result.EI, result.mu
    from .elastica import solve_cantilever_fd

    fig = go.Figure()
    for k, frame in enumerate(prob.frames):
        if k % every:
            continue
        sol = solve_cantilever_fd(
            EI, mu, length=prob.length, s_clamp=prob.s_clamp,
            tip_load=(frame.known_mass + result.frame_loads[k])
            * prob.gravity,
            clamp_angle=frame.clamp_angle + (tp[4] if tp is not None else 0),
            clamp_compliance=result.clamp_compliance)
        model = sol.at(np.linspace(prob.s_clamp, prob.length, 200))[:2].T
        if tr is not None:
            model = tr.to_pixels(tp, model)
        fig.add_trace(go.Scatter(x=frame.points[:, 0], y=frame.points[:, 1],
                                 mode="markers", marker=dict(size=4),
                                 name=f"frame {k} "
                                      f"({1e3 * result.frame_loads[k]:.0f} g)",
                                 legendgroup=str(k)))
        fig.add_trace(go.Scatter(x=model[:, 0], y=model[:, 1], mode="lines",
                                 line=dict(width=1), showlegend=False,
                                 legendgroup=str(k)))
    fig.update_yaxes(scaleanchor="x", scaleratio=1,
                     autorange="reversed" if tr is not None else True)
    fig.update_layout(title="Bend frames: traced centre line vs. fit")
    return fig
