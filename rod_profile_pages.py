"""Streamlit views for fitted rod stiffness / mass profiles.

Used by ``streamlit_app.py`` (*Rod parameters* section).  All computation
lives in :mod:`flycastsim.rod`; this module only lays out widgets and plots.
Rods fitted in the app are kept for the session in
``st.session_state["session_rods"]`` (key -> fitted-rod folder) so the
comparison view and the Cast #1 rod selector can use them.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from flycastsim.rod import (FittedRod, fitted_rods_table, load_fitted_rods,
                            plot_fitted_bend, plot_fitted_frequency,
                            plot_fitted_loads, plot_fitted_profiles)


@st.cache_resource
def bundled_fitted_rods() -> dict[str, FittedRod]:
    """The fitted rods shipped with the package, by id."""
    return {rod.id: rod for rod in load_fitted_rods()}


def available_fitted_rods() -> dict[str, FittedRod]:
    """Bundled fitted rods plus rods fitted in this session.

    Keys are ``"bundled:<id>"`` and ``"session:<id>"``.
    """
    rods = {f"bundled:{k}": v for k, v in bundled_fitted_rods().items()}
    for key, folder in st.session_state.get("session_rods", {}).items():
        rods[key] = FittedRod.from_folder(folder)
    return rods


def rod_label(key: str, rod: FittedRod) -> str:
    """Display name of a fitted rod in selectors."""
    where = "fitted" if key.startswith("bundled:") else "fitted this session"
    return f"{rod.id} — {rod.label.removesuffix(' - fitted rod')} ({where})"


@st.cache_data(show_spinner="Rebuilding the fitted bend shapes...")
def _bend_figure(folder: str, every: int):
    return plot_fitted_bend(FittedRod.from_folder(folder), every=every)


def stiffness_profiles_page(show_intro: bool) -> None:
    """Compare fitted rods: profiles, fit to the data, summary table."""
    st.write("""
    # Rod parameters — Stiffness profiles
    Bending stiffness **EI(s)** and mass per length **μ(s)** along the rod,
    fitted to **static bend tests** (the rod clamped near the butt and
    loaded at the tip in steps, filmed frame by frame), a **tip-mass
    frequency test** and the **Common Cents System** (CCS) point.  The
    fitted rods can be used in *Sample fly cast* (Cast #1).
    """)
    if show_intro:
        st.info("""
        **How it works:** the rod centre line is traced in every frame of the
        bend test, and a large-deflection beam model (the *elastica*) is
        fitted to all frames at once, together with the frequency and CCS
        data.  EI is a smooth spline that may only decrease from butt to tip;
        the mass density is linear within each section (as for swingweight).
        The tip load of each frame, the give of the mount and the camera
        calibration are fitted too.  EI behind the clamp (the handle) is not
        observed and held constant; EI within ~0.3 m of the tip is poorly
        constrained, since the bending moment vanishes there.  See
        ``docs/rod_profile.rst`` for the details.
        """)

    rods = available_fitted_rods()
    if not rods:
        st.warning("No fitted rods found.")
        return
    keys = list(rods)
    chosen = st.multiselect(
        "Rods to compare", keys, default=keys,
        format_func=lambda k: rod_label(k, rods[k]))
    selected = [rods[k] for k in chosen]
    if not selected:
        st.info("Select at least one rod.")
        return

    st.plotly_chart(plot_fitted_profiles(selected), width="stretch")
    st.write("### Summary")
    st.dataframe(pd.DataFrame(fitted_rods_table(selected)).set_index("rod"),
                 width="stretch")
    st.caption(
        "Mass and swingweight come from the fitted mass profile (PA905 has "
        "no section measurements yet, so its mass profile is a guess). "
        "*CCS defl. model* is the model's tip deflection at the CCS load as "
        "a fraction of the free length (measured: 1/3).")

    col1, col2 = st.columns(2)
    col1.plotly_chart(plot_fitted_frequency(selected), width="stretch")
    col2.plotly_chart(plot_fitted_loads(selected), width="stretch")

    st.write("### Fit to the bend frames")
    key = st.selectbox("Rod", chosen,
                       format_func=lambda k: rod_label(k, rods[k]))
    every = st.slider("Show every n-th frame", 1, 4, 2)
    st.plotly_chart(_bend_figure(str(rods[key].folder), every),
                    width="stretch")
    st.caption(
        "Dots: traced rod centre line; x: tip; lines: the fitted model for "
        "each frame's fitted load, in image pixels (y down).")
