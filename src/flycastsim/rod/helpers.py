"""Plotly helpers for visualising fly-rod results (swingweight, profile
fits)."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .profile_fit import ProfileFitResult
from .swingweight import SwingweightResult

#: Plotly's default qualitative colours, for consistent per-rod colours.
_COLORS = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
           "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52"]


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


# ---------------------------------------------------------------------------
# Fitted rods (bundled or fitted at run time), see flycastsim.rod.fitted
# ---------------------------------------------------------------------------
def plot_fitted_profiles(rods, n: int = 300) -> go.Figure:
    """Bending stiffness (log scale) and mass density of several fitted rods.

    Args:
        rods: :class:`~flycastsim.rod.fitted.FittedRod` objects.
    """
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08)
    for i, rod in enumerate(rods):
        s = np.linspace(0.0, rod.length, n)
        color = _COLORS[i % len(_COLORS)]
        fig.add_trace(go.Scatter(x=s, y=rod.EI(s), name=rod.id,
                                 legendgroup=rod.id, line=dict(color=color)),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=s, y=1e3 * rod.mu(s), name=rod.id,
                                 legendgroup=rod.id, showlegend=False,
                                 line=dict(color=color)), row=2, col=1)
    if rods:
        for row in (1, 2):
            fig.add_vline(x=rods[0].s_clamp, line_dash="dot", row=row, col=1)
    fig.update_yaxes(title_text="EI [N m²]", type="log", row=1, col=1)
    fig.update_yaxes(title_text="mass [g/m]", row=2, col=1)
    fig.update_xaxes(title_text="distance from butt [m]", row=2, col=1)
    fig.update_layout(title="Fitted stiffness and mass profiles "
                            "(dotted: clamp)", height=600)
    return fig


def plot_fitted_bend(rod, every: int = 1) -> go.Figure:
    """Traced centre lines (markers) and fitted rod shapes (lines) of a
    fitted rod's static-bend frames."""
    frames = rod.bend_frames()
    pixels = rod.summary.get("frame_units") == "px"
    fig = go.Figure()
    for k, frame in enumerate(frames[::every]):
        color = _COLORS[k % len(_COLORS)]
        name = (f"{frame['load_steps']:g}: "
                f"{1e3 * frame['added_mass_kg']:.0f} g")
        pts = frame["points"]
        fig.add_trace(go.Scatter(x=pts[:, 0], y=pts[:, 1], mode="markers",
                                 marker=dict(size=4, color=color), name=name,
                                 legendgroup=name))
        if frame["tip"] is not None:
            fig.add_trace(go.Scatter(
                x=[frame["tip"][0]], y=[frame["tip"][1]], mode="markers",
                marker=dict(size=9, symbol="x", color=color),
                showlegend=False, legendgroup=name))
        fig.add_trace(go.Scatter(x=frame["model"][:, 0],
                                 y=frame["model"][:, 1], mode="lines",
                                 line=dict(width=1.5, color=color),
                                 showlegend=False, legendgroup=name))
    fig.update_yaxes(scaleanchor="x", scaleratio=1,
                     autorange="reversed" if pixels else True)
    unit = "px" if pixels else "m"
    fig.update_layout(
        title=f"{rod.id}: traced centre line (dots, x = tip) vs. fit (lines)",
        xaxis_title=unit, yaxis_title=unit, legend_title="frame: load",
        height=600)
    return fig


def plot_fitted_frequency(rods) -> go.Figure:
    """Measured (markers) and model (lines) fundamental frequency vs. tip
    mass for fitted rods with frequency data."""
    fig = go.Figure()
    for i, rod in enumerate(rods):
        f = rod.summary.get("frequency")
        if not f:
            continue
        color = _COLORS[i % len(_COLORS)]
        m = 1e3 * np.asarray(f["tip_mass_kg"])
        fig.add_trace(go.Scatter(x=m, y=f["measured_hz"], mode="markers",
                                 name=f"{rod.id} measured", legendgroup=rod.id,
                                 marker=dict(color=color)))
        fig.add_trace(go.Scatter(x=m, y=f["model_hz"], mode="lines",
                                 name=f"{rod.id} model", legendgroup=rod.id,
                                 line=dict(color=color)))
    fig.update_layout(title="Fundamental frequency vs. tip mass",
                      xaxis_title="tip mass [g]", yaxis_title="frequency [Hz]")
    return fig


def plot_fitted_loads(rods) -> go.Figure:
    """Fitted added tip mass of each static-bend frame."""
    fig = go.Figure()
    for i, rod in enumerate(rods):
        steps = rod.summary.get("frame_load_steps")
        if not steps:
            continue
        fig.add_trace(go.Scatter(
            x=steps, y=1e3 * np.asarray(rod.summary["frame_added_mass_kg"]),
            mode="lines+markers", name=rod.id,
            line=dict(color=_COLORS[i % len(_COLORS)])))
    fig.update_layout(title="Fitted tip load per bend frame",
                      xaxis_title="frame", yaxis_title="added tip mass [g]")
    return fig


def fitted_rods_table(rods) -> list[dict]:
    """One summary row per fitted rod (plain dicts, e.g. for a DataFrame)."""
    rows = []
    for rod in rods:
        sm = rod.summary
        ccs = sm.get("ccs", {})
        n = sm.get("n_residuals")
        row = {
            "rod": rod.id,
            "label": rod.label,
            "length [m]": round(rod.length, 3),
            "mass [g]": round(rod.mass_g, 1),
            "swingweight [g m²]": round(rod.swingweight_gm2, 1),
            "EI clamp [N m²]": round(float(rod.EI(rod.s_clamp)), 2),
            "EI mid [N m²]": round(float(rod.EI(
                0.5 * (rod.s_clamp + rod.length))), 2),
            "EI tip-0.3 m [N m²]": round(float(rod.EI(rod.length - 0.3)), 3),
            "CCS IP [g]": (round(1e3 * ccs["ip_kg"], 1) if ccs else None),
            "CCS defl. model": (round(ccs["model_fraction"], 3)
                                if ccs else None),
            "mount compliance [deg/(N m)]": (
                round(float(np.degrees(sm["clamp_compliance_rad_per_Nm"])), 3)
                if "clamp_compliance_rad_per_Nm" in sm else None),
            "fit cost / residuals": (f"{sm['cost']:.0f} / {n}" if n
                                     else None),
        }
        rows.append(row)
    return rows
