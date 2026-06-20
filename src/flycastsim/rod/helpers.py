"""Plotly helpers for visualising fly-rod swingweight results."""

from __future__ import annotations

import plotly.graph_objects as go

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
